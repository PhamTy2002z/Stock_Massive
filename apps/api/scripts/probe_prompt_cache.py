"""Does the route's automatic prefix cache read back the head C2 built for it.

One question, and the reason it needs a script rather than a reading is that the
last answer to it was measured on a different prompt. The 2026-08-23 measurement
(``plans/reports/measurement-260823-1238-prompt-cache-on-cliproxy.md``) found
the route caching prefixes on its own and found explicit ``cache_control``
adding nothing — so the flag stayed off. Since then the prompt has come apart
into a core and a pack body and the body has moved into the cacheable head. That
changes the bytes a cache is keyed on, and a decision made about other bytes is
not a decision about these.

**What it measures, and what it refuses to.** It sends several calls that share
a prefix and differ only in a short tail, and reports what the provider says
came back cached, in aggregate. Aggregate is the honest unit: the earlier
measurement recorded a load balancer serving 3 hits in 8 on the same prefix, so
a per-call assertion would be a test of which backend answered. A single miss is
not a failure; a total of zero is.

**The prefix is production's, not a pad.** It is built by handing a real
:class:`Transcript` to ``build_messages``, so what goes out is the message the
loop sends, block boundaries and all. Padding a prompt until it crosses a
provider's minimum would measure the provider's minimum.

**It never boot-blocks anything.** Not a sixth ``CapabilityProbe`` check:
``enforce_capability_probe`` raises when any check fails, and whether a cache is
warm has no business stopping an API from starting.

Run by hand. It spends real model calls, so it is not in the suite and not in CI.

    make probe-prompt-cache CEILING_USD=0.50

Writes ``plans/reports/probe-<date>-prompt-cache.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from src.core.llm import (
    BudgetLane,
    CallOwner,
    Completion,
    CompletionRequest,
    OwnerType,
    SpendRequest,
    Usage,
    Workload,
    build_client,
    llm_config_from_settings,
)
from src.core.llm.admission import PROBE_DAILY_MICRO_USD
from src.core.llm.probe import PROBE_OUTPUT_TOKENS

#: How many calls one prefix family sends.
#:
#: Four. One call cannot show a cache — the first is always a miss, because
#: there is nothing to read back yet — and the earlier measurement of this route
#: found hits arriving 3 in 8 through a load balancer, so a family of two could
#: report zero on a working cache. Four is the smallest number that separates
#: "cold" from "not caching" without paying for eight.
CALLS_PER_FAMILY = 4

#: How much of the reader's own words each call carries.
#:
#: A different short question per call, so the prefix is shared and the tail is
#: not. Deliberately short: a long tail would make the fresh half of every call
#: large enough to blur the counter this is reading.
QUESTIONS = (
    "Một câu ngắn về việc bạn làm được gì.",
    "Hai câu ngắn về việc bạn làm được gì.",
    "Ba câu ngắn về việc bạn làm được gì.",
    "Bốn câu ngắn về việc bạn làm được gì.",
)


def _reports_dir() -> Path:
    """``plans/reports`` at the repo root, found by walking up.

    The same walk ``probe_vision`` does, and for the same reason: this runs from
    the host checkout and from inside the container, and those are two depths.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "plans" / "reports"
        if candidate.is_dir():
            return candidate
    return here.parent


REPORTS = _reports_dir()


@dataclass
class Call:
    """One request, and what the provider said it cost."""

    family: str
    index: int
    usage: Usage | None = None
    error: str = ""

    @property
    def fresh(self) -> int:
        return self.usage.input_tokens if self.usage else 0

    @property
    def cached(self) -> int:
        return self.usage.cached_input_tokens if self.usage else 0

    @property
    def written(self) -> int:
        return self.usage.cache_write_tokens if self.usage else 0

    @property
    def prompt(self) -> int:
        return self.fresh + self.cached + self.written

    @property
    def hit(self) -> bool:
        return self.cached > 0


@dataclass
class Family:
    """One prefix, sent several times with different tails."""

    name: str
    prefix_tokens: int
    calls: list[Call] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """What this family measured. Aggregate, because per-call is noise.

        ``ratio`` is over the *prompt* total rather than over the prefix, so it
        answers the question somebody actually has — what share of what we send
        are we not paying full price for — rather than a share of a number the
        provider never reports.
        """
        prompt = sum(call.prompt for call in self.calls)
        return {
            "prefix_tokens": self.prefix_tokens,
            "calls": len(self.calls),
            "failed": sum(1 for call in self.calls if call.error),
            "hits": sum(1 for call in self.calls if call.hit),
            "fresh_tokens": sum(call.fresh for call in self.calls),
            "cached_read_tokens": sum(call.cached for call in self.calls),
            "cache_write_tokens": sum(call.written for call in self.calls),
            "prompt_tokens": prompt,
            "cached_ratio": (
                sum(call.cached for call in self.calls) / prompt if prompt else 0.0
            ),
        }


