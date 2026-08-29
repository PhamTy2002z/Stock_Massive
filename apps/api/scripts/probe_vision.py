"""Does the configured route actually read an image, through the real serializer.

This is the blocking gate of ``plans/260829-0010-composer-attachments``. It
answers one question — can the model see pixels we send — and it answers it the
only way that is worth anything: by building a real :class:`Message` carrying a
real :class:`ImageContent` and letting ``as_wire`` and
``_mark_tail_breakpoints`` shape the request, exactly as production would.

**Why not a hand-built payload.** Two functions stand between a content part and
the wire: ``Message.as_wire`` decides block order and list shape, and
``_mark_tail_breakpoints`` decides where ``cache_control`` lands. A probe that
skipped them would prove something about a payload nobody sends. There is
precedent in this repo for the failure that follows: ``JsonSchemaFormat`` records
a gateway measured *silently dropping* ``response_format``.

**Why not a sixth Capability Probe check.** ``enforce_capability_probe`` raises
when any check fails and Alpha Desk is enabled, and ``ProbeResult.ok`` is an
``all(...)`` with no advisory tier — so a route that cannot read images would
stop the API from booting. Reading images is a side capability; it does not get
to kill the product. It also already costs five real calls per restart.

**Why the answer cannot be guessed.** The image carries four digits drawn at
run time. A model that describes the picture in general terms, or hedges, fails.
"Probably it sees it" is not a result.

Run by hand. It spends real model calls, so it is not in the suite and not in CI.

    make probe-vision            # or: python -m scripts.probe_vision

Writes ``plans/reports/probe-<date>-vision-route.md`` with the verbatim answers
and, the number the rest of the plan depends on, ``usage.input_tokens`` for one
image and for two — two points are enough to separate the per-image cost from
the fixed part of the request.
"""

from __future__ import annotations

import asyncio
import base64
import random
import struct
import sys
import zlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.core.llm import (
    BudgetLane,
    CallOwner,
    Completion,
    CompletionRequest,
    ImageContent,
    Message,
    OwnerType,
    Role,
    SpendRequest,
    Workload,
    build_client,
    llm_config_from_settings,
)
from src.core.llm.config import LLMConfig, LLMRoute
from src.core.llm.probe import PROBE_INPUT_TOKENS, PROBE_OUTPUT_TOKENS

