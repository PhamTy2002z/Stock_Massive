const TICKERS = [
  { symbol: "HPG", value: "+1.44%", trend: "up" },
  { symbol: "VCB", value: "-0.65%", trend: "down" },
  { symbol: "MWG", value: "+3.02%", trend: "up" },
  { symbol: "SSI", value: "-0.41%", trend: "down" },
  { symbol: "VNM", value: "+0.72%", trend: "up" },
  { symbol: "TCB", value: "-1.12%", trend: "down" },
] as const

const SECTORS = [
  { name: "Ngân hàng", value: "+1.24%", className: "col-span-4 bg-positive/[0.22]" },
  { name: "Bất động sản", value: "-0.88%", className: "col-span-2 bg-negative/[0.22]" },
  { name: "Thép", value: "+1.96%", className: "col-span-2 bg-positive/[0.28]" },
  { name: "Công nghệ", value: "+2.41%", className: "col-span-2 bg-positive/[0.28]" },
  { name: "Bán lẻ", value: "+0.54%", className: "col-span-2 bg-positive/[0.14]" },
  { name: "Chứng khoán", value: "-0.47%", className: "col-span-2 bg-negative/[0.16]" },
  { name: "Dầu khí", value: "+1.70%", className: "col-span-2 bg-positive/[0.22]" },
] as const

const FLOW_BARS = [16, 26, 9, -14, 30, 19, -8, 37, 25, 13, -21, 28, 38, 18, -10, 32, 24, -5, 34, 28]

export default function MarketShowcase() {
  return (
    <aside className="hidden min-h-dvh flex-col overflow-hidden bg-surface-panel px-12 pb-10 pt-20 text-foreground lg:flex" aria-hidden="true">
      <div className="relative mb-3 h-7 overflow-hidden rounded-full bg-surface-sunken font-mono text-xs font-semibold">
        <div className="absolute inset-y-0 flex min-w-max animate-auth-tape items-center gap-8 px-7 motion-reduce:animate-none">
          {[...TICKERS, ...TICKERS].map((ticker, index) => (
            <span key={`${ticker.symbol}-${index}`} className="flex gap-3">
              <span>{ticker.symbol}</span>
              <span className={ticker.trend === "up" ? "text-positive" : "text-negative"}>{ticker.value}</span>
            </span>
          ))}
        </div>
      </div>

      <section className="rounded-3xl bg-surface-raised p-7">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold">VN-INDEX</h2>
            <div className="mt-1 flex items-baseline gap-3">
              <span className="font-mono text-[34px] font-bold leading-tight tracking-[-0.04em]">1,287.42</span>
              <span className="font-mono text-sm font-semibold text-positive">+0.86%</span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-ink-4" aria-label="Khung thời gian">
            <span className="rounded-full bg-foreground/[0.1] px-4 py-2.5 text-foreground">1D</span>
            <span className="px-2 py-2.5">1M</span>
            <span className="px-2 py-2.5">1Y</span>
          </div>
        </div>

        <figure className="mt-5" aria-label="VN-INDEX tăng 0.86 phần trăm trong ngày">
          <svg viewBox="0 0 560 86" className="h-[86px] w-full" role="img">
            <title>Biểu đồ VN-INDEX trong ngày</title>
            <path d="M0 66 L40 61 L80 69 L120 52 L160 57 L200 43 L240 48 L280 33 L320 39 L360 26 L400 31 L440 20 L480 25 L520 15 L560 18 L560 86 L0 86 Z" className="fill-primary" opacity="0.12" />
            <path d="M0 66 L40 61 L80 69 L120 52 L160 57 L200 43 L240 48 L280 33 L320 39 L360 26 L400 31 L440 20 L480 25 L520 15 L560 18" fill="none" className="stroke-primary" strokeWidth="2" />
          </svg>
          <div className="flex justify-between font-mono text-xs text-ink-4">
            <span>09:15</span><span>11:30</span><span>14:45</span>
          </div>
        </figure>

        <div className="mt-4 flex gap-6 border-t border-border pt-4 text-sm text-ink-4">
          <span>GTGD <strong className="font-mono text-foreground">21.480 tỷ</strong></span>
          <span>Khối ngoại <strong className="font-mono text-positive">+412 tỷ</strong></span>
          <span>P/E <strong className="font-mono text-foreground">13.8x</strong></span>
        </div>
      </section>

      <section className="mt-3.5 rounded-3xl bg-surface-raised px-7 py-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-4">Bản đồ ngành</h2>
          <span className="text-sm text-ink-4">theo vốn hoá · % thay đổi</span>
        </div>
        <div className="grid grid-cols-8 gap-1.5">
          {SECTORS.map((sector) => (
            <div key={sector.name} className={`rounded-xl px-3 py-2 ${sector.className}`}>
              <div className="text-xs font-semibold">{sector.name}</div>
              <div className={`mt-0.5 font-mono text-xs font-semibold ${sector.value.startsWith("+") ? "text-positive" : "text-negative"}`}>{sector.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-3.5 rounded-3xl bg-surface-raised px-7 py-6">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-4">Dòng tiền khối ngoại · 20 phiên</h2>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="font-mono text-[28px] font-bold text-positive">+3.140</span>
              <span className="text-sm text-ink-4">tỷ ròng</span>
            </div>
          </div>
          <div className="flex gap-3 font-mono text-xs"><span className="text-positive">14 mua</span><span className="text-negative">6 bán</span></div>
        </div>
        <div className="mt-3 flex h-14 items-center gap-1.5" aria-label="14 phiên mua ròng, 6 phiên bán ròng">
          {FLOW_BARS.map((value, index) => (
            <span
              key={index}
              className={`flex-1 rounded-sm ${value >= 0 ? "bg-positive" : "bg-negative"}`}
              style={{ height: `${Math.abs(value)}px`, transform: value < 0 ? "translateY(50%)" : "translateY(-50%)" }}
            />
          ))}
        </div>
      </section>
    </aside>
  )
}
