"""Real provider responses, captured 2026-08-27, so the suite stays offline.

The frames are captured rows kept in the provider's own shape: its column
order, the dtypes pandas gives them, its loose window (a request for
2026-06-01..2026-06-15 came back holding 2026-05-29 and 2026-06-16 as well), and
its units — STB in thousands of dong, VNINDEX in points. The units are what the
code under test converts, so a fixture that pre-scaled them would test nothing.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd

#: ``Quote(symbol="STB", source="VCI").history(start="2026-06-01",
#: end="2026-06-15", interval="1D")``. Prices in thousands of dong.
STB_DAILY_CSV = """time,open,high,low,close,volume
2026-05-29,68.0,68.8,68.0,68.0,2629200
2026-06-01,68.4,69.6,67.0,67.0,5044700
2026-06-02,67.2,67.6,66.3,66.6,6788500
2026-06-03,66.5,67.6,66.1,66.1,5310300
2026-06-04,66.3,70.5,66.2,70.4,10815200
2026-06-05,70.5,70.5,69.2,69.8,3820900
2026-06-08,69.2,71.0,68.6,69.8,4880800
2026-06-09,70.0,73.5,69.2,72.0,8269000
2026-06-10,72.1,72.3,70.6,70.6,3159300
2026-06-11,70.7,72.5,70.0,71.3,4074600
2026-06-12,71.5,73.0,70.9,70.9,5420000
2026-06-15,71.1,73.0,71.1,71.8,4486600
2026-06-16,72.1,73.0,71.3,71.3,2756600
"""

#: ``Quote(symbol="VNINDEX", source="VCI").history(...)``. Prices in points, and
#: no scaling is correct for them.
VNINDEX_DAILY_CSV = """time,open,high,low,close,volume
2026-05-29,1864.42,1873.17,1854.34,1863.49,688077025
2026-06-01,1867.44,1871.09,1840.4,1844.54,506972140
2026-06-02,1845.32,1858.76,1822.32,1826.47,727018675
2026-06-03,1824.18,1831.65,1798.05,1819.01,722920164
2026-06-04,1822.08,1831.55,1812.65,1831.55,601316050
2026-06-05,1833.07,1846.71,1830.37,1838.9,502964274
2026-06-08,1822.1,1822.95,1789.31,1790.53,714568751
2026-06-09,1799.21,1800.8,1780.71,1793.05,527110166
2026-06-10,1793.45,1805.03,1789.48,1803.71,625012446
2026-06-11,1793.15,1801.99,1788.64,1798.61,410733903
"""

#: ``Listing(source="VCI").symbols_by_exchange()``, one captured row of each
#: shape the response holds: the three boards, the ``DELISTED`` placeholder the
#: provider uses instead of a board, and the instrument types that are not
#: companies. ``HSX`` is the provider's spelling of HOSE.
#:
#: XPH's ``icb_code2`` is blanked from its captured value on purpose. Today every
#: unclassified share in the response is also delisted, but the roster's
#: classification is nullable by contract — a listed share nothing has
#: classified is a normal row — and that row has to exist somewhere.
LISTINGS_CSV = """symbol,exchange,type,sid,organ_short_name,organ_name,product_grp_id,icb_code2
YEG,HSX,STOCK,3560.0,Tập đoàn Yeah1,Công ty Cổ phần Tập đoàn Yeah1,STO,5500
YTC,UPCOM,STOCK,3561.0,XNK Y tế TP.HCM,Công ty Cổ phần Xuất nhập khẩu Y tế Thành phố Hồ Chí Minh,UPX,4500
X20,HNX,STOCK,3547.0,May mặc X20,Công ty Cổ phần X20,STX,3700
XPH,UPCOM,STOCK,3557.0,Xà phòng Hà Nội,Công ty Cổ phần Xà phòng Hà Nội,UPX,
XDC,DELISTED,STOCK,3550.0,Xây dựng Tân Cảng,Công ty Cổ phần Xây dựng Công trình Tân Cảng,,2300
CVIC2601,HSX,CW,9001.0,CW VIC,Chứng quyền VIC,CW,
E1VFVN30,HSX,ETF,9002.0,E1VFVN30,Quỹ ETF VFMVN30,ETF,
"""

#: ``Listing(source="VCI").industries_icb()``. Level 2 is the level whose codes
#: ``symbols_by_exchange`` reports in ``icb_code2``; the deeper levels are in the
#: real response too and must not be joined on.
INDUSTRIES_CSV = """icb_name,en_icb_name,icb_code,level
Dầu khí,Oil & Gas,0500,2
Xây dựng và Vật liệu,Construction & Materials,2300,2
Y tế,Health Care,4500,2
Hàng cá nhân & Gia dụng,Personal & Household Goods,3700,2
Truyền thông,Media,5500,2
Sản xuất Dầu khí,Oil & Gas Producers,0530,3
"""


def _frame(csv: str, *, parse_time: bool) -> pd.DataFrame:
    frame = pd.read_csv(StringIO(csv), dtype={"icb_code": str, "icb_code2": str})
    if parse_time:
        frame["time"] = pd.to_datetime(frame["time"])
    return frame


def stb_daily() -> pd.DataFrame:
    return _frame(STB_DAILY_CSV, parse_time=True)


def vnindex_daily() -> pd.DataFrame:
    return _frame(VNINDEX_DAILY_CSV, parse_time=True)


def listings() -> pd.DataFrame:
    return _frame(LISTINGS_CSV, parse_time=False)


def industries() -> pd.DataFrame:
    return _frame(INDUSTRIES_CSV, parse_time=False)