def _reports_dir() -> Path:
    """``plans/reports`` at the repo root, wherever this file happens to sit.

    It runs from the host checkout and from inside the api container, and those
    are different depths — so the directory is found by walking up rather than
    by counting parents.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "plans" / "reports"
        if candidate.is_dir():
            return candidate
    return here.parent


REPORTS = _reports_dir()

#: The six the secret is drawn from. Solid colour is the one signal measured to
#: survive this route intact — see the note on ``_swatches``.
COLOURS = {
    "red": (220, 30, 30),
    "green": (30, 170, 60),
    "blue": (30, 60, 220),
    "yellow": (240, 220, 40),
    "magenta": (220, 40, 200),
    "cyan": (40, 210, 220),
}

#: Roughly what a screenshot is after a browser downscales it, so the token cost
#: measured here is the token cost the product will actually pay.
WIDTH = 1_024
HEIGHT = 768


def _swatches(names: tuple[str, ...]) -> bytes:
    """Vertical bands of named colour, as a PNG, with only the standard library.

    **Why colour and not text.** The first version of this probe drew digits in
    a hand-rolled 3x5 pixel font. The image was valid and legible to a human,
    and the model reported "a completely blank white image" and then invented
    digits — the same answer it gives with no image at all. Re-saving the very
    same picture through Pillow changed nothing, so it was the glyphs, not the
    encoder. Meanwhile the model read real antialiased text ("2662") exactly and
    named a random solid colour exactly. So the signal here is one this route was
    measured to carry, rather than one that looked like a good test on paper.

    Pillow would give real text, but it is not in ``requirements.txt`` — it
    arrives as matplotlib's transitive dependency, and a gate that quietly rests
    on one is a gate that stops running the day that dependency moves.

    Bands rather than a single fill on purpose: reading them left to right in
    order is a claim about *where* things are, which a model that merely knows
    "an image was attached" cannot make. Three bands from six colours is one
    answer in 216.
    """
    band = WIDTH // len(names)
    row = bytearray()
    for index in range(WIDTH):
        red, green, blue = COLOURS[names[min(index // band, len(names) - 1)]]
        row += bytes((red, green, blue))
    raw = b"".join(b"\x00" + bytes(row) for _ in range(HEIGHT))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _secret() -> tuple[str, ...]:
    """Three colours drawn at run time, order included."""
    return tuple(random.sample(sorted(COLOURS), 3))


def _image(names: tuple[str, ...], filename: str) -> ImageContent:
    return ImageContent(
        media_type="image/png",
        data=base64.b64encode(_swatches(names)).decode("ascii"),
        placeholder=f"[ảnh: {filename}]",
    )


@dataclass
class Run:
    label: str
    #: One tuple of colour names per image, in the order the bands are drawn.
    secret: tuple[tuple[str, ...], ...]
    completion: Completion | None = None
    error: str = ""

    @property
    def expected(self) -> str:
        # Not "|": this string lands in a Markdown table cell.
        return " · ".join(" ".join(names) for names in self.secret)

    @property
    def passed(self) -> bool:
        """Every band of every image, named in the order it was drawn.

        Order matters: a model that knows an image was attached without reading
        it can still land on three colour words. Landing on them in the right
        sequence, twice over when there are two images, is not something the
        question affords.
        """
        if self.completion is None:
            return False
        answer = (self.completion.text or "").lower()
        cursor = 0
        for names in self.secret:
            for name in names:
                found = answer.find(name, cursor)
                if found < 0:
                    return False
                cursor = found + len(name)
        return True

    @property
    def input_tokens(self) -> int:
        usage = self.completion.usage if self.completion else None
        return usage.input_tokens if usage else 0

    def render(self) -> str:
        if self.completion is None:
            return f"<no completion: {self.error}>"
        return repr(
            {
                "text": self.completion.text,
                "finish_reason": self.completion.finish_reason,
                "usage.input_tokens": self.input_tokens,
            }
        )


def _request(
    model: str, secret: tuple[tuple[str, ...], ...]
) -> CompletionRequest:
    """One question, and the images that answer it.

    The message names each image in its own text, which is the invariant
    ``Message`` enforces: the string a ledger measures has to narrate the whole
    prompt the route reads.
    """
    images = tuple(
        _image(names, f"anh-{index + 1}.png") for index, names in enumerate(secret)
    )
    named = " ".join(image.placeholder for image in images)
    return CompletionRequest(
        model=model,
        messages=(
            Message(
                role=Role.SYSTEM,
                content=(
                    "You read images. Each picture is vertical colour bands. "
                    "Name the bands left to right, lowercase, space separated, "
                    "one line per picture. Nothing else."
                ),
            ),
            Message(
                role=Role.USER,
                content=f"What colours are the bands, left to right? {named}",
                images=images,
            ),
        ),
        max_output_tokens=64,
        metadata={"probe": "vision"},
    )


async def _call(
    config: LLMConfig, run: Run, secret: tuple[tuple[str, ...], ...]
) -> Run:
    client = build_client(config)
    try:
        run.completion = await client.complete(
            _request(config.model_for(Workload.SESSION), secret),
            SpendRequest(
                owner=CallOwner(OwnerType.CAPABILITY_PROBE, f"vision:{run.label}"),
                lane=BudgetLane.EMERGENCY,
                workload=Workload.SESSION,
                input_tokens=PROBE_INPUT_TOKENS,
                output_tokens=PROBE_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - the report says what went wrong
        run.error = f"{type(exc).__name__}: {exc}"
    finally:
        await client.aclose()
    return run


def _with_cache_control(config: LLMConfig, enabled: bool) -> LLMConfig:
    route = config.route
    if route.prompt_cache_control == enabled:
        return config
    from dataclasses import replace

    return replace(config, route=replace(route, prompt_cache_control=enabled))


async def main() -> int:
    config = llm_config_from_settings()
    if not config.route.base_url:
        print("no route configured — set LLM_BASE_URL and LLM_API_KEY", file=sys.stderr)
        return 2

    one = (_secret(),)
    two = (_secret(), _secret())

    # Three calls. The first two are the same request under both cache settings:
    # the second is where ``_mark_tail_breakpoints`` could hang the marker on the
    # image block, which is the failure a unit test of ``as_wire`` cannot see.
    # The third differs from the first only by one image, so the difference in
    # ``input_tokens`` is what one image costs.
    runs = [
        await _call(_with_cache_control(config, False), Run("one-image", one), one),
        await _call(_with_cache_control(config, True), Run("cache-control", one), one),
        await _call(_with_cache_control(config, False), Run("two-images", two), two),
    ]

    for run in runs:
        mark = "PASS" if run.passed else "FAIL"
        print(f"[{mark}] {run.label}: expected {run.expected}")
        print(f"       {run.render()}")

    slope = runs[2].input_tokens - runs[0].input_tokens
    print(f"\ninput_tokens: one={runs[0].input_tokens} two={runs[2].input_tokens} → per image ≈ {slope}")

    _write_report(config.route, config.model_for(Workload.SESSION), runs, slope)
    return 0 if all(run.passed for run in runs) else 1


def _write_report(route: LLMRoute, model: str, runs: list[Run], slope: int) -> None:
    path = REPORTS / f"probe-{date.today():%y%m%d}-vision-route.md"
    lines = [
        "# Probe: does the route read images",
        "",
        f"- Ngày chạy: {date.today().isoformat()}",
        f"- Model: `{model}`",
        f"- Route: `{route.base_url}`",
        "",
        "| Lượt | `prompt_cache_control` | Dải màu chờ | Kết quả | `usage.input_tokens` |",
        "|---|---|---|---|---|",
    ]
    cache = {"one-image": "off", "cache-control": "on", "two-images": "off"}
    for run in runs:
        lines.append(
            f"| `{run.label}` | {cache[run.label]} | {run.expected} | "
            f"{'PASS' if run.passed else 'FAIL'} | {run.input_tokens} |"
        )
    lines += [
        "",
        f"Chi phí một ảnh ≈ **{slope}** token "
        "(hiệu `input_tokens` giữa lượt hai ảnh và lượt một ảnh, cùng cache off).",
        "Đây là số chốt `IMAGE_TOKENS` ở `core/llm/protocol.py` và trần",
        "bytes của phase 05.",
        "",
        "## Câu trả lời nguyên văn",
        "",
    ]
    for run in runs:
        lines += [f"### `{run.label}`", "", "```", run.render(), "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport → {path}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
