import { DashboardLayout } from "@/components/layout"
import { MarketIndices, StockTickerHeader, StockDetailPanel, StockStatsTable, StockCompanyInfo } from "@/components/dashboard"

export default function Home() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6">
        {/* Market Indices Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Chỉ số thị trường
          </h2>
          <MarketIndices />
        </section>

        {/* Selected Stock Ticker */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* Left: Main Content */}
          <div className="space-y-4">
            <StockTickerHeader
              symbol="HAG"
              companyName="Công ty Cổ phần Hoàng Anh Gia Lai"
              price={17.50}
              change={0}
              changePercent={0}
            />
            <StockDetailPanel
              volume={2450000}
              tradingValue={42.87}
              marketCap={16200}
              industry="Bất động sản"
            />
            <StockStatsTable
              openPrice={17.60}
              highPrice={17.70}
              lowPrice={17.45}
              tradingVolume={3400000}
              marketCap={22200}
              high52Week={19.25}
              low52Week={9.54}
              avgVolume52Week={11000000}
              eps={null}
              pe={null}
              beta={null}
              dividendYield={null}
            />
          </div>

          {/* Right: Company Info Sidebar */}
          <div className="space-y-4">
            <StockCompanyInfo
              symbol="HAG"
              industry="Sản xuất thực phẩm"
              marketCap={22200}
              outstandingShares={1.3}
              exchange={null}
              vn30Rank={null}
              description="Công ty Cổ phần Hoàng Anh Gia Lai (HAG) thành lập vào năm 1993, năm 2006 chuyển sang hoạt động động theo mô hình cổ phần. Công ty hoạt động trong lĩnh vực trồng và kinh doanh cao su, cọ dầu và các loại cây ăn quả..."
            />
          </div>
        </section>
      </div>
    </DashboardLayout>
  )
}
