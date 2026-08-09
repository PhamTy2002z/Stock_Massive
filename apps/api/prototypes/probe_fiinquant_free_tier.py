"""PROTOTYPE — vứt đi sau khi đo xong. Không import từ src/.

Đo năng lực thật của gói FiinQuant free, để chốt bảng Main/Cover trong ADR-0002.

Chạy:
    export FIINQUANT_USERNAME=... FIINQUANT_PASSWORD=...
    apps/api/.venv/bin/python apps/api/prototypes/probe_fiinquant_free_tier.py

Thêm --ratelimit để đo trần request/phút (gọi liên tục tới khi bị chặn —
tốn vài trăm request trong hạn mức 100.000/tháng, mặc định tắt).
"""

import json
import os
import sys
import time
from datetime import date, timedelta

VN30 = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
    "CMG", "PNJ", "KDH", "HSG", "DGC", "REE", "SBT", "DXG", "NLG", "VCI",
    "HVN", "GEX", "PDR", "KBC", "VND", "HCM", "BSI", "CTS", "FTS", "ORS",
]

ALL_FIELDS = ["open", "high", "low", "close", "volume", "value", "bu", "sd", "fb", "fs", "fn"]

results = {}


def probe(name):
    """Chạy một phép đo, ghi kết quả vào results, không để lỗi chặn phép đo sau."""
    def wrap(fn):
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        started = time.monotonic()
        try:
            value = fn()
            results[name] = {"ok": True, "value": value}
            print(json.dumps(value, indent=2, ensure_ascii=False, default=str)[:3000])
        except Exception as exc:
            results[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(f"LỖI  {type(exc).__name__}: {exc}")
        print(f"({time.monotonic() - started:.1f}s)")
    return wrap


def frame_summary(frame, note=""):
    """Rút gọn một DataFrame thành thứ đọc được, kèm dải ngày và giá mẫu."""
    if frame is None:
        return {"note": note, "empty": True}
    if hasattr(frame, "get_data"):
        frame = frame.get_data()
    if frame is None or getattr(frame, "empty", True):
        return {"note": note, "empty": True}
    out = {
        "note": note,
        "rows": int(len(frame)),
        "columns": [str(c) for c in frame.columns],
        "tickers": sorted({str(t) for t in frame["ticker"]}) if "ticker" in frame.columns else None,
    }
    if "timestamp" in frame.columns:
        out["timestamp_min"] = str(frame["timestamp"].min())
        out["timestamp_max"] = str(frame["timestamp"].max())
    if "close" in frame.columns:
        out["close_sample"] = [float(v) for v in frame["close"].head(3)]
    out["first_row"] = {str(k): str(v) for k, v in frame.iloc[0].to_dict().items()}
    return out


username = os.environ.get("FIINQUANT_USERNAME")
password = os.environ.get("FIINQUANT_PASSWORD")
if not username or not password:
    sys.exit("Thiếu FIINQUANT_USERNAME / FIINQUANT_PASSWORD trong môi trường.")

from FiinQuantX import FiinSession  # noqa: E402

print("Đăng nhập FiinQuant…")
login_started = time.monotonic()
client = FiinSession(username=username, password=password).login()
print(f"Đăng nhập xong sau {time.monotonic() - login_started:.1f}s")

today = date.today()


@probe("0. Bề mặt API — có những nhóm hàm nào")
def _():
    groups = [n for n in dir(client) if not n.startswith("_")]
    detail = {}
    for group in groups:
        try:
            attr = getattr(client, group)
            if callable(attr) and group[0].isupper():
                detail[group] = [n for n in dir(attr()) if not n.startswith("_")]
        except Exception as exc:
            detail[group] = f"không gọi được: {type(exc).__name__}"
    return {"top_level": groups, "sub_functions": detail}


@probe("1. Trường dữ liệu — bu/sd/fb/fs/fn có mở cho gói free không")
def _():
    frame = client.Fetch_Trading_Data(
        realtime=False, tickers=["HPG"], fields=ALL_FIELDS,
        adjusted=True, by="1d", period=3,
    ).get_data()
    summary = frame_summary(frame, "xin đủ 11 trường")
    got = set(summary.get("columns") or [])
    summary["fields_missing"] = sorted(f for f in ALL_FIELDS if f not in got)
    return summary


@probe("2. Đơn vị giá — VND hay nghìn VND")
def _():
    frame = client.Fetch_Trading_Data(
        realtime=False, tickers=["HPG", "VCB"], fields=["close", "value", "volume"],
        adjusted=True, by="1d", period=1,
    ).get_data()
    summary = frame_summary(frame, "so close với giá thật: HPG ~2x.xxx đ, VCB ~6x.xxx đ")
    closes = summary.get("close_sample") or []
    if closes:
        summary["verdict"] = "VND" if max(closes) > 1000 else "nghìn VND"
    return summary


@probe("3. Trần số mã — 33 là thật hay đoán")
def _():
    out = {}
    for count in (10, 33, 34, 50):
        try:
            frame = client.Fetch_Trading_Data(
                realtime=False, tickers=VN30[:count], fields=["close"],
                adjusted=True, by="1d", period=1,
            ).get_data()
            distinct = len({str(t) for t in frame["ticker"]}) if frame is not None and not frame.empty else 0
            out[f"{count} mã"] = {"ok": True, "distinct_tickers_returned": distinct}
        except Exception as exc:
            out[f"{count} mã"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return out


@probe("4. Độ sâu lịch sử ngày — pricing nói 1 năm")
def _():
    out = {}
    for years_back, label in ((1, "1 năm"), (2, "2 năm"), (5, "5 năm")):
        try:
            frame = client.Fetch_Trading_Data(
                realtime=False, tickers=["HPG"], fields=["close"], adjusted=True, by="1d",
                from_date=str(today - timedelta(days=365 * years_back)), to_date=str(today),
            ).get_data()
            out[f"xin {label}"] = frame_summary(frame)
        except Exception as exc:
            out[f"xin {label}"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


@probe("5. Độ sâu intraday — pricing nói 1 tháng")
def _():
    out = {}
    for days_back, label in ((7, "7 ngày"), (30, "30 ngày"), (90, "90 ngày")):
        try:
            frame = client.Fetch_Trading_Data(
                realtime=False, tickers=["HPG"], fields=["close"], adjusted=False, by="1m",
                from_date=str(today - timedelta(days=days_back)), to_date=str(today),
            ).get_data()
            out[f"xin {label}"] = frame_summary(frame)
        except Exception as exc:
            out[f"xin {label}"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


@probe("6. Báo cáo tài chính — có trong gói free không")
def _():
    data = client.FundamentalAnalysis().get_financial_statement(
        tickers=["HPG"], statement="balancesheet", years=[2024],
        quarters=[4], audited=True, type="consolidated",
    )
    if hasattr(data, "keys"):
        return {"type": type(data).__name__, "keys": [str(k) for k in list(data.keys())[:20]]}
    return frame_summary(data)


@probe("7. Định giá P/E, P/B — có trong gói free không")
def _():
    data = client.MarketDepth().get_stock_valuation(
        tickers=["HPG", "VCB"],
        from_date=str(today - timedelta(days=10)), to_date=str(today),
    )
    return frame_summary(data)


@probe("8. Reference — room NĐTNN, freefloat, giá trần sàn, giao dịch theo nhà đầu tư")
def _():
    stats = client.PriceStatistics()
    out = {}
    for label, call in (
        ("get_foreign", lambda: stats.get_foreign(tickers=["HPG"])),
        ("get_freefloat", lambda: stats.get_freefloat(tickers=["HPG"])),
        ("get_ceilingfloor", lambda: stats.get_ceilingfloor(tickers=["HPG"])),
        ("get_overview", lambda: stats.get_overview(tickers=["HPG"])),
        ("get_value_by_investor", lambda: stats.get_value_by_investor(tickers=["HPG"])),
    ):
        try:
            out[label] = frame_summary(call())
        except Exception as exc:
            out[label] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


@probe("8b. Gói của tài khoản này được phép những gì")
def _():
    fundamental = client.FundamentalAnalysis()
    out = {}
    for label in ("package_list", "valid_fields", "ratio_map"):
        try:
            value = getattr(fundamental, label)
            out[label] = str(value)[:1500]
        except Exception as exc:
            out[label] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        out["get_ratios"] = frame_summary(
            fundamental.get_ratios(tickers=["HPG"], years=[2024], quarters=[4])
        )
    except Exception as exc:
        out["get_ratios"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


@probe("8c. Dữ liệu thị trường khác — độ rộng, dòng tiền, danh sách mã")
def _():
    out = {}
    for label, call in (
        ("TickerList VN30", lambda: client.TickerList(ticker="VN30")),
        ("MarketBreadth", lambda: client.MarketBreadth().get()),
        ("MoneyFlow", lambda: client.MoneyFlow().get_contribution()),
        ("sector_valuation", lambda: client.MarketDepth().get_sector_valuation(
            from_date=str(today - timedelta(days=5)))),
    ):
        try:
            value = call()
            out[label] = value if isinstance(value, (list, str)) else frame_summary(value)
        except Exception as exc:
            out[label] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


if "--ratelimit" in sys.argv:
    @probe("9. Cách đếm request — 1 lời gọi nhiều mã tính là 1 hay N")
    def _():
        out = {}
        for label, tickers in (("1 mã/lần", VN30[:1]), ("10 mã/lần", VN30[:10])):
            calls = 0
            started = time.monotonic()
            error = None
            while time.monotonic() - started < 75 and calls < 200:
                try:
                    client.Fetch_Trading_Data(
                        realtime=False, tickers=tickers, fields=["close"],
                        adjusted=True, by="1d", period=1,
                    ).get_data()
                    calls += 1
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    break
            out[label] = {
                "calls_before_block": calls,
                "elapsed_s": round(time.monotonic() - started, 1),
                "stopped_by": error or "hết thời gian đo, chưa bị chặn",
            }
            time.sleep(65)  # để cửa sổ phút trôi qua trước phép đo sau
        out["đọc kết quả"] = (
            "hai con số xấp xỉ nhau ⇒ đếm theo lời gọi; "
            "con số của '10 mã/lần' nhỏ hơn ~10 lần ⇒ đếm theo mã"
        )
        return out
else:
    print("\n(Bỏ qua phép đo rate limit — thêm --ratelimit để chạy)")


out_path = os.path.join(os.path.dirname(__file__), "fiinquant_free_tier_results.json")
with open(out_path, "w") as handle:
    json.dump(results, handle, indent=2, ensure_ascii=False, default=str)

print(f"\n{'=' * 70}\nTÓM TẮT\n{'=' * 70}")
for name, result in results.items():
    print(f"{'✓' if result['ok'] else '✗'}  {name}" + ("" if result["ok"] else f"  →  {result['error']}"))
print(f"\nKết quả đầy đủ: {out_path}")
