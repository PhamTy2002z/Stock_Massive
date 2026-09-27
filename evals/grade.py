"""Automatic checks for one round of selftest Turns, written independently of agent/evidence/grounding.py.

    apps/api/.venv/bin/python evals/grade.py evals/runs/r1            # table + evals/runs/r1/_auto.json
    apps/api/.venv/bin/python evals/grade.py evals/runs/r1 --verify   # also cross-check prices with VCI

Checks, per Turn (each returns pass/fail plus the evidence it saw):
  numbers  every figure in the answer is printed in this Turn's tool output (unit scale, rounding)
  year     date arguments and web-search years belong to the current year (or one the question names)
  dated    every figure carries a dated source marker; nothing marked stale; "current" prices are recent
  ledger   a claim ledger was written and the verifier recorded an outcome
  tools    no tool call failed on bad arguments; every ticker in the arguments exists
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

TODAY = date.today()
STALE_DAYS = 7  # a "current" price older than this many calendar days fails `dated`
ROOT = Path(__file__).resolve().parent.parent

LABEL = re.compile(r"\s?\[(\d{1,3} · [^\]\n]{1,80}|chưa kiểm chứng)\]")
MASKS = [
    re.compile(r"\b\d{1,2}\s*[-–]\s*\d{1,2}/\d{1,2}(?:/\d{4})?\b"),  # 21-25/9/2026
    re.compile(r"\b\d+/\d{4}/[A-ZĐ][A-ZĐ0-9-]*"),  # document numbers: 96/2025/QH15
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),  # dd/mm/yyyy
    re.compile(r"\b\d{1,2}/\d{4}\b"),  # mm/yyyy, "đợt 1/2026"
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"(?i)\b(?:quý|q)\s*[1-4]\s*/\s*\d{4}\b"),
    re.compile(r"(?i)\b(?:năm|tháng|quý|kỳ|giai đoạn|nq|fy)\s*\d{1,4}(?:\s*[/-]\s*\d{1,4})?\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}\b"),  # dd/mm
    re.compile(r"(?<![\d.,])(?:19|20)\d{2}(?![\d.,%])"),  # bare years
    re.compile(r"(?m)^\s*\d{1,2}[.)]\s"),  # list numbering
    re.compile(r"\b[A-Z]{1,6}\d+[A-Z0-9]*\b"),  # VN30, VN-Index-like codes
    re.compile(r"(?i)\b\d+\s*(?:tháng|ngày|tuần|phiên|quý|năm|mã|nhóm|bước|lần gần nhất)\b"),  # counts/horizons
    re.compile(r"\[\d{1,3}\]"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),  # clock times
]
NUM = re.compile(r"(?<![\w.,])[-+−]?\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\d])|(?<![\w.,])[-+−]?\d+(?:[.,]\d+)?(?![\d])")


def load_result(result):
    """A tool result is {"text": "<json>"}; return the parsed body when it parses."""
    if isinstance(result, dict) and isinstance(result.get("text"), str):
        try:
            return json.loads(result["text"], strict=False)
        except ValueError:
            return result["text"]
    return result


def vn_number(tok: str) -> tuple[float, int]:
    """Value and decimals of a number written the Vietnamese way (dot thousands, comma decimals)."""
    tok = tok.replace("−", "-").lstrip("+")
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?", tok):
        ip, _, dp = tok.replace(".", "").partition(",")
    elif "," in tok:
        ip, _, dp = tok.partition(",")
    elif "." in tok:  # 4.99 written English style
        ip, _, dp = tok.partition(".")
    else:
        ip, dp = tok, ""
    return float(f"{ip}.{dp}" if dp else ip), len(dp)


def source_numbers(obj, out: set[float]) -> set[float]:
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            source_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            source_numbers(v, out)
    elif isinstance(obj, str):
        for m in re.finditer(r"\d[\d.,]*\d|\d", obj):
            t = m.group(0)
            for cand in {t.replace(",", ""), t.replace(".", "").replace(",", ".")}:
                try:
                    out.add(float(cand))
                except ValueError:
                    pass
    return out


SCALES = (1, 1e3, 1e6, 1e9, 1e12, 1e-3, 1e-6, 1e-9, 1e-12, 100, 0.01)


def matches(value: float, decimals: int, pool: set[float]) -> bool:
    step = 10 ** -decimals
    for s in pool:
        for k in SCALES:
            v = s * k
            for cand in (v, abs(v)):
                # rounded to the written precision, or truncated to it
                if abs(round(cand, decimals) - abs(value)) < step / 2 or (0 <= abs(value) - int(cand / step) * step < step / 2 and cand > 0):
                    if abs(value) != 0 or cand == 0:
                        return True
    return False


def answer_body(text: str) -> str:
    return re.split(r"\n-{3,}\s*\n+\*\*Nguồn số liệu\*\*", text)[0]


def figures(text: str, question: str):
    """(token, value, decimals, label, line) for each figure; label is the marker right after it."""
    q_values = {vn_number(t)[0] for t in NUM.findall(question)}
    out = []
    for line in answer_body(text).splitlines():
        # attach each label to the figure just before it, then mask dates/years/labels
        work = line
        for rx in [LABEL] + MASKS:
            work = rx.sub(lambda m: " " * len(m.group(0)), work)
        for m in NUM.finditer(work):
            tok = m.group(0)
            value, dec = vn_number(tok)
            if value in q_values or (abs(value) < 10 and dec == 0 and not re.match(r"\s*(%|lần|x\b|đồng|tỷ|triệu|nghìn|điểm)", work[m.end():])):
                continue  # the reader's own numbers, and bare small integers (counts, ranks)
            tail = line[m.end(): m.end() + 60]
            lab = LABEL.search(tail)
            label = lab.group(1) if lab and not NUM.search(re.sub(r"\s?\[[^\]]*\]", "", tail[: lab.start()])) else None
            out.append((tok, value, dec, label, line.strip()[:160]))
    return out


QEND = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
PERIOD = re.compile(r"(?i)\b(?:q|quý)\s*([1-4])\s*/\s*(\d{4})\b")


def period_end(cell: str) -> date | None:
    m = PERIOD.search(cell)
    if m:
        mo, d = QEND[int(m.group(1))]
        return date(int(m.group(2)), mo, d)
    return None


def period_mismatches(text: str) -> list[str]:
    """A table cell whose column or row names a quarter, cited to a source of another period."""
    out = []
    header: list[str] | None = None
    for line in answer_body(text).splitlines():
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        row_p = period_end(cells[0]) if cells else None
        for i, cell in enumerate(cells[1:], 1):
            want = row_p or (period_end(header[i]) if i < len(header) else None)
            if not want:
                continue
            for lab in LABEL.finditer(cell):
                m = re.search(r"kỳ đến (\d{2})/(\d{2})/(\d{4})", lab.group(1))
                if m and date(int(m.group(3)), int(m.group(2)), int(m.group(1))) != want:
                    out.append(f"{cells[0]} | {header[i] if i < len(header) else '?'}: {cell[:70]}")
    return out


def label_date(label: str | None) -> date | None:
    if not label:
        return None
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", label)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def check(turn: dict) -> dict:
    q = turn["question"]["text"]
    resp = turn.get("response") or {}
    text = resp.get("answer") or resp.get("text") or ""  # what the reader is shown; narration rides in thoughts
    calls = turn.get("tool_calls") or []
    pool: set[float] = set()
    for c in calls:
        source_numbers(load_result(c.get("result")), pool)
    lane = next((p["payload"]["lane"] for p in resp.get("progress", []) if p["kind"] == "lane_selected"), None)
    figs = figures(text, q)
    r = {"turn": turn["turn"]["id"], "status": turn["turn"]["status"], "reason": turn["turn"]["terminal_reason"], "lane": lane, "tool_names": [c["tool_name"] for c in calls], "n_figures": len(figs)}

    # numbers
    bad = [f"{t} ({line})" for t, v, d, lab, line in figs if not matches(v, d, pool)]
    unv = [f"{t} ({line})" for t, v, d, lab, line in figs if lab == "chưa kiểm chứng"]
    wrong_period = period_mismatches(text)
    r["numbers"] = {"pass": bool(text) and not bad and not unv and not wrong_period, "not_in_tools": bad[:8], "labelled_unverified": unv[:8], "wrong_period": wrong_period[:8]}

    # year
    years_q = {int(y) for y in re.findall(r"\b(20\d{2})\b", q)}
    ok_years = {TODAY.year} | years_q
    wrong = []
    blocked = []  # wrong-year calls the harness refused before dispatch: the model erred, the system held
    for c in calls:
        a = c.get("arguments") or {}
        if c["status"] != "ok" and "blocked" in str(c.get("error") or ""):
            sink = blocked
        else:
            sink = wrong
        for k, v in a.items():
            if not isinstance(v, str):
                continue
            if k in ("query", "q") or c["tool_name"] == "web_search":
                bare = re.sub(r"\b\d+/20\d{2}/[A-ZĐ][A-ZĐ0-9-]*", "", v)  # a law or decision number is not a date
                sink += [f"{c['tool_name']}.{k}={v!r}" for y in re.findall(r"\b(20\d{2})\b", bare) if int(y) not in ok_years]
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                d = date.fromisoformat(v)
                if d > TODAY + timedelta(days=1) or (k in ("end", "to", "end_date") and d.year < TODAY.year and d.year not in years_q):
                    sink.append(f"{c['tool_name']}.{k}={v}")

    # dated
    undated = [f"{t} ({line})" for t, v, d, lab, line in figs if lab is None or lab == "chưa kiểm chứng" or "không rõ ngày" in lab]
    # the answer's own prose naming a wrong year ("tuần 21-25/9/2025") is a year error too
    blob = json.dumps([load_result(c.get("result")) for c in calls], ensure_ascii=False, default=str)
    seen = {(int(d), int(mo), int(y)) for y, mo, d in re.findall(r"(20\d{2})-(\d{2})-(\d{2})", blob)}
    seen |= {(int(d), int(mo), int(y)) for d, mo, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", blob)}
    for m in re.finditer(r"\b(?:\d{1,2}\s*[-–]\s*)?(\d{1,2})/(\d{1,2})/(20\d{2})\b", answer_body(text)):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y not in ok_years and (d, mo, y) not in seen:
            wrong.append(f"answer: {m.group(0)}")
    stale_marked = "nguồn cũ" in text
    sessions = [label_date(lab) for _, _, _, lab, _ in figs if lab and lab.split(" · ", 1)[-1].startswith("phiên")]
    sessions = [s for s in sessions if s]
    current_q = bool(re.search(r"(?i)hôm nay|hiện tại|bây giờ|lúc này|gần nhất|mới nhất|\?$", q))
    latest = max(sessions) if sessions else None
    old_current = bool(current_q and latest and (TODAY - latest).days > STALE_DAYS)
    r["year"] = {"pass": not wrong, "wrong": wrong[:8], "blocked_by_harness": blocked[:8]}
    r["dated"] = {"pass": bool(text) and not undated and not stale_marked and not old_current, "undated": undated[:8], "stale_marked": stale_marked, "latest_session": str(latest) if latest else None}

    # ledger + verifier
    led = turn.get("ledger")
    vo = (led or {}).get("payload", {}).get("verifierOutcome")
    r["ledger"] = {"pass": bool(led) and vo not in (None, "verifier_failed"), "ledger": bool(led), "verifierOutcome": vo, "claims": len((led or {}).get("payload", {}).get("claims", [])), "gaps": (led or {}).get("payload", {}).get("gaps", [])[:6], "trajectory": turn.get("trajectory_stages")}

    # tools
    errs = [f"{c['tool_name']}: {c['status']} {str(c.get('error') or '')[:120]}" for c in calls if c["status"] not in ("ok", "success", "completed")]
    arg_err = [e for e in errs if re.search(r"(?i)invalid|schema|argument|validation|unknown", e)]
    syms = sorted({v.upper() for c in calls for k, v in (c.get("arguments") or {}).items() if k in ("symbol", "ticker") and isinstance(v, str)} | {s.upper() for c in calls for k, v in (c.get("arguments") or {}).items() if k in ("symbols", "tickers") and isinstance(v, list) for s in v if isinstance(s, str)})
    r["tools"] = {"errors": errs, "arg_errors": arg_err, "symbols": syms}
    if not calls and not figs:  # nothing read, nothing stated: no evidence either way
        for k in ("numbers", "year", "dated"):
            r[k]["pass"] = False
            r[k]["no_evidence"] = "không gọi tool, không nêu số — không có bằng chứng"
    if r["status"] != "complete":  # a Turn that never answered passes nothing
        for k in ("numbers", "year", "dated", "ledger"):
            r[k]["pass"] = False
    return r


def known_symbols(syms: list[str]) -> set[str]:
    if not syms:
        return set()
    lst = ",".join(f"'{s}'" for s in syms if re.fullmatch(r"[A-Z0-9]{2,10}", s))
    out = subprocess.run(["docker", "compose", "exec", "-T", "db", "psql", "-U", "postgres", "-d", "stockmassive", "-At", "-c", f"select distinct symbol from listing_roster where symbol in ({lst})"], cwd=ROOT, capture_output=True, text=True).stdout
    return set(out.split()) | {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX", "VN100"}


def verify_prices(turn: dict) -> list[str]:
    """Cross-check each market read's latest close against VCI, a source the Agent did not use."""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        from vnstock import Quote

    notes = []
    for c in turn.get("tool_calls") or []:
        if c["tool_name"] != "get_market_data":
            continue
        body = load_result(c.get("result"))
        if not isinstance(body, dict) or not body.get("latest"):
            continue
        sym, lt = body["symbol"], body["latest"]
        d = lt["session_date"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                df = Quote(symbol=sym, source="VCI").history(start=(date.fromisoformat(d) - timedelta(days=7)).isoformat(), end=d, interval="1D")
            row = df[df["time"].astype(str).str.startswith(d)].iloc[-1]
            vci = float(row["close"]) * (1000 if float(row["close"]) < 1000 and sym not in ("VNINDEX", "VN30", "HNXINDEX") else 1)
            ok = abs(vci - lt["close"]) <= max(1, 0.001 * vci)
            notes.append(f"{sym} {d}: tool={lt['close']} VCI={vci:g} {'khớp' if ok else 'LỆCH'}")
        except Exception as e:  # noqa: BLE001 — a verification miss is reported, not fatal
            notes.append(f"{sym} {d}: VCI lỗi {type(e).__name__}: {str(e)[:80]}")
    return notes


def main(run_dir: str, verify: bool) -> None:
    rows = []
    for p in sorted(q for q in Path(run_dir).glob("[AN]*.json") if ".full." not in q.name):
        # the trace keeps only the preview the model saw; refetch_tools.py recovers the whole result
        full = p.with_name(p.stem + ".full.json")
        turn = json.loads((full if full.exists() else p).read_text())
        r = check(turn)
        r["id"], r["kind"], r["question"] = p.stem, turn["meta"]["kind"], turn["meta"]["text"]
        rows.append(r)
    allsyms = sorted({s for r in rows for s in r["tools"]["symbols"]})
    known = known_symbols(allsyms)
    for r in rows:
        unknown = [s for s in r["tools"]["symbols"] if s not in known]
        r["tools"]["unknown_symbols"] = unknown
        r["tools"]["pass"] = r["status"] == "complete" and bool(r["tool_names"]) and not r["tools"]["arg_errors"] and not unknown
        if verify:
            r["verify"] = verify_prices(json.loads((Path(run_dir) / f"{r['id']}.json").read_text()))
    Path(run_dir, "_auto.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for r in rows:
        flags = " ".join(f"{k}={'Đ' if r[k]['pass'] else 'K'}" for k in ("numbers", "year", "dated", "ledger", "tools"))
        print(f"{r['id']} {r['lane']} {r['status']}/{r['reason']} figs={r['n_figures']} {flags} tools={','.join(r['tool_names'])}")
        for k in ("numbers", "year", "dated", "ledger", "tools"):
            if not r[k]["pass"]:
                print(f"   {k}: {json.dumps({x: y for x, y in r[k].items() if x != 'pass' and y}, ensure_ascii=False)[:600]}")
        if r.get("verify"):
            print("   verify:", "; ".join(r["verify"]))


if __name__ == "__main__":
    main(sys.argv[1], "--verify" in sys.argv)
