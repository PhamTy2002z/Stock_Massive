/**
 * PROTOTYPE — throwaway. Fixtures for issue #21.
 *
 * Fabricated but realistically shaped payloads for one nightly Analysis. The
 * type below doubles as the concrete proposal the artifact prototype is arguing
 * for: whatever wins here is what #23's structured-output schema has to emit.
 *
 * Constraints these fixtures deliberately encode:
 *  - #24: `verdict` is a single extracted value, never a structure.
 *  - #37: every model-visible field declares kind / unit / interpretation, and
 *    the artifact carries the list of registered fields the verdict rested on.
 *    v1 `claim` is `descriptive` everywhere — no field bears a direction.
 *  - #37: `source: 'stored'` figures skip null calibration but still carry a
 *    staleness stamp; `signal` figures carry `nullFpr`.
 *  - #41: a window crossing the 2021-08-05 provider seam is `mixed` and
 *    `prepare_bars()` must refuse it — MWG's momentum field shows that hole.
 *  - map: no chart Stock 360 already owns is redrawn here.
 */

export type FieldKind = "estimator" | "percentile" | "signal"
export type FieldSource = "computed" | "stored"
export type FieldHealth = "ok" | "degraded" | "insufficient_history" | "refused"
export type AxisKey = "technical" | "fundamental" | "money_flow" | "news"
export type Emphasis = "lead" | "support" | "context"
export type Verdict = "accumulate" | "hold" | "reduce" | "avoid" | "watch"

export interface Figure {
  /** Registered field id — `<tool>.<field>`. The tool layer serializes only these. */
  id: string
  label: string
  /** Null whenever health is not `ok`. */
  value: number | string | null
  unit: string
  kind: FieldKind
  source: FieldSource
  /** #37: the only sanctioned reading of this number. */
  interpretation: string
  /** Staleness stamp. Stored provider figures are often quarters old. */
  asOf: string
  health: FieldHealth
  /** Required when health is `degraded` or `refused`. */
  reason?: string
  /** Published false-positive rate — `signal` fields only. */
  nullFpr?: number
  /** Trailing comparison the model may cite; not a forecast. */
  ownHistory?: string
}

export interface AxisSection {
  axis: AxisKey
  title: string
  /** Why this axis carries the weight it does for this industry. */
  emphasis: Emphasis
  emphasisReason: string
  /** The model's one-line read. Cites figures, never derives them. */
  read: string
  figures: Figure[]
}

export interface PriceZone {
  closeVnd: number
  /** "This symbol's ordinary daily range" — a registered computed field, not a target. */
  ordinaryLowVnd: number
  ordinaryHighVnd: number
  bandFloorVnd: number
  bandCeilingVnd: number
  bandPct: number
  basis: string
  fieldId: string
  asOf: string
}

export interface NewsItem {
  title: string
  source: string
  publishedAt: string
  url: string
}

export interface AnalysisArtifact {
  schemaVersion: number
  symbol: string
  companyName: string
  icbIndustry: string
  exchange: "HOSE" | "HNX" | "UPCOM"
  tradingDay: string
  generatedAt: string
  /** #24: one extracted value. */
  verdict: Verdict
  verdictLine: string
  /** v1 is entirely descriptive. */
  claim: "descriptive"
  thesis: string
  priceZone: PriceZone
  /** Always these four, always in this DOM order. Emphasis is what varies. */
  sections: AxisSection[]
  /** #37: exactly what the verdict rested on. */
  citedFieldIds: string[]
  windowHealth: {
    sessions: number
    adjustment: "adjusted" | "raw" | "mixed"
    limitDaysInWindow: number
    note?: string
  }
  news: NewsItem[]
  disclaimer: string
}

const DISCLAIMER =
  "Nội dung do hệ thống tạo tự động từ dữ liệu EOD, mang tính tham khảo và không phải khuyến nghị đầu tư. Mọi vùng giá là mô tả biên độ dao động thường ngày của mã, không phải mục tiêu giá."

