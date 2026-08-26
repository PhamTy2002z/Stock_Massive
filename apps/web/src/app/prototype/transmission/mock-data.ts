/**
 * PROTOTYPE — throwaway. Số liệu minh hoạ, không phải dữ liệu thật.
 *
 * Ba variant của màn hình Transmission Lab, đổi bằng `?variant=`.
 * Không gọi API, không persist. State nằm trong memory.
 */

export type Tier = "registered_field" | "extracted_filing" | "derived" | "unknown";

export type Evidence = {
  label: string;
  value: string;
  tier: Tier;
  formula?: string;
  numerator?: string;
  denominator?: string;
  doc: string;
  page: string;
  period: string;
  published: string;
  observed: string;
  reviewed: string | null;
  revisedFrom?: { value: string; observed: string };
};

export type BankExposure = {
  ticker: string;
  name: string;
  wholesale: number | null;
  casa: number | null;
  sensitivity: "nhạy nhất" | "trung tính" | "được che" | "ít ảnh hưởng" | "không rõ";
  impactBps: [number, number] | null;
  weight: number | null;
};

export type Verification = {
  expectedAt: string;
  source: string;
  confirmIf: string;
  refuteIf: string;
  writtenAt: string;
};

export type Card = {
  id: string;
  /** Tiêu đề ngắn, tiếng Việt thường — thứ đọc được khi liếc. */
  title: string;
  /** Một câu giải thích hệ quả, không dùng từ chuyên môn. */
  plainSummary: string;
  /** Ai trong danh mục bị ảnh hưởng, nói bằng câu. */
  plainWho: string;
  state: "active" | "challenged" | "confirmed" | "invalidated";
  confidence: number;
  confidencePrev: number;
  trigger: { text: string; knownAt: string };
  mechanism: { chain: string[]; sign: "+" | "−"; condition: string };
  exposures: BankExposure[];
  impact: string;
  lag: string;
  counterforces: string[];
  verification: Verification;
  edge: { id: string; label: string; checked: number; right: number; brier: number };
  evidence: Record<string, Evidence>;
};

export const REGIME = [
  { label: "Áp lực tỷ giá", dir: "up" as const, detail: "USD/VND +1,8% từ đầu quý" },
  { label: "Thanh khoản", dir: "tight" as const, detail: "ON liên NH 4,85% (4 tuần)" },
  { label: "Xung lực tín dụng", dir: "up" as const, detail: "+11,2% YTD toàn hệ thống" },
];

export const REGIME_CONFIDENCE = 72;

export const PORTFOLIO = [
  { ticker: "MBB", weight: 25 },
  { ticker: "VCB", weight: 20 },
  { ticker: "TCB", weight: 15 },
  { ticker: "VPB", weight: 15 },
  { ticker: "ACB", weight: 10 },
  { ticker: "Khác", weight: 15 },
];

const casaEvidence = (
  t: string, v: string, num: string, den: string, page: string, reviewed: string | null,
): Evidence => ({
  label: `CASA ${t}`,
  value: v,
  tier: "extracted_filing",
  formula: "tiền gửi không kỳ hạn / tổng tiền gửi khách hàng",
  numerator: num,
  denominator: den,
  doc: `BCTC Q2/2026 hợp nhất — ${t}`,
  page,
  period: "30/06/2026",
  published: "29/07/2026",
  observed: "30/07/2026",
  reviewed,
});