def summarise(families: list[Family]) -> dict[str, Any]:
    """Every family, and the one verdict this probe is allowed to reach.

    The verdict is a single boolean about the *total*: did anything at all come
    back cached. Not a threshold, and not per call — see the module docstring.
    A run whose provider reported no usage counters at all reports ``False`` and
    zero everywhere, which is the honest shape: "we cannot tell" and "it does
    not cache" look the same from here, and the report says which by carrying
    the failure count beside it.
    """
    per_family = {family.name: family.summary() for family in families}
    totals = {
        key: sum(item[key] for item in per_family.values())
        for key in (
            "calls",
            "failed",
            "hits",
            "fresh_tokens",
            "cached_read_tokens",
            "cache_write_tokens",
            "prompt_tokens",
        )
    }
    totals["cached_ratio"] = (
        totals["cached_read_tokens"] / totals["prompt_tokens"]
        if totals["prompt_tokens"]
        else 0.0
    )
    return {
        "families": per_family,
        "totals": totals,
        "cache_is_reading": totals["cached_read_tokens"] > 0,
    }


# -- building the two prefixes production actually sends --------------------


def _tools() -> tuple[Any, ...]:
    """The twelve schemas the chat lane offers, unchanged.

    In the request because they are in the *head* of it: the schemas travel
    ahead of the conversation, in the same stable region the prompt occupies,
    which is why ``prompt.cache_key`` has taken a tool-surface digest since it
    was written. A probe sending no tools would measure a prefix five thousand
    tokens shorter than the one production sends, and a provider with a minimum
    cacheable length would answer a different question.
    """
    from src.agent.definitions import resolve_tool_surface
    from src.agent.toolsets import CHAT_TOOLSETS

    return tuple(resolve_tool_surface(CHAT_TOOLSETS).offered_schemas)


def _messages(body: bool, question: str) -> tuple[Any, ...]:
    """The real constructed context, with and without the pack body.

    Through ``build_messages`` rather than by hand, so the blocks, their order
    and their breakpoints are the ones the loop sends. A probe that assembled
    its own system message would be measuring a prefix nothing else uses.
    """
    from src.agent.domain import active_pack
    from src.agent.messages import Transcript, TranscriptTurn, build_messages
    from src.agent.prompt import RuntimeContext, prefix as prompt_prefix, render

    context = build_messages(
        Transcript(
            system_prompt=render(RuntimeContext(today=date.today())),
            system_prefix=prompt_prefix(),
            system_body=active_pack().body_text if body else None,
            turns=(TranscriptTurn(user_text=question),),
        )
    )
    return context.messages


def _prefix_tokens(body: bool) -> int:
    """What the stable head of this family is worth, by the harness's estimate."""
    from src.agent.messages import estimate_tokens

    system = _messages(body, QUESTIONS[0])[0]
    return estimate_tokens(system)


def _identity() -> str:
    """The harness's own name for the head being measured.

    A hash and a version, never the prose: this string lands in a report, and a
    report is not a place to reprint the system prompt.
    """
    from src.agent.definitions import resolve_tool_surface
    from src.agent.domain import active_pack
    from src.agent.prompt import cache_key
    from src.agent.toolsets import CHAT_TOOLSETS

    config = llm_config_from_settings()
    return cache_key(
        config.model_for(Workload.SESSION),
        resolve_tool_surface(CHAT_TOOLSETS).identity_digest,
        active_pack().identity,
    )


# -- the run ----------------------------------------------------------------


async def _one(config: Any, family: str, index: int, body: bool) -> Call:
    call = Call(family=family, index=index)
    client = build_client(config)
    try:
        completion: Completion = await client.complete(
            CompletionRequest(
                model=config.model_for(Workload.SESSION),
                messages=_messages(body, QUESTIONS[index % len(QUESTIONS)]),
                tools=_tools(),
                # Nothing may be called. The question is what the *head* costs
                # on the second reading of it, and a tool call would end the
                # measurement in a round of work nobody asked for.
                tool_choice="none",
                max_output_tokens=PROBE_OUTPUT_TOKENS,
                # Local to this process; the transport does not put it on the
                # wire. Recorded so a trace can say which head was measured.
                metadata={"probe": "prompt_cache", "family": family},
            ),
            SpendRequest(
                owner=CallOwner(
                    OwnerType.CAPABILITY_PROBE, f"prompt-cache:{family}:{index}"
                ),
                lane=BudgetLane.EMERGENCY,
                workload=Workload.SESSION,
                input_tokens=_prefix_tokens(body) + 64,
                output_tokens=PROBE_OUTPUT_TOKENS,
            ),
        )
        call.usage = completion.usage
    except Exception as exc:  # noqa: BLE001 - the report says what went wrong
        call.error = f"{type(exc).__name__}: {exc}"
    finally:
        await client.aclose()
    return call