/** Bank — fundamental leads: asset quality is the story, technicals are context. */
const VCB: AnalysisArtifact = {
  schemaVersion: 1,
  symbol: "VCB",
  companyName: "Ngân hàng TMCP Ngoại thương Việt Nam",
  icbIndustry: "Banks",
  exchange: "HOSE",
  tradingDay: "2026-08-11",
  generatedAt: "2026-08-11T17:12:04+07:00",
  verdict: "hold",
  verdictLine: "Chất lượng tài sản đi ngang, giá nằm giữa biên độ thường ngày — không có cớ để hành động gấp.",
  claim: "descriptive",
  thesis:
    "VCB đang ở trạng thái ít biến động nhất trong sáu tháng: biến động thực hiện 20 phiên ở 18,4%/năm, thấp hơn trung vị trượt của chính nó. Nền tảng vẫn là điểm mạnh — ROE ở phân vị 88 trong Universe và NIM giữ được 3,08% — nhưng NPL nhích lên 0,98% và tỷ lệ bao phủ nợ xấu giảm hai quý liên tiếp, nên phần \"mạnh\" đã hết đà mở rộng. Dòng ngoại mua ròng nhẹ, chuỗi 4 phiên, chưa đủ lớn so với ADTV để coi là một lực đỡ. Giá đóng cửa nằm gần giữa vùng dao động thường ngày, không sát biên nào.",
  priceZone: {
    closeVnd: 68400,
    ordinaryLowVnd: 66900,
    ordinaryHighVnd: 69900,
    bandFloorVnd: 63600,
    bandCeilingVnd: 73200,
    bandPct: 7,
    basis: "±1σ quanh giá đóng cửa, σ từ Yang-Zhang 20 phiên",
    fieldId: "band_pressure.ordinary_range_vnd",
    asOf: "2026-08-11",
  },
  sections: [
    {
      axis: "technical",
      title: "Technical",
      emphasis: "context",
      emphasisReason: "Biến động ở vùng thấp và không có phiên trần/sàn nào trong cửa sổ — kỹ thuật không mang thông tin quyết định cho phiên này.",
      read: "Biến động thấp hơn trung vị trượt, rút chân khỏi đáy chưa sâu, không có phiên chạm biên.",
      figures: [
        {
          id: "realized_volatility.yang_zhang_annualized_pct",
          label: "Realized volatility (20d, Yang-Zhang)",
          value: 18.4,
          unit: "%/năm",
          kind: "estimator",
          source: "computed",
          interpretation: "Độ dao động thực hiện của giá trong 20 phiên gần nhất, quy năm. Không mang dấu, không nói hướng.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "trung vị 6 tháng 24,1%/năm",
        },
        {
          id: "volatility_regime.gk_variance_robust_z",
          label: "Volatility regime (robust z)",
          value: -0.82,
          unit: "z (robust)",
          kind: "signal",
          source: "computed",
          interpretation: "Phương sai Garman-Klass so với trung vị/MAD trượt của chính mã. Dương = biến động cao hơn quá khứ gần. |z| < 2,1 không vượt ngưỡng.",
          asOf: "2026-08-11",
          health: "ok",
          nullFpr: 0.008,
          ownHistory: "ngưỡng công bố |z| ≥ 2,1",
        },
        {
          id: "drawdown_stats.current_drawdown_pct",
          label: "Current drawdown",
          value: -6.2,
          unit: "%",
          kind: "estimator",
          source: "computed",
          interpretation: "Khoảng cách từ đỉnh trượt 252 phiên tới giá hiện tại. Luôn ≤ 0.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "E[MDD] ≈ 1,25σ√T ⇒ −14,8% là mức 'bình thường' cho cửa sổ này",
        },
        {
          id: "band_pressure.limit_days_in_window",
          label: "Limit-lock days (20d)",
          value: 0,
          unit: "phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Số phiên đóng cửa tại biên trần/sàn trong cửa sổ. Bằng 0 nghĩa là các thống kê trượt không bị biên làm méo.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
    {
      axis: "fundamental",
      title: "Fundamental",
      emphasis: "lead",
      emphasisReason: "Với ngân hàng, chất lượng tài sản và NIM quyết định giá trị; đây là trục duy nhất có thay đổi thật trong kỳ.",
      read: "Sinh lời vẫn ở nhóm đầu Universe, nhưng NPL nhích lên và bao phủ nợ xấu giảm hai quý liền.",
      figures: [
        {
          id: "factor_percentiles.roe_percentile",
          label: "ROE percentile (Universe)",
          value: 88,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng ROE trong Universe tại cùng thời điểm. Cao = sinh lời trên vốn tốt hơn phần còn lại.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "quý trước phân vị 90",
        },
        {
          id: "bank_metrics.nim_pct",
          label: "NIM",
          value: 3.08,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Biên lãi thuần theo báo cáo quý của nhà cung cấp. Số của kỳ, không phải số dự phóng.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 3,21 → 3,15 → 3,11 → 3,08",
        },
        {
          id: "bank_metrics.npl_ratio_pct",
          label: "NPL ratio",
          value: 0.98,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Tỷ lệ nợ nhóm 3–5 trên tổng dư nợ, theo báo cáo quý.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 0,83 → 0,89 → 0,94 → 0,98",
        },
        {
          id: "bank_metrics.llr_coverage_pct",
          label: "Loan-loss coverage",
          value: 212,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Dự phòng rủi ro trên nợ xấu. Giảm nghĩa là đệm mỏng đi, không nói gì về xác suất tổn thất.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 246 → 233 → 224 → 212",
        },
        {
          id: "factor_percentiles.earnings_yield_percentile",
          label: "E/P percentile (Universe)",
          value: 41,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng lợi suất lợi nhuận E/P trong Universe. Cao = rẻ hơn tương đối.",
          asOf: "2026-06-30",
          health: "ok",
        },
      ],
    },
    {
      axis: "money_flow",
      title: "Money flow & foreign",
      emphasis: "support",
      emphasisReason: "Có chuỗi mua ròng nhưng quy mô nhỏ so với ADTV, nên chỉ đóng vai trò xác nhận.",
      read: "Ngoại mua ròng 4 phiên liền, tổng chỉ 0,31 lần ADTV — dai dẳng nhưng chưa nặng.",
      figures: [
        {
          id: "foreign_flow_pressure.net_value_over_adtv",
          label: "Foreign net buy / ADTV (10d)",
          value: 0.31,
          unit: "lần ADTV",
          kind: "signal",
          source: "computed",
          interpretation: "Giá trị mua ròng nước ngoài trượt 10 phiên chia ADTV. Dương = mua ròng. Chỉ mô tả mức độ dai dẳng, không dự báo lợi suất.",
          asOf: "2026-08-11",
          health: "ok",
          nullFpr: 0.009,
          ownHistory: "ngưỡng công bố |ratio| ≥ 0,75",
        },
        {
          id: "foreign_flow_pressure.persistence_run_days",
          label: "Persistence run",
          value: 4,
          unit: "phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Số phiên liên tiếp cùng dấu dòng ngoại tính tới phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
        },
        {
          id: "liquidity_profile.adtv_vnd",
          label: "ADTV (20d)",
          value: 412_000_000_000,
          unit: "VND/phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Giá trị giao dịch bình quân phiên trong 20 phiên. Là ngưỡng thanh khoản cho mọi chỉ báo khác.",
          asOf: "2026-08-11",
          health: "ok",
        },
        {
          id: "bank_metrics.foreign_room_pct",
          label: "Foreign room remaining",
          value: 0.4,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Phần còn lại của giới hạn sở hữu nước ngoài. Gần 0 nghĩa là dòng mua bị chặn bởi cơ chế, không phải bởi khẩu vị.",
          asOf: "2026-08-08",
          health: "degraded",
          reason: "Snapshot sở hữu nước ngoài cũ 3 phiên — Collector chưa cập nhật lớp reference.",
        },
      ],
    },
    {
      axis: "news",
      title: "News",
      emphasis: "context",
      emphasisReason: "Hai tin trong 7 phiên, đều là sự kiện đã lên lịch — không đổi cách đọc các trục còn lại.",
      read: "Chỉ có tin cổ tức và tin nhân sự đã công bố trước; không có sự kiện ngoài dự kiến.",
      figures: [
        {
          id: "search_news.items_7d",
          label: "Items (7d)",
          value: 2,
          unit: "tin",
          kind: "estimator",
          source: "stored",
          interpretation: "Số tin theo mã từ nguồn đã được duyệt trong 7 phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
  ],
  citedFieldIds: [
    "realized_volatility.yang_zhang_annualized_pct",
    "volatility_regime.gk_variance_robust_z",
    "factor_percentiles.roe_percentile",
    "bank_metrics.nim_pct",
    "bank_metrics.npl_ratio_pct",
    "bank_metrics.llr_coverage_pct",
    "foreign_flow_pressure.net_value_over_adtv",
    "foreign_flow_pressure.persistence_run_days",
    "band_pressure.ordinary_range_vnd",
  ],
  windowHealth: {
    sessions: 252,
    adjustment: "adjusted",
    limitDaysInWindow: 0,
  },
  news: [
    {
      title: "VCB chốt danh sách cổ đông trả cổ tức bằng tiền 800 đồng/cp",
      source: "vnstock · VCI",
      publishedAt: "2026-08-07",
      url: "#",
    },
    {
      title: "Vietcombank bổ nhiệm Phó Tổng giám đốc phụ trách khối bán lẻ",
      source: "CafeF",
      publishedAt: "2026-08-05",
      url: "#",
    },
  ],
  disclaimer: DISCLAIMER,
}

/** Real estate — money flow leads: quarterly fundamentals are stale, flow is live. */
const VHM: AnalysisArtifact = {
  schemaVersion: 1,
  symbol: "VHM",
  companyName: "Công ty CP Vinhomes",
  icbIndustry: "Real Estate Investment & Services",
  exchange: "HOSE",
  tradingDay: "2026-08-11",
  generatedAt: "2026-08-11T17:12:39+07:00",
  verdict: "reduce",
  verdictLine: "Dòng ngoại bán ròng dai dẳng gặp đòn cân nợ cao và một cửa sổ biến động đã leo thang.",
  claim: "descriptive",
  thesis:
    "Trục nặng nhất phiên này là dòng tiền: ngoại bán ròng 11 phiên liên tiếp, tổng bằng 1,42 lần ADTV — vượt ngưỡng công bố 0,75 với FPR đã hiệu chuẩn 0,9%. Cùng lúc chế độ biến động chuyển sang cao (z = +2,38), và mã đang ở mức lỗ tối đa −27,4% so với đỉnh 252 phiên, sâu hơn mốc E[MDD] ≈ −19,1% của chính cửa sổ đó. Nền tảng chỉ nói được phần cũ: nợ ròng/EBITDA 3,4 lần theo báo cáo quý II, tồn kho bất động sản chiếm 61% tổng tài sản — cả hai đều là số của 30/06 và không phản ánh gì sau đó. Giá đang nằm ở nửa dưới của vùng dao động thường ngày.",
  priceZone: {
    closeVnd: 41200,
    ordinaryLowVnd: 39300,
    ordinaryHighVnd: 43100,
    bandFloorVnd: 38300,
    bandCeilingVnd: 44100,
    bandPct: 7,
    basis: "±1σ quanh giá đóng cửa, σ từ Yang-Zhang 20 phiên",
    fieldId: "band_pressure.ordinary_range_vnd",
    asOf: "2026-08-11",
  },
  sections: [
    {
      axis: "technical",
      title: "Technical",
      emphasis: "support",
      emphasisReason: "Chế độ biến động đã vượt ngưỡng và mức lỗ sâu hơn mốc chuẩn — kỹ thuật xác nhận điều dòng tiền đang nói.",
      read: "Biến động leo thang vượt ngưỡng, lỗ tối đa sâu hơn mốc E[MDD] của cùng cửa sổ.",
      figures: [
        {
          id: "realized_volatility.yang_zhang_annualized_pct",
          label: "Realized volatility (20d, Yang-Zhang)",
          value: 43.7,
          unit: "%/năm",
          kind: "estimator",
          source: "computed",
          interpretation: "Độ dao động thực hiện của giá trong 20 phiên gần nhất, quy năm. Không mang dấu, không nói hướng.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "trung vị 6 tháng 29,8%/năm",
        },
        {
          id: "volatility_regime.gk_variance_robust_z",
          label: "Volatility regime (robust z)",
          value: 2.38,
          unit: "z (robust)",
          kind: "signal",
          source: "computed",
          interpretation: "Phương sai Garman-Klass so với trung vị/MAD trượt của chính mã. Dương = biến động cao hơn quá khứ gần. Vượt ngưỡng công bố |z| ≥ 2,1.",
          asOf: "2026-08-11",
          health: "ok",
          nullFpr: 0.008,
          ownHistory: "3 phiên liên tiếp trên ngưỡng",
        },
        {
          id: "drawdown_stats.max_drawdown_pct",
          label: "Max drawdown (252d)",
          value: -27.4,
          unit: "%",
          kind: "estimator",
          source: "computed",
          interpretation: "Mức lỗ sâu nhất từ đỉnh trong cửa sổ 252 phiên. Luôn ≤ 0.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "E[MDD] ≈ 1,25σ√T ⇒ −19,1% là mức 'bình thường'; 96 phiên dưới nước",
        },
        {
          id: "band_pressure.limit_days_in_window",
          label: "Limit-lock days (20d)",
          value: 2,
          unit: "phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Số phiên đóng cửa tại biên trần/sàn trong cửa sổ; đã loại khỏi mọi trung vị/MAD trượt.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
    {
      axis: "fundamental",
      title: "Fundamental",
      emphasis: "context",
      emphasisReason: "Toàn bộ số nền tảng là của 30/06 và không có kỳ mới nào từ đó — chỉ đóng vai trò nền, không phải nguyên nhân của phiên này.",
      read: "Đòn cân nợ và tồn kho vẫn cao, nhưng đây là số quý II — đã 42 phiên không đổi.",
      figures: [
        {
          id: "developer_metrics.net_debt_to_ebitda",
          label: "Net debt / EBITDA",
          value: 3.4,
          unit: "lần",
          kind: "estimator",
          source: "stored",
          interpretation: "Nợ ròng trên EBITDA 4 quý gần nhất theo báo cáo. Cao = đòn cân nợ nặng hơn.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 2,6 → 2,9 → 3,2 → 3,4",
        },
        {
          id: "developer_metrics.inventory_share_of_assets_pct",
          label: "Property inventory / total assets",
          value: 61,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Tỷ trọng tồn kho bất động sản trong tổng tài sản, theo báo cáo quý.",
          asOf: "2026-06-30",
          health: "ok",
        },
        {
          id: "factor_percentiles.book_yield_percentile",
          label: "B/P percentile (Universe)",
          value: 74,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng lợi suất giá trị sổ sách B/P trong Universe. Cao = rẻ hơn tương đối theo sổ sách.",
          asOf: "2026-06-30",
          health: "ok",
        },
        {
          id: "factor_percentiles.roe_percentile",
          label: "ROE percentile (Universe)",
          value: 52,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng ROE trong Universe tại cùng thời điểm.",
          asOf: "2026-06-30",
          health: "ok",
        },
      ],
    },
    {
      axis: "money_flow",
      title: "Money flow & foreign",
      emphasis: "lead",
      emphasisReason: "Đây là trục duy nhất vượt ngưỡng đã hiệu chuẩn trong phiên này, và là số duy nhất mới tới hôm nay.",
      read: "Ngoại bán ròng 11 phiên liền, 1,42 lần ADTV — vượt ngưỡng công bố 0,75.",
      figures: [
        {
          id: "foreign_flow_pressure.net_value_over_adtv",
          label: "Foreign net buy / ADTV (10d)",
          value: -1.42,
          unit: "lần ADTV",
          kind: "signal",
          source: "computed",
          interpretation: "Giá trị mua ròng nước ngoài trượt 10 phiên chia ADTV. Âm = bán ròng. Chỉ mô tả mức độ dai dẳng, không dự báo lợi suất.",
          asOf: "2026-08-11",
          health: "ok",
          nullFpr: 0.009,
          ownHistory: "ngưỡng công bố |ratio| ≥ 0,75; lần cuối vượt: 2026-03",
        },
        {
          id: "foreign_flow_pressure.persistence_run_days",
          label: "Persistence run",
          value: 11,
          unit: "phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Số phiên liên tiếp cùng dấu dòng ngoại tính tới phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "dài nhất 12 tháng: 14 phiên",
        },
        {
          id: "liquidity_profile.adtv_vnd",
          label: "ADTV (20d)",
          value: 286_000_000_000,
          unit: "VND/phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Giá trị giao dịch bình quân phiên trong 20 phiên. Là ngưỡng thanh khoản cho mọi chỉ báo khác.",
          asOf: "2026-08-11",
          health: "ok",
        },
        {
          id: "liquidity_profile.amihud_illiq",
          label: "Amihud ILLIQ",
          value: 0.041,
          unit: "%/tỷ VND",
          kind: "percentile",
          source: "computed",
          interpretation: "Tác động giá trên mỗi tỷ đồng giao dịch. Cao = kém thanh khoản hơn. Phân vị 22 trong Universe.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
    {
      axis: "news",
      title: "News",
      emphasis: "support",
      emphasisReason: "Một tin về tiến độ pháp lý dự án trùng đúng phiên dòng ngoại bắt đầu chuỗi bán.",
      read: "Một tin pháp lý dự án ngày 28/07, cùng phiên chuỗi bán ròng bắt đầu.",
      figures: [
        {
          id: "search_news.items_7d",
          label: "Items (7d)",
          value: 0,
          unit: "tin",
          kind: "estimator",
          source: "stored",
          interpretation: "Số tin theo mã từ nguồn đã được duyệt trong 7 phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
        },
        {
          id: "search_news.items_30d",
          label: "Items (30d)",
          value: 1,
          unit: "tin",
          kind: "estimator",
          source: "stored",
          interpretation: "Số tin theo mã từ nguồn đã được duyệt trong 30 phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
  ],
  citedFieldIds: [
    "foreign_flow_pressure.net_value_over_adtv",
    "foreign_flow_pressure.persistence_run_days",
    "volatility_regime.gk_variance_robust_z",
    "drawdown_stats.max_drawdown_pct",
    "developer_metrics.net_debt_to_ebitda",
    "developer_metrics.inventory_share_of_assets_pct",
    "band_pressure.ordinary_range_vnd",
  ],
  windowHealth: {
    sessions: 252,
    adjustment: "adjusted",
    limitDaysInWindow: 2,
    note: "2 phiên chạm biên đã loại khỏi baseline trung vị/MAD.",
  },
  news: [
    {
      title: "Vinhomes cập nhật tiến độ pháp lý dự án phía Đông Hà Nội",
      source: "vnstock · VCI",
      publishedAt: "2026-07-28",
      url: "#",
    },
  ],
  disclaimer: DISCLAIMER,
}

/** Retail — technical leads, and one field is refused outright by #41's seam. */
const MWG: AnalysisArtifact = {
  schemaVersion: 1,
  symbol: "MWG",
  companyName: "Công ty CP Đầu tư Thế Giới Di Động",
  icbIndustry: "General Retailers",
  exchange: "HOSE",
  tradingDay: "2026-08-11",
  generatedAt: "2026-08-11T17:13:11+07:00",
  verdict: "watch",
  verdictLine: "Biên lợi nhuận đang mở rộng nhưng bằng chứng xu hướng dài hạn không dùng được — chưa đủ cơ sở để kết luận.",
  claim: "descriptive",
  thesis:
    "Trục kỹ thuật là nơi có số mới nhất, nhưng nó khuyết một mảng: xếp hạng động lượng 12-2 cần 273 phiên và cửa sổ đó bắc qua mốc 2021-08-05, nơi chuỗi giá trong store trộn hai quy ước điều chỉnh — prepare_bars() từ chối trả về thay vì trả một con số không trung thực. Phần còn lại đọc được: biến động thực hiện 31,2%/năm ngang trung vị, mã đang rút chân từ mức lỗ −18,9%, và không có phiên chạm biên trong cửa sổ. Nền tảng là điểm sáng — biên lợi nhuận gộp 21,4%, quý thứ ba liên tiếp mở rộng, vòng quay tồn kho từ 3,9 lên 4,6 lần — nhưng cả hai là số quý II. Dòng ngoại gần như trung tính. Giá nằm ở nửa trên vùng dao động thường ngày.",
  priceZone: {
    closeVnd: 58900,
    ordinaryLowVnd: 56600,
    ordinaryHighVnd: 61200,
    bandFloorVnd: 54800,
    bandCeilingVnd: 63000,
    bandPct: 7,
    basis: "±1σ quanh giá đóng cửa, σ từ Yang-Zhang 20 phiên",
    fieldId: "band_pressure.ordinary_range_vnd",
    asOf: "2026-08-11",
  },
  sections: [
    {
      axis: "technical",
      title: "Technical",
      emphasis: "lead",
      emphasisReason: "Đây là trục có dữ liệu mới nhất và cũng là trục có lỗ hổng cần nói rõ — người đọc phải thấy chỗ khuyết trước khi tin phần còn lại.",
      read: "Biến động ngang trung vị, đang rút chân từ đáy; xếp hạng động lượng bị từ chối vì cửa sổ bắc qua mốc trộn quy ước điều chỉnh.",
      figures: [
        {
          id: "realized_volatility.yang_zhang_annualized_pct",
          label: "Realized volatility (20d, Yang-Zhang)",
          value: 31.2,
          unit: "%/năm",
          kind: "estimator",
          source: "computed",
          interpretation: "Độ dao động thực hiện của giá trong 20 phiên gần nhất, quy năm. Không mang dấu, không nói hướng.",
          asOf: "2026-08-11",
          health: "ok",
          ownHistory: "trung vị 6 tháng 30,4%/năm",
        },
        {
          id: "momentum_rank.percentile_12_2",
          label: "Momentum rank (12-2, Universe)",
          value: null,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng lợi suất 12-2 trong Universe. Cao = mã dẫn đầu.",
          asOf: "2026-08-11",
          health: "refused",
          reason: "Cửa sổ 273 phiên bắc qua mốc 2021-08-05: chuỗi trộn giá thô (FiinQuant) và giá đã điều chỉnh (vnstock VCI). WindowHealth.adjustment = mixed ⇒ prepare_bars() từ chối.",
        },
        {
          id: "drawdown_stats.current_drawdown_pct",
          label: "Current drawdown",
          value: -18.9,
          unit: "%",
          kind: "estimator",
          source: "computed",
          interpretation: "Khoảng cách từ đỉnh trượt 252 phiên tới giá hiện tại. Luôn ≤ 0.",
          asOf: "2026-08-11",
          health: "degraded",
          reason: "Cửa sổ 252 phiên chỉ có 231 phiên nằm sau mốc điều chỉnh; đỉnh tính trên phần sạch, không phải toàn cửa sổ.",
          ownHistory: "E[MDD] ≈ 1,25σ√T ⇒ −24,6% là mức 'bình thường'",
        },
        {
          id: "indicator_pack.rsi_14",
          label: "RSI(14)",
          value: 54.1,
          unit: "chỉ số 0–100",
          kind: "estimator",
          source: "computed",
          interpretation: "Chỉ dùng làm từ vựng mô tả. Không có bằng chứng thống kê sau 1986 cho RSI như một tín hiệu (Sullivan-Timmermann-White 1999).",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
    {
      axis: "fundamental",
      title: "Fundamental",
      emphasis: "support",
      emphasisReason: "Biên lợi nhuận mở rộng ba quý liền là lý do duy nhất để chưa loại mã, nhưng số đã 42 phiên không đổi.",
      read: "Biên gộp mở rộng ba quý liên tiếp, vòng quay tồn kho cải thiện rõ; toàn bộ là số quý II.",
      figures: [
        {
          id: "retail_metrics.gross_margin_pct",
          label: "Gross margin",
          value: 21.4,
          unit: "%",
          kind: "estimator",
          source: "stored",
          interpretation: "Biên lợi nhuận gộp theo báo cáo quý của nhà cung cấp.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 19,2 → 20,1 → 20,8 → 21,4",
        },
        {
          id: "retail_metrics.inventory_turnover_x",
          label: "Inventory turnover",
          value: 4.6,
          unit: "lần/năm",
          kind: "estimator",
          source: "stored",
          interpretation: "Giá vốn trên tồn kho bình quân, quy năm từ báo cáo quý. Cao = luân chuyển hàng nhanh hơn.",
          asOf: "2026-06-30",
          health: "ok",
          ownHistory: "4 quý: 3,9 → 4,1 → 4,4 → 4,6",
        },
        {
          id: "retail_metrics.store_count",
          label: "Store count",
          value: 3418,
          unit: "cửa hàng",
          kind: "estimator",
          source: "stored",
          interpretation: "Số điểm bán theo công bố của doanh nghiệp. Đổi chậm; là số reference, không phải số thị trường.",
          asOf: "2026-06-30",
          health: "insufficient_history",
          reason: "Nhà cung cấp chỉ có 2 kỳ — không đủ để nêu xu hướng, chỉ nêu mức.",
        },
        {
          id: "factor_percentiles.earnings_yield_percentile",
          label: "E/P percentile (Universe)",
          value: 29,
          unit: "phân vị 0–100",
          kind: "percentile",
          source: "computed",
          interpretation: "Xếp hạng lợi suất lợi nhuận E/P trong Universe. Thấp = đắt hơn tương đối.",
          asOf: "2026-06-30",
          health: "ok",
        },
      ],
    },
    {
      axis: "money_flow",
      title: "Money flow & foreign",
      emphasis: "context",
      emphasisReason: "Dòng ngoại gần như bằng 0 so với ADTV và không có chuỗi — không có gì để đọc.",
      read: "Dòng ngoại trung tính, 0,08 lần ADTV, không thành chuỗi.",
      figures: [
        {
          id: "foreign_flow_pressure.net_value_over_adtv",
          label: "Foreign net buy / ADTV (10d)",
          value: 0.08,
          unit: "lần ADTV",
          kind: "signal",
          source: "computed",
          interpretation: "Giá trị mua ròng nước ngoài trượt 10 phiên chia ADTV. Dưới ngưỡng công bố 0,75 — không đọc là tín hiệu.",
          asOf: "2026-08-11",
          health: "ok",
          nullFpr: 0.009,
        },
        {
          id: "liquidity_profile.adtv_vnd",
          label: "ADTV (20d)",
          value: 198_000_000_000,
          unit: "VND/phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Giá trị giao dịch bình quân phiên trong 20 phiên.",
          asOf: "2026-08-11",
          health: "ok",
        },
        {
          id: "foreign_flow_pressure.persistence_run_days",
          label: "Persistence run",
          value: 1,
          unit: "phiên",
          kind: "estimator",
          source: "computed",
          interpretation: "Số phiên liên tiếp cùng dấu dòng ngoại tính tới phiên gần nhất.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
    {
      axis: "news",
      title: "News",
      emphasis: "context",
      emphasisReason: "Không có tin nào từ nguồn đã duyệt trong 30 phiên — trục này không nói gì cho phiên này.",
      read: "Không có tin nào từ nguồn đã duyệt trong 30 phiên gần nhất.",
      figures: [
        {
          id: "search_news.items_30d",
          label: "Items (30d)",
          value: 0,
          unit: "tin",
          kind: "estimator",
          source: "stored",
          interpretation: "Số tin theo mã từ nguồn đã được duyệt trong 30 phiên gần nhất. Bằng 0 là 'không có tin', không phải 'không tìm được'.",
          asOf: "2026-08-11",
          health: "ok",
        },
      ],
    },
  ],
  citedFieldIds: [
    "realized_volatility.yang_zhang_annualized_pct",
    "drawdown_stats.current_drawdown_pct",
    "retail_metrics.gross_margin_pct",
    "retail_metrics.inventory_turnover_x",
    "foreign_flow_pressure.net_value_over_adtv",
    "band_pressure.ordinary_range_vnd",
  ],
  windowHealth: {
    sessions: 231,
    adjustment: "mixed",
    limitDaysInWindow: 0,
    note: "Chuỗi bắc qua mốc 2021-08-05; mọi cửa sổ dài hơn 231 phiên bị prepare_bars() từ chối.",
  },
  news: [],
  disclaimer: DISCLAIMER,
}

export const ARTIFACTS: Record<string, AnalysisArtifact> = { VCB, VHM, MWG }
export const SYMBOLS = ["VCB", "VHM", "MWG"] as const

export const AXIS_ORDER: AxisKey[] = ["technical", "fundamental", "money_flow", "news"]

/** Fixed DOM order; only `emphasis` differs between industries. */
export function orderedSections(a: AnalysisArtifact): AxisSection[] {
  return AXIS_ORDER.map((k) => a.sections.find((s) => s.axis === k)!).filter(Boolean)
}

/** Emphasis order, for the variants that let the model lead with an axis. */
const EMPHASIS_RANK: Record<Emphasis, number> = { lead: 0, support: 1, context: 2 }
export function byEmphasis(a: AnalysisArtifact): AxisSection[] {
  return [...orderedSections(a)].sort(
    (x, y) => EMPHASIS_RANK[x.emphasis] - EMPHASIS_RANK[y.emphasis]
  )
}

export function formatValue(f: Figure): string {
  if (f.value === null) return "—"
  if (typeof f.value === "string") return f.value
  if (f.unit === "VND/phiên") return `${(f.value / 1_000_000_000).toFixed(0)} tỷ`
  if (Number.isInteger(f.value)) return f.value.toLocaleString("vi-VN")
  return f.value.toLocaleString("vi-VN", { maximumFractionDigits: 3 })
}

export function formatVnd(n: number): string {
  return n.toLocaleString("vi-VN")
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  accumulate: "Accumulate",
  hold: "Hold",
  reduce: "Reduce",
  avoid: "Avoid",
  watch: "Watch",
}
