"""Real provider responses, captured 2026-08-27, so the suite stays offline.

Each frame is a **subset of rows** from a live response, kept in the provider's
own shape: its column order, its four quarter columns (this client answered four
and printed that it would; a newer vnstock answered eight for the same account,
so the count is the client's and not a contract), its Vietnamese and English
labels, and its floats. Rows were dropped, never edited — the numbers are the
ones the provider answered, which is the whole point of a golden test that
checks arithmetic instead of labels.

The three symbols are the three templates this market reports under: STB is a
bank, SSI a securities house, HPG a non-financial company.

Two shapes here exist only because the provider produces them:

- SSI's income statement carries ``business_income_tax_deferred`` twice, and the
  second row's label is "Lợi nhuận thuần phân bổ cho lợi ích của cổ đông không
  kiểm soát" — the minority interest line under another line's id. Its balance
  sheet carries ``accumulated_depreciation`` four times, one per class of asset.
- the KBS ratio response's fourth column is labelled ``2025-Q4_1`` (pandas'
  suffix for a duplicated column name) and repeats the ``2026-Q2`` column's
  values exactly.

``STB_OWNERS_EQUITY_2026Q2`` is the cross-check: the same number is already
stored as ``parent_equity_vnd`` under the ``fundamental`` Capability in
``provider_snapshots``, effective 2026-06-29, read from the live database on
2026-08-27. Two independent paths to one figure.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd

#: ``Finance(symbol="STB", source="VCI").income_statement(period="quarter",
#: lang="en", dropna=True)``. A bank: the pretax line is labelled, and
#: ``business_income_tax_expenses`` really is the tax.
STB_INCOME_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
Tổng lợi nhuận/lỗ trước thuế,Net Accounting Profit/(loss) before tax,net_accounting_profit_loss_before_tax,2029891000000.0,2106205000000.0,-3360145000000.0,3656898000000.0
Chi phí thuế TNDN hiện hành,Business income tax - current,business_income_tax_current,-683200000000.0,-521801000000.0,595471000000.0,-755615000000.0
Chi phí thuế TNDN hoãn lại,Business income tax - deferred,business_income_tax_deferred,0.0,0.0,12212000000.0,0.0
Chi phí thuế thu nhập doanh nghiệp,Business income tax expenses,business_income_tax_expenses,-683200000000.0,-521801000000.0,607683000000.0,-755615000000.0
Lợi nhuận sau thuế,Net profit/(loss) after tax,net_profit_loss_after_tax,1346691000000.0,1584404000000.0,-2752462000000.0,2901283000000.0
Tổng thu nhập hoạt động,Total Operating Income,total_operating_income,9950076000000.0,7538113000000.0,7694340000000.0,8796519000000.0
"""

#: ``Finance(symbol="SSI", ...).income_statement(...)``. A securities house: no
#: correctly labelled pretax line, a duplicated ``item_id`` whose two values
#: differ, and a tax label on a number that is not a tax.
SSI_INCOME_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
KẾT QUẢ HOẠT ĐỘNG,OPERATING PROFIT/(LOSS),operating_profit_loss,1528681849704.0,1595722713102.0,998697843536.0,1835408403000.0
CHI PHÍ THUẾ THU NHẬP DOANH NGHIỆP,BUSINESS INCOME TAX EXPENSES,business_income_tax_expenses,1528966041130.0,1593431914504.0,1003195760696.0,1834918059122.0
Chi phí thuế thu nhập hiện hành,Business income tax - current,business_income_tax_current,-301667112228.0,-300862943049.0,-186886839058.0,-352165041119.0
Chi phí thuế thu nhập hoãn lại,Business income tax - deferred,business_income_tax_deferred,4585945424.0,-14974173554.0,3380268456.0,-7154348387.0
LỢI NHUẬN KẾ TOÁN SAU THUẾ,NET PROFIT/(LOSS) AFTER TAX,net_profit_loss_after_tax,1231884874326.0,1277594797901.0,819689190094.0,1475598669616.0
Lợi nhuận thuần phân bổ cho lợi ích của cổ đông không kiểm soát,Business income tax - deferred,business_income_tax_deferred,758786600.0,-315043012.0,2227880294.0,470785705.0
"""

#: ``Finance(symbol="HPG", ...).income_statement(...)``. Non-financial: the
#: pretax line is labelled and the tax total arrives under a third name,
#: ``corporate_income_tax_expenses``.
HPG_INCOME_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
Doanh thu thuần,Net sales,net_sales,55158902298901.0,52900847302653.0,46176484549771.0,36407416403924.0
Lãi/(lỗ) trước thuế,Net accounting profit/(loss) before tax,net_accounting_profit_loss_before_tax,7184684207426.0,10762183839545.0,4600129962763.0,4628313172434.0
Thuế thu nhập doanh nghiệp - hiện thời,Business income tax - current,business_income_tax_current,-904510286555.0,-1681871206942.0,-744749714238.0,-632794091038.0
Thuế thu nhập doanh nghiệp - hoãn lại,Business income tax - deferred,business_income_tax_deferred,144300346223.0,-24394432580.0,32969484742.0,16733235327.0
Chi phí thuế thu nhập doanh nghiệp,Corporate income tax expenses,corporate_income_tax_expenses,-760209940332.0,-1706265639522.0,-711780229496.0,-616060855711.0
Lãi/(lỗ) thuần sau thuế,Net profit/(loss) after tax,net_profit_loss_after_tax,6424474267094.0,9055918200023.0,3888349733267.0,4012252316723.0
"""