export const CARDS: Card[] = [
  {
    id: "nim-funding",
    title: "Chi phí huy động đang tăng",
    plainSummary:
      "Tỷ giá căng khiến Ngân hàng Nhà nước hút bớt tiền đồng về. Thanh khoản liên ngân hàng thắt lại, nên ngân hàng nào phải đi vay nhiều trên thị trường này sẽ chịu chi phí vốn cao hơn trong 1–2 quý tới.",
    plainWho:
      "VPB chịu ảnh hưởng rõ nhất. TCB ở mức trung bình. MBB và VCB gần như không, nhờ tiền gửi không kỳ hạn cao.",
    state: "active",
    confidence: 74,
    confidencePrev: 61,
    trigger: {
      text: "Lãi suất liên ngân hàng qua đêm, bình quân 4 tuần: 4,85% (từ 3,20%)",
      knownAt: "25/08/2026, 17:00",
    },
    mechanism: {
      chain: [
        "Tỷ giá USD/VND chịu áp lực",
        "Ngân hàng Nhà nước hút bớt tiền đồng về để giữ tỷ giá",
        "Thanh khoản giữa các ngân hàng thắt lại, lãi suất vay lẫn nhau tăng",
        "Ngân hàng phụ thuộc nguồn vay này phải trả chi phí vốn cao hơn",
        "Biên lãi ròng thu hẹp, lợi nhuận giảm theo",
      ],
      sign: "−",
      condition: "Chỉ hiệu lực khi huy động bán buôn > 15% và CASA không bù được",
    },
    exposures: [
      { ticker: "VPB", name: "VPBank", wholesale: 23, casa: 14, sensitivity: "nhạy nhất", impactBps: [-35, -15], weight: 15 },
      { ticker: "TCB", name: "Techcombank", wholesale: 18, casa: 37, sensitivity: "trung tính", impactBps: [-15, -5], weight: 15 },
      { ticker: "MBB", name: "MB Bank", wholesale: 12, casa: 39, sensitivity: "được che", impactBps: [-8, 0], weight: 25 },
      { ticker: "VCB", name: "Vietcombank", wholesale: 9, casa: 32, sensitivity: "ít ảnh hưởng", impactBps: [-5, 0], weight: 20 },
      { ticker: "ACB", name: "ACB", wholesale: null, casa: null, sensitivity: "không rõ", impactBps: null, weight: 10 },
    ],
    impact: "NIM: −15 đến −35 bps (VPB), −5 đến −15 bps (TCB)",
    lag: "1–2 quý · Sự kiện T8/2026 → phản ánh BCTC Q4/2026",
    counterforces: [
      "CASA tăng theo mùa cuối năm",
      "Tài sản tái định giá nhanh hơn nguồn vốn",
      "Cạnh tranh huy động yếu đi nếu tín dụng chậm lại",
    ],
    verification: {
      expectedAt: "30/10/2026",
      source: "BCTC Q3/2026",
      confirmIf: "Chi phí vốn VPB tăng > 20 bps so với Q2",
      refuteIf: "CASA VPB tăng > 3 điểm % HOẶC chi phí vốn đi ngang/giảm",
      writtenAt: "25/08/2026",
    },
    edge: { id: "liq-cof", label: "thanh khoản chặt → chi phí vốn ↑", checked: 5, right: 4, brier: 0.18 },
    evidence: {
      "VPB.casa": casaEvidence("VPB", "14,1%", "48.902 tỷ", "346.821 tỷ", "tr.51, Thuyết minh 19", "30/07/2026"),
      "TCB.casa": casaEvidence("TCB", "37,2%", "84.312 tỷ", "226.640 tỷ", "tr.47, Thuyết minh 18, dòng 2", "30/07/2026"),
      "MBB.casa": casaEvidence("MBB", "39,4%", "112.083 tỷ", "284.474 tỷ", "tr.44, Thuyết minh 17", "30/07/2026"),
      "VCB.casa": casaEvidence("VCB", "32,0%", "418.220 tỷ", "1.306.940 tỷ", "tr.62, Thuyết minh 21", "31/07/2026"),
      "interbank": {
        label: "Lãi suất liên NH qua đêm (bình quân 4 tuần)",
        value: "4,85%",
        tier: "registered_field",
        formula: "trung bình cộng lãi suất ON, 20 phiên gần nhất",
        doc: "NHNN — Thống kê thị trường liên ngân hàng",
        page: "Bảng 1, cột ON",
        period: "28/07 – 22/08/2026",
        published: "25/08/2026",
        observed: "25/08/2026",
        reviewed: null,
        revisedFrom: { value: "4,79%", observed: "22/08/2026" },
      },
    },
  },
  {
    id: "property-asset",
    title: "Bất động sản chậm lại, nợ xấu có thể nhích lên",
    plainSummary:
      "Giao dịch nhà đất TP.HCM giảm 18% so với cùng kỳ. Chủ đầu tư thu tiền chậm hơn, nên ngân hàng cho vay nhóm này có thể phải trích lập dự phòng nhiều hơn từ cuối năm.",
    plainWho:
      "TCB có tỷ trọng cho vay chủ đầu tư cao nhất trong danh mục. VCB gần như không liên quan.",
    state: "challenged",
    confidence: 48,
    confidencePrev: 55,
    trigger: { text: "Số căn giao dịch TP.HCM Q2: −18% so với cùng kỳ", knownAt: "18/08/2026, 09:00" },
    mechanism: {
      chain: [
        "Giao dịch nhà đất chậm lại",
        "Chủ đầu tư thu tiền về chậm hơn dự kiến",
        "Khoản vay chuyển sang nhóm nợ cần chú ý",
        "Ngân hàng phải trích lập dự phòng nhiều hơn",
      ],
      sign: "−",
      condition: "Chỉ hiệu lực khi dư nợ chủ đầu tư + trái phiếu BĐS > 8% tổng dư nợ",
    },
    exposures: [
      { ticker: "TCB", name: "Techcombank", wholesale: null, casa: null, sensitivity: "nhạy nhất", impactBps: null, weight: 15 },
      { ticker: "VPB", name: "VPBank", wholesale: null, casa: null, sensitivity: "trung tính", impactBps: null, weight: 15 },
      { ticker: "VCB", name: "Vietcombank", wholesale: null, casa: null, sensitivity: "ít ảnh hưởng", impactBps: null, weight: 20 },
    ],
    impact: "Chi phí tín dụng: +10 đến +30 bps (nhóm nhạy)",
    lag: "2 quý",
    counterforces: [
      "Pháp lý dự án được tháo gỡ nhanh hơn dự kiến",
      "Giá trị tài sản bảo đảm giữ được mặt bằng",
    ],
    verification: {
      expectedAt: "30/10/2026",
      source: "BCTC Q3/2026 — thuyết minh phân loại nợ",
      confirmIf: "Nợ nhóm 2 TCB tăng > 15% so với Q2",
      refuteIf: "Nợ nhóm 2 đi ngang hoặc giảm",
      writtenAt: "18/08/2026",
    },
    edge: { id: "prop-npl", label: "giao dịch BĐS ↓ → nợ nhóm 2 ↑", checked: 3, right: 2, brier: 0.31 },
    evidence: {},
  },
];

