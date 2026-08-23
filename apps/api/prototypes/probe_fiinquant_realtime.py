"""PROTOTYPE — vứt đi sau khi đo xong. Không import từ src/.

Đo ba con số quyết định thiết kế Stream Worker, phải chạy TRONG GIỜ GIAO DỊCH
(09:00–15:00 giờ VN, ngày giao dịch). Ngoài giờ, hub nhận connection và join
group nhưng không đẩy tick nào, nên phép đo trả về 0 và không nói được gì.

  1. Tick rate mỗi mã — quyết định buffer và nhịp ghi Redis.
  2. Vòng reconnect có còn trong phiên hay không — ngoài giờ đã thấy server đóng
     bằng {"type":7,...} rồi client tự rejoin mỗi ~7s. Nếu điều đó cũng xảy ra
     trong phiên thì Stream Worker cần backoff và dedup theo timestamp; nếu
     không thì universe tĩnh là đủ và không cần gì thêm.
  3. Breadth có về khi subscribe index hay không — RealTimeData khai
     TotalStockUpPrice/Down/NoChange/OverCeiling/UnderFloor. Nếu index đẩy các
     field đó thì hệ thống bỏ được phần tự tính breadth.

Cần signalrcore < 1.0: 1.0.0 thêm validator bắt buộc "negotiateVersion" mà hub
FiinQuant không trả (requirements.txt đã pin >=0.9.5,<1.0.0).

Chạy trong container, vì signalrcore đã pin đúng ở image chứ không ở venv host —
và ``prototypes/`` không nằm trong các thư mục được mount, nên phải copy vào:

    docker compose cp apps/api/prototypes/probe_fiinquant_realtime.py \\
        api:/tmp/probe_realtime.py
    docker compose exec api python /tmp/probe_realtime.py --minutes 10

Kết quả JSON ghi cạnh script (tức /tmp trong container); lấy ra bằng
``docker compose cp api:/tmp/fiinquant_realtime_results.json .``
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from collections import Counter, defaultdict

# Mã đại diện đủ dải thanh khoản, cộng hai index để đo breadth.
TICKERS = ["STB", "FPT", "HPG", "MBB", "VCB", "SSI", "VNM", "MWG"]
INDICES = ["VNINDEX", "VN30"]

# Field breadth mà RealTimeData khai — đo xem chúng có thật sự về hay không.
BREADTH_FIELDS = (
    "TotalStockUpPrice",
    "TotalStockDownPrice",
    "TotalStockNoChangePrice",
    "TotalStockOverCeiling",
    "TotalStockUnderFloor",
)

parser = argparse.ArgumentParser()
parser.add_argument("--minutes", type=float, default=10.0, help="thời lượng đo")
args = parser.parse_args()

user = os.environ.get("FIINQUANT_USERNAME", "")
password = os.environ.get("FIINQUANT_PASSWORD", "")
if not user or not password:
    raise SystemExit("thiếu FIINQUANT_USERNAME / FIINQUANT_PASSWORD")

import certifi  # noqa: E402  - sau khi đã chắc có credential

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
from FiinQuantX import FiinSession  # noqa: E402

lock = threading.Lock()
ticks = Counter()
first_seen: dict[str, float] = {}
last_seen: dict[str, float] = {}
gaps: dict[str, list[float]] = defaultdict(list)
breadth_hits = Counter()
market_status = Counter()
samples: dict[str, dict] = {}
started = time.time()


def on_tick(data):
    """Đếm, đo khoảng cách giữa hai tick, và giữ một mẫu mỗi symbol."""
    now = time.time()
    try:
        row = data.to_dict()
    except Exception:  # pragma: no cover - prototype
        return
    symbol = str(row.get("Ticker") or "?")
    with lock:
        ticks[symbol] += 1
        if symbol in last_seen:
            gaps[symbol].append(now - last_seen[symbol])
        else:
            first_seen[symbol] = now
            samples[symbol] = row
        last_seen[symbol] = now
        if row.get("MarketStatus"):
            market_status[str(row["MarketStatus"])] += 1
        for field in BREADTH_FIELDS:
            if row.get(field) not in (None, ""):
                breadth_hits[f"{symbol}.{field}"] += 1


session = FiinSession(username=user, password=password).login()
stream = session.Trading_Data_Stream(tickers=TICKERS + INDICES, callback=on_tick)

# Đếm reconnect qua log. Đo được: FiinQuantX *print* dòng "Joined group" nên
# handler không thấy, còn signalrcore *log* lần đóng kết nối nên đếm được — vậy
# lấy số lần đóng làm số reconnect, vì mỗi lần đóng đều được client dựng lại.
# Vẫn giữ bộ đếm join để nếu bản thư viện sau chuyển sang log thì thấy ngay.
events = Counter()


class EventCounter(logging.Handler):
    def emit(self, record):
        text = record.getMessage()
        if "Joined group" in text:
            events["joined"] += 1
        if "Connection closed" in text or '"type":7' in text:
            events["closed"] += 1


logging.getLogger().addHandler(EventCounter())

threading.Thread(target=lambda: stream.start(), daemon=True).start()

deadline = started + args.minutes * 60
while time.time() < deadline:
    time.sleep(15)
    with lock:
        elapsed = time.time() - started
        total = sum(ticks.values())
        print(
            f"t+{elapsed:6.0f}s  tick={total:6d}  "
            f"symbols={len(ticks):2d}/{len(TICKERS) + len(INDICES)}  "
            f"rate={total / max(elapsed, 1):.2f}/s",
            flush=True,
        )

elapsed = time.time() - started
with lock:
    per_symbol = {}
    for symbol, count in sorted(ticks.items(), key=lambda kv: -kv[1]):
        symbol_gaps = sorted(gaps[symbol])
        per_symbol[symbol] = {
            "ticks": count,
            "ticks_per_minute": round(count / (elapsed / 60), 2),
            "gap_median_s": round(symbol_gaps[len(symbol_gaps) // 2], 3) if symbol_gaps else None,
            "gap_max_s": round(symbol_gaps[-1], 3) if symbol_gaps else None,
        }
    out = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S%z"),
        "duration_s": round(elapsed, 1),
        "subscribed": {"tickers": TICKERS, "indices": INDICES},
        "silent_symbols": sorted(set(TICKERS + INDICES) - set(ticks)),
        "market_status": dict(market_status),
        "group_joins": events["joined"],
        "connection_closes": events["closed"],
        # Số lần đóng kết nối là tín hiệu đếm được; xem ghi chú ở EventCounter.
        "reconnects": events["closed"],
        "per_symbol": per_symbol,
        "breadth_fields_seen": dict(breadth_hits),
        "breadth_on_indices": sorted(
            {key.split(".")[0] for key in breadth_hits} & set(INDICES)
        ),
        "samples": samples,
    }

path = os.path.join(os.path.dirname(__file__), "fiinquant_realtime_results.json")
with open(path, "w") as handle:
    json.dump(out, handle, indent=2, ensure_ascii=False, default=str)

print("\n" + "=" * 70 + "\nKẾT LUẬN\n" + "=" * 70)
print(f"Tổng tick        : {sum(ticks.values())} trong {elapsed:.0f}s")
print(f"Mã im lặng       : {out['silent_symbols'] or 'không có'}")
print(f"MarketStatus     : {out['market_status'] or 'không thấy field này'}")
print(
    f"Reconnect trong phiên: {out['reconnects']} "
    f"(joins={out['group_joins']}, closes={out['connection_closes']}) "
    "— >0 nghĩa là Stream Worker cần backoff + dedup theo timestamp"
)
print(f"Breadth trên index: {out['breadth_on_indices'] or 'KHÔNG — vẫn phải tự tính breadth'}")
if not sum(ticks.values()):
    print("\n0 tick — kiểm tra lại có đang trong giờ giao dịch không.")
print(f"\nKết quả đầy đủ: {path}")

# stop() has been observed to block; the results are already written, so hand it
# a bounded attempt and then leave rather than hanging the measurement on it.
# os._exit skips the interpreter's flush, and stdout is block-buffered whenever
# this is piped to a file — so flush first or the summary above is discarded.
sys.stdout.flush()
sys.stderr.flush()
stopper = threading.Thread(target=stream.stop, daemon=True)
stopper.start()
stopper.join(timeout=5)
os._exit(0)
