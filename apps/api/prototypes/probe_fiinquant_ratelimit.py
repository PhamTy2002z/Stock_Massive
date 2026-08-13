"""PROTOTYPE — đo cách FiinQuant đếm request: theo lời gọi hay theo mã.

Trần công bố là 90 request/phút. Nếu đếm theo mã thì một lời gọi 50 mã đã tiêu
hơn nửa hạn mức phút, và vòng B sẽ bị chặn sau một vài lời gọi. Nếu đếm theo
lời gọi thì hai vòng cho kết quả xấp xỉ nhau.

    export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
    set -a && source .env && set +a
    apps/api/.venv/bin/python apps/api/prototypes/probe_fiinquant_ratelimit.py
"""

import json
import os
import sys
import time

username = os.environ.get("FIINQUANT_USERNAME")
password = os.environ.get("FIINQUANT_PASSWORD")
if not username or not password:
    sys.exit("Thiếu FIINQUANT_USERNAME / FIINQUANT_PASSWORD.")

from FiinQuantX import FiinSession  # noqa: E402

client = FiinSession(username=username, password=password).login()

TICKERS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
    "CMG", "PNJ", "KDH", "HSG", "DGC", "REE", "SBT", "DXG", "NLG", "VCI",
    "HVN", "GEX", "PDR", "KBC", "VND", "HCM", "BSI", "CTS", "FTS", "ORS",
]
WINDOW_SECONDS = 70
results = {}


def hammer(label, tickers):
    calls, empties, error, durations = 0, 0, None, []
    started = time.monotonic()
    while time.monotonic() - started < WINDOW_SECONDS:
        call_started = time.monotonic()
        try:
            frame = client.Fetch_Trading_Data(
                realtime=False, tickers=list(tickers), fields=["close"],
                adjusted=False, by="1d", period=1,
            ).get_data()
            calls += 1
            durations.append(round(time.monotonic() - call_started, 2))
            if frame is None or frame.empty:
                empties += 1
                if empties >= 3:
                    error = "3 lần liên tiếp trả rỗng — nhiều khả năng đã bị chặn ngầm"
                    break
            else:
                empties = 0
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
    elapsed = time.monotonic() - started
    out = {
        "mã mỗi lời gọi": len(tickers),
        "số lời gọi thành công": calls,
        "tổng số mã đã xin": calls * len(tickers),
        "giây đã chạy": round(elapsed, 1),
        "lời gọi mỗi phút": round(calls / elapsed * 60, 1) if elapsed else 0,
        "thời gian mỗi lời gọi (s)": {
            "nhanh nhất": min(durations) if durations else None,
            "chậm nhất": max(durations) if durations else None,
        },
        "dừng vì": error or "hết cửa sổ đo, chưa bị chặn",
    }
    results[label] = out
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return out


a = hammer("Vòng A — 1 mã mỗi lời gọi", TICKERS[:1])
print(f"\nNghỉ 65s để cửa sổ phút trôi qua…")
time.sleep(65)
b = hammer("Vòng B — 50 mã mỗi lời gọi", TICKERS)

if b["số lời gọi thành công"] <= 3 < a["số lời gọi thành công"]:
    verdict = "ĐẾM THEO MÃ — vòng B bị chặn gần như ngay lập tức"
elif b["số lời gọi thành công"] >= a["số lời gọi thành công"] * 0.5:
    verdict = "ĐẾM THEO LỜI GỌI — số mã trong một lời gọi không ảnh hưởng hạn mức"
else:
    verdict = "KHÔNG KẾT LUẬN ĐƯỢC — vòng B chậm hơn nhưng chưa rõ vì hạn mức hay vì tải"

results["kết luận"] = verdict
print(f"\n{'=' * 70}\nKẾT LUẬN: {verdict}\n{'=' * 70}")
print(
    f"Ngân sách EOD với 100 mã: "
    f"{'~1 lời gọi/ngày' if 'LỜI GỌI' in verdict else '~100 request/ngày'}, "
    f"trên hạn mức 100.000/tháng."
)

path = os.path.join(os.path.dirname(__file__), "fiinquant_ratelimit.json")
with open(path, "w") as handle:
    json.dump(results, handle, indent=2, ensure_ascii=False)
print(f"Kết quả: {path}")