def probe_charged_today() -> int:
    """What the Capability Probe lane has spent since midnight ICT.

    The same window ``admission`` counts, computed the same way, because a probe
    that guessed at the boundary would refuse a run that would have fitted or
    start one that will not.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func, select

    from src.alpha.models import LlmCallUsage
    from src.core.database import sync_session_factory
    from src.core.llm.admission import ICT

    now = datetime.now(ICT)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with sync_session_factory() as session:
        charged = session.execute(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            LlmCallUsage.actual_micro_usd,
                            LlmCallUsage.reserved_micro_usd,
                        )
                    ),
                    0,
                )
            ).where(
                LlmCallUsage.owner_type == OwnerType.CAPABILITY_PROBE.value,
                LlmCallUsage.provider_called_at >= day_start,
                LlmCallUsage.provider_called_at < day_start + timedelta(days=1),
            )
        ).scalar_one()
    return int(charged)


def _estimated_micro(config: Any) -> int:
    """What one call of this probe reserves, priced the way admission prices it.

    Through ``admission``'s own pricing rather than a rule of thumb: what the
    allowance check below compares against has to be the number the allowance
    check *inside* the client will compute, or this refuses runs that would have
    fitted and starts runs that will not.
    """
    from src.core.llm.admission import _micro_usd
    from src.core.llm.config import TokenPrices

    prices = config.prices_for(Workload.SESSION)
    return _micro_usd(
        TokenPrices(
            input=prices.worst_case_input,
            cached_input=prices.cached_input,
            cache_write=prices.cache_write,
            output=prices.output,
        ),
        input_tokens=_prefix_tokens(body=True) + 64,
        output_tokens=PROBE_OUTPUT_TOKENS,
    )


def ledger_totals(owner_prefix: str = "prompt-cache:") -> dict[str, int]:
    """What ``llm_call_usage`` says this probe's calls cost.

    Read back rather than trusted from the completions, because the two are
    different records and a discrepancy between them is the finding: the ledger
    is what the envelope is spent against, and a probe reporting a saving the
    ledger never saw would be reporting on nothing.
    """
    from sqlalchemy import func, select

    from src.alpha.models import LlmCallUsage
    from src.core.database import sync_session_factory

    with sync_session_factory() as session:
        row = session.execute(
            select(
                func.coalesce(func.sum(LlmCallUsage.input_tokens), 0),
                func.coalesce(func.sum(LlmCallUsage.cached_read_tokens), 0),
                func.coalesce(func.sum(LlmCallUsage.cache_write_tokens), 0),
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            LlmCallUsage.actual_micro_usd,
                            LlmCallUsage.reserved_micro_usd,
                        )
                    ),
                    0,
                ),
                func.count(),
            ).where(
                LlmCallUsage.owner_type == OwnerType.CAPABILITY_PROBE.value,
                LlmCallUsage.owner_id.like(f"{owner_prefix}%"),
            )
        ).one()
    return {
        "fresh_tokens": int(row[0]),
        "cached_read_tokens": int(row[1]),
        "cache_write_tokens": int(row[2]),
        "micro_usd": int(row[3]),
        "rows": int(row[4]),
    }


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.probe_prompt_cache")
    parser.add_argument(
        "--ceiling-usd",
        type=float,
        required=True,
        help="hard spend ceiling; this probe refuses to start without one",
    )
    parser.add_argument("--calls", type=int, default=CALLS_PER_FAMILY)
    args = parser.parse_args(argv)
    if args.ceiling_usd <= 0:
        print("--ceiling-usd must be positive", file=sys.stderr)
        return 2

    config = llm_config_from_settings()
    if not config.route.base_url:
        print("no route configured — set LLM_BASE_URL and LLM_API_KEY", file=sys.stderr)
        return 2

    ceiling_micro = int(args.ceiling_usd * 1_000_000)

    # The other ceiling, and it is not this script's. ``PROBE_DAILY_MICRO_USD``
    # is a contract constant shared with the boot-time Capability Probe, so a
    # measurement started on an exhausted allowance does not merely fail — it
    # produces a report full of refusals that reads like a route that stopped
    # caching. Checked up front and named, rather than discovered one call at a
    # time.
    headroom = PROBE_DAILY_MICRO_USD - probe_charged_today()
    needed = 2 * args.calls * _estimated_micro(config)
    if headroom < needed:
        print(
            "the Capability Probe allowance for today is down to "
            f"{headroom} µUSD and this run needs about {needed}. "
            "It resets at midnight Asia/Ho_Chi_Minh. Nothing was sent.",
            file=sys.stderr,
        )
        return 3

    before = ledger_totals()
    families = [
        Family("core", _prefix_tokens(body=False)),
        Family("core+domain-body", _prefix_tokens(body=True)),
    ]
    stopped = ""
    for family, body in zip(families, (False, True), strict=True):
        for index in range(args.calls):
            spent = ledger_totals()["micro_usd"] - before["micro_usd"]
            if spent >= ceiling_micro:
                stopped = f"ceiling reached after {spent} µUSD"
                break
            call = await _one(config, family.name, index, body)
            family.calls.append(call)
            mark = "hit " if call.hit else "miss"
            print(
                f"[{mark}] {family.name} #{index}: "
                f"fresh={call.fresh} cached={call.cached} written={call.written}"
                + (f"  {call.error}" if call.error else "")
            )
        if stopped:
            break

    report = summarise(families)
    after = ledger_totals()
    report["ledger"] = {
        key: after[key] - before[key] for key in ("fresh_tokens", "cached_read_tokens", "cache_write_tokens", "micro_usd", "rows")
    }
    report["stopped"] = stopped
    report["model"] = config.model_for(Workload.SESSION)
    report["prompt_cache_control"] = config.route.prompt_cache_control
    report["identity"] = _identity()

    totals = report["totals"]
    print(
        f"\naggregate: fresh={totals['fresh_tokens']} "
        f"cached={totals['cached_read_tokens']} "
        f"written={totals['cache_write_tokens']} "
        f"ratio={totals['cached_ratio']:.1%} "
        f"hits={totals['hits']}/{totals['calls']}"
    )
    _write_report(report)
    return 0 if report["cache_is_reading"] and not totals["failed"] else 1


def _write_report(report: dict[str, Any]) -> None:
    path = REPORTS / f"probe-{date.today():%y%m%d}-prompt-cache.md"
    totals = report["totals"]
    ledger = report["ledger"]
    lines = [
        "# Probe: prefix cache tự động của route, trên đúng cái đầu C2 dựng",
        "",
        f"- Ngày chạy: {date.today().isoformat()}",
        f"- Model: `{report['model']}`",
        f"- `prompt_cache_control`: **{report['prompt_cache_control']}**",
        f"- Danh tính cái đầu: `{report['identity']}`",
        "",
        "| Prefix | Token prefix | Lượt | Hit | Fresh | Cached read | Cache write | Tỷ lệ cached |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in report["families"].items():
        lines.append(
            f"| `{name}` | {item['prefix_tokens']:,} | {item['calls']} | "
            f"{item['hits']} | {item['fresh_tokens']:,} | "
            f"{item['cached_read_tokens']:,} | {item['cache_write_tokens']:,} | "
            f"{item['cached_ratio']:.1%} |"
        )
    lines += [
        f"| **tổng** | | {totals['calls']} | {totals['hits']} | "
        f"{totals['fresh_tokens']:,} | {totals['cached_read_tokens']:,} | "
        f"{totals['cache_write_tokens']:,} | {totals['cached_ratio']:.1%} |",
        "",
        "## Đối chiếu ledger",
        "",
        "| | Provider nói | `llm_call_usage` ghi |",
        "|---|---:|---:|",
        f"| Fresh | {totals['fresh_tokens']:,} | {ledger['fresh_tokens']:,} |",
        f"| Cached read | {totals['cached_read_tokens']:,} | {ledger['cached_read_tokens']:,} |",
        f"| Cache write | {totals['cache_write_tokens']:,} | {ledger['cache_write_tokens']:,} |",
        f"| Số dòng | {totals['calls']} | {ledger['rows']} |",
        "",
        f"Chi phí probe: **{ledger['micro_usd']:,} µUSD**.",
        "",
        "## Đọc thế nào",
        "",
        "Đơn vị là **tổng**, không phải từng lượt. Đo 2026-08-23 trên chính route",
        "này ghi nhận load balancer phục vụ 3 hit trên 8 lượt cùng một prefix, nên",
        "một lượt miss không nói được gì; một tổng bằng không thì có.",
        "",
        f"Verdict: cache **{'đang đọc' if report['cache_is_reading'] else 'không đọc'}**"
        + (f" — dừng sớm: {report['stopped']}" if report["stopped"] else "")
        + ".",
        "",
        "Không sửa cờ nào từ script này. `llm_prompt_cache_control_enabled` là một",
        "quyết định đã kiểm chứng và một phép đo không đảo nó — nó chỉ nói phép đo",
        "cũ còn đúng hay không trên cái đầu mới.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport → {path}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))