export type Outcome = "confirmed" | "invalidated" | "closed";

export const RESOLVED = [
  {
    id: "r1",
    title: "Áp lực NIM VPB — Q1/2026",
    outcome: "invalidated" as Outcome,
    writtenAt: "12/05/2026",
    resolvedAt: "30/07/2026",
    reason: "CASA VPB tăng 4,0 điểm % — phản lực ① thắng",
    edgeBefore: 74,
    edgeAfter: 61,
  },
  {
    id: "r2",
    title: "Chi phí vốn hệ thống — Q4/2025",
    outcome: "confirmed" as Outcome,
    writtenAt: "05/11/2025",
    resolvedAt: "28/01/2026",
    reason: "Chi phí vốn nhóm nhạy +26 bps, vượt ngưỡng 20 bps",
    edgeBefore: 58,
    edgeAfter: 71,
  },
  {
    id: "r3",
    title: "Room tín dụng → tăng trưởng cho vay",
    outcome: "closed" as Outcome,
    writtenAt: "20/02/2026",
    resolvedAt: "29/04/2026",
    reason: "Không ngân hàng nào công bố hạn mức tín dụng được cấp, nên luận điểm này không có cách nào chấm đúng hay sai. Đã đóng.",
    edgeBefore: 40,
    edgeAfter: 0,
  },
];

export const CALENDAR = [
  { date: "28/08/2026", label: "NHNN — thống kê tiền tệ tháng 7", kind: "macro" as const },
  { date: "06/09/2026", label: "NSO — CPI tháng 8", kind: "macro" as const },
  { date: "30/10/2026", label: "BCTC Q3 — 6 ngân hàng", kind: "filing" as const, cards: 2 },
  { date: "15/11/2026", label: "NHNN — NPL hệ thống Q3", kind: "macro" as const },
];