STB_BALANCE_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
TỔNG TÀI SẢN,TOTAL ASSETS,total_assets,892048566000000.0,859571527000000.0,917119803000000.0,848942045000000.0
VỐN CHỦ SỞ HỮU,OWNER'S EQUITY,owners_equity,62807249000000.0,61476611000000.0,59866744000000.0,62704792000000.0
"""

#: Four ``accumulated_depreciation`` rows, three of them with different numbers.
SSI_BALANCE_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
Khấu hao lũy kế TSCĐ hữu hình,Accumulated depreciation,accumulated_depreciation,-337183966640.0,-325881860094.0,-324514814928.0,-313202787336.0
Khấu hao lũy kế tài sản thuê tài chính,Accumulated depreciation,accumulated_depreciation,0.0,0.0,0.0,0.0
Khấu khao lũy kế TSCĐ vô hình,Accumulated depreciation,accumulated_depreciation,-244903394361.0,-234486615367.0,-226987121513.0,-216103113927.0
Khấu hao lũy kế tài sản đầu tư,Accumulated depreciation,accumulated_depreciation,-104659706736.0,-102116024126.0,-99081694077.0,-97187169862.0
Vốn chủ sở hữu,Owner's Equity,owners_equity,40723958711514.0,39668193663782.0,32066318460762.0,31255465832917.0
Vốn đầu tư của chủ sở hữu,Shareholders' equity,shareholders_equity,30396503767268.0,30296698167268.0,24068975194604.0,24069363381308.0
"""

HPG_BALANCE_CSV = """item,item_en,item_id,2026-Q2,2026-Q1,2025-Q4,2025-Q3
Vốn chủ sở hữu,Owner's Equity,owners_equity,141516026558331.0,139781792206472.0,131220010876575.0,127516012099269.0
"""

#: ``Finance(symbol="STB", source="KBS").ratio(period="quarter", lang="en",
#: dropna=True)``. Two columns short of the statements' meta (no ``item_en`` —
#: KBS ignores ``lang``), the periods out of order, and a fourth column whose
#: label repeats 2025-Q4 while its values repeat 2026-Q2's.
STB_RATIO_CSV = """item,item_id,2026-Q2,2025-Q4,2026-Q1,2025-Q4_1
Thu nhập trên mỗi cổ phần của 4 quý gần nhất (EPS),trailing_eps,6518.96,5767.39,3150.36,6518.96
Giá trị sổ sách của cổ phiếu (BVPS),book_value_per_share_bvps,33261.34,30692.71,31755.91,33261.34
Chỉ số giá thị trường trên thu nhập (P/E),pe_ratio,8.73,6.64,18.41,8.73
Chỉ số giá thị trường trên giá trị sổ sách (P/B),pb_ratio,1.71,1.25,1.83,1.71
Beta,beta,0.99,1.2,1.05,0.99
Tỷ suất lợi nhuận trên vốn chủ sở hữu bình quân (ROEA),roe,4.74,5.13,-4.49,4.74
Tỷ suất sinh lợi trên tổng tài sản bình quân (ROAA),roa,0.35,0.38,-0.31,0.35
"""

#: STB's owner's equity for 2026-Q2, as both the balance sheet and the stored
#: ``fundamental`` snapshot report it.
STB_OWNERS_EQUITY_2026Q2 = 62_807_249_000_000

#: The quarter every golden assertion is made on.
GOLDEN_PERIOD = "2026-Q2"


def _frame(csv: str) -> pd.DataFrame:
    return pd.read_csv(StringIO(csv))


def stb_income() -> pd.DataFrame:
    return _frame(STB_INCOME_CSV)


def ssi_income() -> pd.DataFrame:
    return _frame(SSI_INCOME_CSV)


def hpg_income() -> pd.DataFrame:
    return _frame(HPG_INCOME_CSV)


def stb_balance() -> pd.DataFrame:
    return _frame(STB_BALANCE_CSV)


def ssi_balance() -> pd.DataFrame:
    return _frame(SSI_BALANCE_CSV)


def hpg_balance() -> pd.DataFrame:
    return _frame(HPG_BALANCE_CSV)


def stb_ratio() -> pd.DataFrame:
    return _frame(STB_RATIO_CSV)
