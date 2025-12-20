# Income Statement ("Kết Quả Kinh Doanh") - Scout Report

Date: 2025-12-20

## Summary
Found all income statement files. System uses: UI Component → React Hooks → API Client → Backend Router → Service → Schema

## FRONTEND FILES

### 1. Main UI Component
File: D:\Stock_Massive\apps\web\src\components\dashboard\finance-tab-content.tsx
Purpose: Renders "Kết quả kinh doanh" (Income Statement) financial table
- 19+ line items from mock data
- Displays: Revenue, COGS, Expenses, Profits, Taxes, Net Income
- Period selector: Quarter/Year
- Vietnamese labels with proper formatting
- Fallback to mock data if API unavailable

Key Rows in Table:
- Doanh thu bán hàng và cung cấp dịch vụ (Sales Revenue)
- Doanh thu thuần (Net Revenue)
- Giá vốn hàng bán (Cost of Goods Sold)
- Lãi gộp (Gross Profit)
- Chi phí bán hàng (Selling Expenses)
- Chi phí quản lý doanh nghiệp (Administrative Expenses)
- Lãi/Lỗ từ hoạt động kinh doanh (Operating Profit)
- Lợi nhuận trước thuế (Profit Before Tax)
- Lợi nhuận thuần (Net Profit)
- Cổ đông của Công ty mẹ (Parent Company Shareholders' Profit)

### 2. React Hooks
Files:
- D:\Stock_Massive\apps\web\src\hooks\use-income-statement.ts
- D:\Stock_Massive\apps\web\src\hooks\use-balance-sheet.ts
- D:\Stock_Massive\apps\web\src\hooks\use-cash-flow.ts

All use TanStack React Query with 5-minute cache stale time.

### 3. API Client
File: D:\Stock_Massive\apps\web\src\lib\api.ts (lines 146-227)

Defines:
- IncomeStatementRow interface
- IncomeStatementResponse interface
- fetchIncomeStatement() function
- fetchBalanceSheet() function
- fetchCashFlow() function

API Endpoints Called:
GET /stocks/{symbol}/financials/income-statement?period=quarter&limit=4
GET /stocks/{symbol}/financials/balance-sheet-detailed?period=quarter&limit=4
GET /stocks/{symbol}/financials/cash-flow?period=quarter&limit=4

## BACKEND FILES

### 4. FastAPI Router
File: D:\Stock_Massive\apps\api\src\stocks\financial\router.py (lines 41-72)

Endpoints:
- GET /{symbol}/financials/income - Simplified (List[IncomeStatementItem])
- GET /{symbol}/financials/income-statement - Detailed (IncomeStatementResponse)
- GET /{symbol}/financials/balance-sheet-detailed
- GET /{symbol}/financials/cash-flow

### 5. Backend Service
File: D:\Stock_Massive\apps\api\src\stocks\financial\service.py

Methods:
- get_income_statement() - Simplified version
- get_income_statement_detailed() - Full table version
- _df_to_income_statement_response() - Data transformation

Data Transformation:
- Converts vnstock Finance DataFrame to IncomeStatementResponse
- Maps 15 income statement line items
- Divides values by 1,000,000 (unit: "Triệu VND" - millions)
- Supports quarter and year periods
- Vietnamese column name preferences with English fallbacks

Row Mappings (15 items):
1. revenue - Doanh thu thuần
2. cogs - Giá vốn hàng bán
3. gross_profit - Lợi nhuận gộp
4. selling_expense - Chi phí bán hàng
5. admin_expense - Chi phí quản lý
6. operating_profit - Lợi nhuận từ HĐKD
7. financial_income - Doanh thu tài chính
8. financial_expense - Chi phí tài chính
9. other_income - Thu nhập khác
10. other_expense - Chi phí khác
11. pre_tax_profit - Lợi nhuận trước thuế
12. tax_expense - Chi phí thuế TNDN
13. net_profit - Lợi nhuận sau thuế
14. parent_profit - LNST của cổ đông công ty mẹ
15. eps - EPS (VND)

### 6. Backend Schema
File: D:\Stock_Massive\apps\api\src\stocks\schemas\financial.py (lines 31-61)

Models:
- IncomeStatementItem - Simplified summary
- IncomeStatementRow - Table row with metadata
- IncomeStatementResponse - Complete API response

IncomeStatementRow contains:
- id: str - Unique identifier
- label: str - Vietnamese display label
- values: dict[str, Optional[float]] - Period → Value mapping
- level: int - Indentation level (0-2)
- is_header: bool - Section header flag
- is_summary: bool - Summary row flag

## DATA FLOW

FinanceTabContent
  → useIncomeStatement hook
    → fetchIncomeStatement (api.ts)
      → GET /stocks/{symbol}/financials/income-statement
        → Router: get_income_statement_detailed
          → Service: get_income_statement_detailed
            → FinancialService: _df_to_income_statement_response
              → vnstock: Finance.income_statement()
                → Returns: IncomeStatementResponse with rows and periods

## CURRENT DISPLAY

Periods: Q3/2025, Q2/2025, Q1/2025, Q4/2024 (Quarterly)
Rows: 19 items (including detail rows)
Unit: Triệu VND (Millions Vietnamese Dong)
Format: Dot thousand separators, comma decimals

## FILES SUMMARY

Frontend:
- D:\Stock_Massive\apps\web\src\components\dashboard\finance-tab-content.tsx (main UI)
- D:\Stock_Massive\apps\web\src\hooks\use-income-statement.ts
- D:\Stock_Massive\apps\web\src\hooks\use-balance-sheet.ts
- D:\Stock_Massive\apps\web\src\hooks\use-cash-flow.ts
- D:\Stock_Massive\apps\web\src\lib\api.ts

Backend:
- D:\Stock_Massive\apps\api\src\stocks\financial\router.py
- D:\Stock_Massive\apps\api\src\stocks\financial\service.py
- D:\Stock_Massive\apps\api\src\stocks\schemas\financial.py
