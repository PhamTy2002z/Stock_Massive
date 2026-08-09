"""PROTOTYPE — vòng 2. Đo lại ba thứ vòng 1 làm lộ ra mâu thuẫn với trang Pricing.

    export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
    set -a && source .env && set +a
    apps/api/.venv/bin/python apps/api/prototypes/probe_fiinquant_limits_round2.py
"""

import json
import os
import sys
from datetime import date, timedelta

username = os.environ.get("FIINQUANT_USERNAME")
password = os.environ.get("FIINQUANT_PASSWORD")
if not username or not password:
    sys.exit("Thiếu FIINQUANT_USERNAME / FIINQUANT_PASSWORD.")

from FiinQuantX import FiinSession  # noqa: E402

client = FiinSession(username=username, password=password).login()
today = date.today()
results = {}


def show(title, value):
    results[title] = value
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    print(json.dumps(value, indent=1, ensure_ascii=False, default=str)[:2500])


# Danh sách mã đủ lớn để dò trần thật, lấy từ chính API.
try:
    universe = list(client.TickerList(ticker="VNAllShare"))
except Exception:
    universe = []
if len(universe) < 400:
    universe = sorted({
        *["ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG"],
        *["MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB"],
        *["TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"],
        *["CMG", "PNJ", "KDH", "HSG", "DGC", "REE", "SBT", "DXG", "NLG", "VCI"],
        *["HVN", "GEX", "PDR", "KBC", "VND", "HCM", "BSI", "CTS", "FTS", "ORS"],
        *["DIG", "CII", "HAG", "ANV", "ASM", "BAF", "BCG", "BMP", "BSR", "BWE"],
        *["CTD", "CTR", "DBC", "DCM", "DGW", "DPM", "DRC", "EIB", "EVF", "FCN"],
        *["FRT", "GMD", "HAH", "HDC", "HDG", "HHV", "HT1", "IDC", "IJC", "IMP"],
        *["KOS", "LPB", "MSB", "NAB", "NKG", "NT2", "NTL", "OCB", "PAN", "PC1"],
        *["PET", "PHR", "PPC", "PTB", "PVD", "PVT", "QCG", "SCS", "SIP", "SJS"],
        *["SZC", "TCH", "TLG", "TMS", "TNH", "VCG", "VGC", "VHC", "VIX", "VPI"],
    })
show("Nguồn danh sách mã để dò trần", {"count": len(universe), "sample": universe[:12]})


def distinct_returned(tickers, **kwargs):
    frame = client.Fetch_Trading_Data(
        realtime=False, tickers=list(tickers), fields=["close"], adjusted=False, **kwargs
    ).get_data()
    if frame is None or frame.empty:
        return 0
    return len({str(t) for t in frame["ticker"]})


# 1. Trần số mã thật cho dữ liệu lịch sử — Pricing nói 33, vòng 1 đo được 50.
out = {}
for count in (33, 50, 100, 200, len(universe)):
    if count > len(universe):
        continue
    try:
        out[f"{count} mã"] = distinct_returned(universe[:count], by="1d", period=1)
    except Exception as exc:
        out[f"{count} mã"] = f"LỖI {type(exc).__name__}: {exc}"
show("1. Trần số mã cho dữ liệu lịch sử (realtime=False)", out)

# 2. Độ sâu lịch sử ngày — vòng 1: 2 năm được, 5 năm rỗng. Trần nằm ở đâu?
out = {}
for years in (2, 3, 4, 5, 10):
    try:
        frame = client.Fetch_Trading_Data(
            realtime=False, tickers=["HPG"], fields=["close"], adjusted=False, by="1d",
            from_date=str(today - timedelta(days=365 * years)), to_date=str(today),
        ).get_data()
        out[f"xin {years} năm"] = (
            {"rows": len(frame), "oldest": str(frame["timestamp"].min())}
            if frame is not None and not frame.empty else "rỗng"
        )
    except Exception as exc:
        out[f"xin {years} năm"] = f"LỖI {type(exc).__name__}: {exc}"
show("2. Độ sâu lịch sử ngày", out)

# 3. adjusted=True cho giá lẻ, adjusted=False cho giá tròn — cái nào là giá khớp thật?
out = {}
for adjusted in (True, False):
    frame = client.Fetch_Trading_Data(
        realtime=False, tickers=["HPG"], fields=["close"], adjusted=adjusted, by="1d", period=2,
    ).get_data()
    out[f"adjusted={adjusted}"] = [float(v) for v in frame["close"]]
show("3. Giá điều chỉnh so với giá khớp", out)

# 4. PriceStatistics — vòng 1 gọi thiếu tham số nên chưa biết có quyền hay không.
stats = client.PriceStatistics()
from_date = str(today - timedelta(days=10))
out = {}
for label, call in (
    ("get_foreign", lambda: stats.get_foreign(tickers=["HPG"], time_filter="Daily", from_date=from_date)),
    ("get_freefloat", lambda: stats.get_freefloat(tickers=["HPG"], from_date=from_date)),
    ("get_ceilingfloor", lambda: stats.get_ceilingfloor(tickers=["HPG"], from_date=from_date)),
    ("get_overview", lambda: stats.get_overview(tickers=["HPG"], time_filter="Daily", from_date=from_date)),
    ("get_value_by_investor", lambda: stats.get_value_by_investor(tickers=["HPG"], from_date=from_date)),
):
    try:
        frame = call()
        out[label] = (
            {"rows": len(frame), "columns": [str(c) for c in frame.columns],
             "first_row": {str(k): str(v) for k, v in frame.iloc[0].to_dict().items()}}
            if frame is not None and not getattr(frame, "empty", True) else "rỗng"
        )
    except Exception as exc:
        out[label] = f"LỖI {type(exc).__name__}: {exc}"
show("4. Reference data qua PriceStatistics", out)

# 5. Báo cáo tài chính — vòng 1 trả rỗng. Thử các tổ hợp tham số khác.
fundamental = client.FundamentalAnalysis()
out = {}
for label, kwargs in (
    ("2024 Q4 hợp nhất đã kiểm toán", dict(statement="balancesheet", years=[2024], quarters=[4], audited=True, type="consolidated")),
    ("2024 Q4 chưa kiểm toán", dict(statement="balancesheet", years=[2024], quarters=[4], audited=False, type="consolidated")),
    ("2024 cả năm", dict(statement="balancesheet", years=[2024], audited=True, type="consolidated")),
    ("2025 Q2 chưa kiểm toán", dict(statement="incomestatement", years=[2025], quarters=[2], audited=False, type="consolidated")),
    ("full 2024", dict(statement="full", years=[2024], quarters=[4], audited=False, type="consolidated")),
):
    try:
        data = fundamental.get_financial_statement(tickers=["HPG"], **kwargs)
        if hasattr(data, "keys"):
            out[label] = {"kiểu": "dict", "keys": [str(k) for k in list(data.keys())[:10]]}
        elif data is not None and not getattr(data, "empty", True):
            out[label] = {"rows": len(data), "columns": [str(c) for c in data.columns][:15]}
        else:
            out[label] = "rỗng"
    except Exception as exc:
        out[label] = f"LỖI {type(exc).__name__}: {exc}"
try:
    ratios = fundamental.get_ratios(tickers=["HPG"], years=[2024], quarters=[4])
    out["get_ratios"] = (
        {"rows": len(ratios), "columns": [str(c) for c in ratios.columns][:15]}
        if ratios is not None and not getattr(ratios, "empty", True) else "rỗng"
    )
except Exception as exc:
    out["get_ratios"] = f"LỖI {type(exc).__name__}: {exc}"
show("5. Báo cáo tài chính", out)

# 6. Vốn hoá và các hàm định giá còn lại.
out = {}
for label, call in (
    ("BasicInfor", lambda: client.BasicInfor(tickers=["HPG"])),
    ("GetDataPoint", lambda: client.GetDataPoint(tickers=["HPG"], fields=["MarketCap"])),
    ("sector_valuation", lambda: client.MarketDepth().get_sector_valuation(
        tickers=["HPG"], level=2, from_date=from_date)),
    ("index_valuation", lambda: client.MarketDepth().get_index_valuation(
        tickers=["VN30"], from_date=from_date)),
):
    try:
        value = call()
        if value is None:
            out[label] = "None"
        elif hasattr(value, "columns"):
            out[label] = {"rows": len(value), "columns": [str(c) for c in value.columns][:15]}
        else:
            out[label] = str(value)[:400]
    except Exception as exc:
        out[label] = f"LỖI {type(exc).__name__}: {exc}"
show("6. Vốn hoá và định giá theo ngành/chỉ số", out)

path = os.path.join(os.path.dirname(__file__), "fiinquant_limits_round2.json")
with open(path, "w") as handle:
    json.dump(results, handle, indent=2, ensure_ascii=False, default=str)
print(f"\nKết quả: {path}")
