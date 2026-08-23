# VisgniteAI — Product & AI Platform Blueprint

> Tài liệu tổng hợp toàn bộ định hướng sản phẩm, UI/UX, AI architecture và roadmap đã brainstorm cho VisgniteAI.
>
> Mục tiêu: xây dựng một **AI-native financial intelligence workspace cho thị trường chứng khoán**, trong đó AI Chat, dữ liệu thị trường, tin tức và Portfolio AI dùng chung một lớp context/intelligence thay vì tồn tại như các module rời rạc.

---

# 1. Product Vision

VisgniteAI không nên được định vị đơn giản là:

> Chatbot + bảng giá + tin tức.

North Star phù hợp hơn là:

> **Một financial intelligence workspace giúp nhà đầu tư hiểu thị trường, hiểu cổ phiếu và hiểu điều đó có ý nghĩa gì đối với chính danh mục của họ.**

Product progression:

```text
MARKET
What happened?
    ↓

NEWS
Why did it happen?
    ↓

AI
What does it mean?
    ↓

PORTFOLIO
What does it mean for me?
```

Ba lớp đầu tạo nền móng.

Portfolio AI là phần Core và là nơi có khả năng tạo moat lớn nhất.

---

# 2. Ba module chính

Hệ thống được chia thành 3 khu vực sản phẩm chính:

## 2.1. AI Chat

Trải nghiệm tương tự Claude.ai / ChatGPT / Grok nhưng chuyên biệt cho chứng khoán.

Use cases:

- Hỏi tình hình thị trường.
- Phân tích một mã.
- So sánh nhiều mã.
- Hỏi về ngành.
- Hỏi về một tin cụ thể.
- Hỏi nguyên nhân biến động.
- Hỏi về dữ liệu tài chính.
- Hỏi về chính danh mục của user.
- Deep research một doanh nghiệp.
- Giải thích thuật ngữ và số liệu.

AI Chat không nên là một module độc lập.

Nó phải trở thành **cửa vào chung của toàn bộ intelligence layer**.

---

## 2.2. Thị trường / Bảng giá

Nhiệm vụ:

> Giúp user hiểu **đang xảy ra chuyện gì** trên thị trường.

Bao gồm:

- VN-INDEX.
- VN30.
- HNX-INDEX.
- UPCOM-INDEX.
- Market breadth.
- Sector performance.
- Liquidity.
- Foreign flow.
- Top movers.
- VN30 board.
- Watchlist.
- Symbol search.
- Stock detail.

Không nên chỉ là "bảng giá".

Hướng phát triển nên là:

> **Market Intelligence Dashboard**

---

## 2.3. Portfolio AI

Đây là Core.

Mỗi user có thể đưa tối đa khoảng 5 mã vào danh mục ban đầu.

Nhưng sản phẩm không nên dừng ở:

> "AI viết 5 bài phân tích về 5 mã."

Nên biến nó thành:

> **AI Portfolio Intelligence Engine**

Luồng tư duy chính:

```text
Tôi đang nắm cái gì?
        ↓
Điều gì đang thay đổi?
        ↓
Nó ảnh hưởng danh mục tôi như thế nào?
        ↓
Tôi cần chú ý điều gì?
```

---

# 3. Product Architecture tổng thể

Ba surface chính không được hoạt động như ba island.

```text
                       VISGNITE
                          │
            ┌─────────────┴─────────────┐
            │                           │
         App Shell                 User Context
            │
     ┌──────┼───────────┐
     │      │           │
     AI   Market     Portfolio
     │      │           │
     └──────┼───────────┘
            │
          News
            │
            ▼

      Intelligence Layer
            │
   ┌────────┼──────────────┐
   │        │              │
Market    News       Fundamentals
Data      Data          Data
   │        │              │
   └────────┼──────────────┘
            │
       Feature Layer
            │
       Quant / Risk
            │
       AI Tool Layer
            │
       Agent Runtime
            │
           LLM
```

---

# 4. Information Architecture / Sidebar

UI hiện tại đã có foundation tốt:

- dark theme,
- sidebar cố định,
- whitespace nhiều,
- typography premium,
- số liệu mono,
- màu xanh/đỏ restrained.

Không nên redesign toàn bộ.

## Navigation đề xuất

Thay cụm:

```text
[ Hỏi đáp ] [ Bảng giá ]
```

bằng:

```text
[ Hỏi AI ] [ Thị trường ] [ Danh mục ]
```

Ba tab này tương ứng với ba intent chính:

```text
HỎI AI
"Phân tích cái này cho tôi"

THỊ TRƯỜNG
"Đang xảy ra chuyện gì?"

DANH MỤC
"Nó ảnh hưởng gì tới tôi?"
```

Sidebar gợi ý:

```text
⚡ VisgniteAI

[ Hỏi AI ] [ Thị trường ] [ Danh mục ]

+ Trò chuyện mới

Khám phá
├ Tin tức
├ Bộ lọc cổ phiếu
└ Báo cáo

Mã theo dõi                   3/10 +
● STB   74.700   +0.27%   •
● VHM   71.700   +3.17%
● BID   36.900   +2.93%

Gần đây
├ Phân tích MBB
├ VNINDEX hôm qua
└ ...
```

## Watchlist và Portfolio phải tách rõ

Watchlist:

> User quan tâm mã này.

Portfolio:

> User thật sự đang sở hữu mã này.

Không nên merge.

---

# 5. Context System — Primitive quan trọng nhất

Một trong những primitive nên build ngay từ đầu:

```text
Context

type:
market | symbol | news | sector | portfolio

id:
VNINDEX | STB | news_123 | banking | portfolio_abc
```

Mọi surface đều có thể tạo context.

Ví dụ:

- Click STB → `symbol: STB`
- Click một bài báo → `news: 123`
- Click ngành ngân hàng → `sector: banking`
- Click Portfolio → `portfolio: current_user`

Sau đó AI Chat nhận context này.

---

# 6. Context Chips trong AI Chat

Ví dụ:

```text
┌─────────────────────────────────────────┐
│ [ STB × ] [ Tin NHNN × ]               │
│                                         │
│ Tin này ảnh hưởng thế nào?              │
│                                         │
│ +                           Visgnite Pro │
└─────────────────────────────────────────┘
```

Sau này:

```text
[ Danh mục của tôi × ]
```

User hỏi:

> Tin này ảnh hưởng gì tới tôi?

AI đã có đầy đủ context.

Đây là cách nối Chat + Market + News + Portfolio thành một sản phẩm.

---

# 7. AI Chat — phát triển từ UI hiện tại

Landing hiện tại đã có cảm giác Claude/ChatGPT.

Nhưng không nên để phần dưới prompt quá trống.

## Landing đề xuất

```text
                    Rise and shine

        ┌─────────────────────────────┐
        │ Hỏi về thị trường...        │
        │                             │
        │ +              Visgnite Pro │
        └─────────────────────────────┘

      VNINDEX +1.95%  VN30 +2.16%

─────────────────────────────────────────

Hôm nay trên thị trường

┌─────────────────┐ ┌─────────────────┐
│ VNINDEX          │ │ Khối ngoại      │
│ +1.95%           │ │ -1,240 tỷ       │
│ Thanh khoản ↑    │ │ Bán ròng mạnh   │
└─────────────────┘ └─────────────────┘

Có thể bạn muốn hỏi

[ Vì sao VNINDEX tăng mạnh hôm nay? ]
[ Ngành nào đang dẫn dắt? ]
[ Phân tích STB ]
[ Tin quan trọng nhất hôm nay ]
```

Chat landing chỉ nên có **market awareness nhẹ**, không copy nguyên dashboard.

---

# 8. AI response không nên chỉ là text

Một trong những hướng differentiation quan trọng nhất:

> AI phải render **financial-native UI blocks**, không chỉ trả markdown.

Ví dụ user hỏi:

> Phân tích STB.

AI có thể render:

```text
STB — Sacombank
74,700    +0.27%

AI VIEW
Tích cực
Confidence 78%

────────────────────────

Key drivers
↑ KQKD cải thiện
↑ Dòng tiền tích cực
↑ Banking sector mạnh

Risk
↓ Valuation không còn quá rẻ
↓ Resistance 76–78

────────────────────────

Giá       74.7
P/B       1.42x
ROE       ...

Nguồn
HOSE · BCTC Q2 · ...
```

---

# 9. Bộ AI Blocks

Frontend nên có component system riêng:

```text
<StockQuote />
<StockSummary />
<MarketSummary />
<NewsCard />
<NewsCluster />
<FinancialMetrics />
<PriceChart />
<SectorPerformance />
<ForeignFlow />
<TechnicalSignal />
<ValuationCard />
<ComparisonTable />
<RiskCard />
<SourceCitation />
<PortfolioSummary />
<PositionAnalysis />
```

Backend trả structured output thay vì raw HTML:

```json
{
  "answer": "...",
  "blocks": [
    {
      "type": "stock_quote",
      "symbol": "STB"
    },
    {
      "type": "technical_signal",
      "symbol": "STB"
    }
  ]
}
```

Frontend chịu trách nhiệm render.

---

# 10. Market / Bảng giá

Layout hiện tại:

- Index cards.
- Sector heatmap.
- Liquidity.
- Foreign flow.
- VN30 board.

Foundation tốt.

Không cần thay cấu trúc mạnh.

## Mục tiêu mới

Từ:

> Market Data Dashboard

sang:

> **Market Intelligence Dashboard**

---

# 11. Market Pulse

Thêm một AI summary layer nhẹ:

```text
THỊ TRƯỜNG HÔM NAY

Tích cực                         AI Summary
████████░░  78 / 100

VNINDEX       +1.95%
Breadth       312 ↑ / 98 ↓
Liquidity     1.18x avg
Foreign       -1,240 tỷ

AI
Dòng tiền lan tỏa mạnh với chứng khoán và
ngân hàng dẫn dắt. Tuy nhiên khối ngoại tiếp
tục bán ròng lớn.

[ Hỏi AI về phiên hôm nay ]
```

Bridge trực tiếp giữa Market và AI.

---

# 12. Sector Heatmap

Heatmap hiện tại đẹp nhưng có thể tăng độ trực quan:

- intensity theo % change,
- size card theo market cap hoặc trading value,
- hiển thị vài mã dẫn dắt trong card.

Ví dụ:

```text
┌───────────────────────┐
│ Chứng khoán           │
│ +4.5%                 │
│ SSI +5.1   VND +4.8   │
└───────────────────────┘
```

Click một ngành:

```text
NGÂN HÀNG

+2.1%

18 tăng
2 giảm
1 tham chiếu

Leading
STB +4.2%
MBB +3.6%
TCB +3.1%

AI Market Insight
...

[ Hỏi AI về ngành ngân hàng ]
```

---

# 13. Bảng giá tương tác

Click/hover một row có quick panel:

```text
STB

74,700
+0.27%

Today
╭──────── chart ────────╮
╰───────────────────────╯

Volume        18.2M
Foreign       +96 tỷ
P/B           1.42

[ Chi tiết ]   [ Hỏi AI ]
```

Mục tiêu:

- exploration nhanh,
- giảm page switching,
- AI luôn available.

---

# 14. Universal Search

Nút "Chi tiết mã" không nên là navigation button.

Nên chuyển thành:

```text
⌘ K  Tìm mã
```

Search toàn app:

```text
Tìm mã, công ty, tin tức...

STB
Sacombank

Tin tức
Sacombank công bố...

Chủ đề
Ngân hàng
```

Một universal search engine tốt hơn nhiều search riêng lẻ.

---

# 15. Stock Detail

Dù MVP có ba module, UX thực tế vẫn cần Stock Detail như một contextual destination.

Structure:

```text
STB
Sacombank

74,700
+200 (+0.27%)

[ Tổng quan ]
[ Biểu đồ ]
[ Tài chính ]
[ Tin tức ]
[ Phân tích AI ]
```

## Tổng quan

```text
STB

74,700  +0.27%

AI View
Tích cực · 78%

────────────────────

Chart

────────────────────

Market stats

Open
High
Low
Volume
Foreign flow

────────────────────

Fundamentals

Market Cap
P/E
P/B
ROE

────────────────────

Latest news

────────────────────

[ Hỏi AI về STB ]
```

Stock Detail là foundation trực tiếp cho Portfolio AI.

---

# 16. News UI — đánh giá hiện tại

News UI hiện tại có identity tốt:

> financial publication / editorial magazine.

Điểm mạnh:

- hero story rõ hierarchy,
- typography premium,
- article reader đẹp,
- right rail có VNINDEX context,
- category navigation rõ,
- "Bài gốc" hữu ích.

Không nên redesign thành dashboard card dày đặc.

Nên giữ khoảng 80–90% visual structure hiện tại.

Điểm còn thiếu:

> **AI Market Intelligence Layer**

---

# 17. News Home — AI Brief

Ngay dưới category navigation có thể thêm một strip mỏng:

```text
✦ AI Brief   Ngân hàng dẫn dắt · Thanh khoản ↑ · Khối ngoại bán ròng
                                                       Xem tổng quan →
```

Hoặc:

```text
AI BRIEF · 23/08

Thị trường hôm nay     TÍCH CỰC ↑

VN-Index tăng mạnh nhờ ngân hàng và chứng khoán,
trong khi khối ngoại tiếp tục bán ròng.

5 câu chuyện đáng chú ý     [Xem brief]
```

Không cần phá editorial layout.

---

# 18. News Home — Right Rail

VNINDEX card hiện tại nên giữ.

Phần right rail có thể phát triển từ:

> Bài viết mới nhất

thành:

```text
ĐANG TÁC ĐỘNG

↑ Ngân hàng kéo VNINDEX
  8 nguồn · 14 phút

↓ Khối ngoại bán ròng mạnh
  5 nguồn · 21 phút

↑ Nhóm chứng khoán bứt phá
  11 nguồn · 34 phút
```

Sau đó mới đến:

> Bài viết mới nhất.

---

# 19. Article != Story

Backend không nên xem mỗi article là một event độc lập.

Ví dụ 10 báo cùng viết về một sự kiện:

```text
CafeF
VnExpress
Vietstock
Reuters
...
```

Nên cluster thành:

```text
Story:
"Ngân hàng tăng mạnh trong phiên 23/08"

├ CafeF article
├ VnExpress article
├ Vietstock article
├ SSI commentary
└ ...
```

Frontend có thể hiển thị:

```text
6 nguồn đang đưa tin
```

Điều này quan trọng cho:

- deduplication,
- credibility,
- AI evidence,
- causal reasoning,
- portfolio event detection.

---

# 20. News Pipeline

```text
News Sources
     │
     ▼
Ingestion
     │
     ▼
Normalize
     │
     ├ source
     ├ timestamp
     ├ canonical URL
     └ content
     │
     ▼
Deduplication
     │
     ▼
Story Clustering
     │
     ▼
Entity Extraction
     │
     ├ company
     ├ ticker
     ├ sector
     └ macro entities
     │
     ▼
AI Intelligence
     │
     ├ summary
     ├ key facts
     ├ sentiment
     ├ market relevance
     ├ potential impact
     └ relationships
     │
     ▼
News API
```

---

# 21. Entity / Ticker Tagging

Mỗi article/story cần structured metadata:

```json
{
  "entities": [
    {
      "type": "company",
      "name": "Vingroup",
      "ticker": "VIC"
    }
  ],
  "sectors": ["Real Estate"],
  "topics": ["Vingroup"],
  "market_relevance": 0.41
}
```

Sau này có thể filter:

- Tin về STB.
- Tin về watchlist.
- Tin ảnh hưởng banking.
- Tin ảnh hưởng portfolio.

---

# 22. Article Detail — giữ reader mode

Màn article hiện tại nên giữ:

- headline lớn,
- body centered,
- hero image rộng,
- dark editorial layout.

Không nên nhét AI summary card khổng lồ lên đầu.

AI nên đóng vai **companion**, không phá trải nghiệm đọc.

---

# 23. AI Insight Rail

Desktop có thể mở một side rail:

```text
┌────────────────────────┐
│ ✦ AI Insight           │
│                        │
│ Tóm tắt                │
│ ...                    │
│                        │
│ Tác động               │
│ VIC     Trung tính     │
│ VHM     Trung tính     │
│                        │
│ Liên quan              │
│ BĐS · Vingroup         │
│                        │
│ 6 nguồn khác           │
│                        │
│ [ Hỏi AI về tin này ] │
└────────────────────────┘
```

---

# 24. Hỏi AI về tin này

Khi bấm:

```text
[ 📰 2 ngày cuối tuần... × ]

Hỏi về bài viết này...
```

User có thể hỏi:

- Có đáng lo không?
- Tin này ảnh hưởng STB không?
- Mã nào hưởng lợi?
- Có nguồn nào xác nhận?
- Tác động tới VNINDEX?
- Tại sao nó quan trọng?

AI nhận Article Context + Market Context + Symbol Context nếu có.

---

# 25. Fact vs AI Interpretation

Finance cần tách rõ dữ kiện và suy luận.

Ví dụ:

```text
Key facts

• VNINDEX đóng cửa +1.95%
• Thanh khoản đạt 24.680 tỷ
• Khối ngoại bán ròng 1.240 tỷ

AI interpretation

Độ rộng thị trường và thanh khoản cho thấy...
```

User luôn biết đâu là:

- số liệu,
- nguồn,
- suy luận của AI.

---

# 26. Why It Matters

Không nên chỉ có AI Summary.

Nên thêm:

> **TẠI SAO ĐÁNG CHÚ Ý?**

Ví dụ:

```text
Tóm tắt
...

TẠI SAO ĐÁNG CHÚ Ý?

Thông tin này cho thấy...
Tuy nhiên tác động trực tiếp tới lợi nhuận VIC
hiện chưa đáng kể.
```

Summary ≠ Insight.

---

# 27. Potential Impact

Không nên vội biến news thành BUY/SELL.

Vocabulary phù hợp hơn:

```text
Potential Impact

Tích cực
Tiêu cực
Trung tính
Chưa rõ
```

và:

```text
Confidence

Cao
Trung bình
Thấp
```

Ví dụ:

```text
VHM
Tích cực · Confidence trung bình
```

---

# 28. Market Reaction

Feature rất stock-native:

```text
TIN
NHNN ...
09:35

30 phút sau

Bank Index     +1.2%
STB            +1.8%
MBB            +1.4%
Volume         1.7x
```

Article detail có thể show:

```text
MARKET REACTION

STB       +1.8%
MBB       +1.4%
Banking   +1.2%

Kể từ thời điểm tin xuất hiện
```

AI có thể giải thích:

> Tin này có khả năng đóng góp, nhưng chưa đủ bằng chứng để quy toàn bộ biến động cho sự kiện.

---

# 29. Official Disclosure

Phần "Công bố thông tin" nên được phát triển thành nguồn riêng:

```text
TIN TỨC
Editorial / media

CÔNG BỐ
Official disclosure
```

Nguồn:

- HOSE.
- HNX.
- SSC.
- Company IR.
- Báo cáo tài chính.
- Công bố doanh nghiệp.

Có badge:

```text
OFFICIAL
```

AI nên ưu tiên primary source khi có conflict.

---

# 30. Source Hierarchy

Backend có thể có source reliability layer:

```text
Tier 1
Official disclosure
Financial statements
Exchange
Government

Tier 2
Reuters / Bloomberg / established media

Tier 3
Financial news sites

Tier 4
Social / community
```

Không nhất thiết hiển thị tier trực tiếp cho user.

Nhưng AI / ranking engine nên biết.

---

# 31. Watchlist + News

Sidebar hiện có chấm cam cạnh mã.

Nên biến nó thành event indicator:

```text
STB   74.700   +0.27%   ●
```

Tooltip:

```text
2 cập nhật mới

1 tin quan trọng
1 biến động đáng chú ý
```

Click → filter news theo STB.

Sau này indicator này có thể tiến hóa thành Portfolio Event.

---

# 32. Personalized News

News có thể có filter:

```text
[Mới nhất] [Theo dõi]
```

Hoặc:

```text
Dành cho bạn
```

Lấy dữ liệu từ:

- watchlist,
- portfolio,
- ngành user thường xem.

Ví dụ:

```text
DÀNH CHO BẠN

VHM
Vingroup công bố...
8 phút trước

STB
Sacombank...
37 phút trước
```

---

# 33. Portfolio — vị trí trong UI

Portfolio không nên bị giấu dưới "Đã ghim".

Nó là Core.

Nên nằm ở primary navigation:

```text
[ Hỏi AI ] [ Thị trường ] [ Danh mục ]
```

---

# 34. Portfolio Home

Màn đầu tiên không nên mở bằng 5 bài phân tích dài.

Nó phải trả lời:

> Danh mục của tôi đang thế nào?

Ví dụ:

```text
Danh mục của tôi

Tổng tài sản
1.248.500.000đ
+127.400.000đ (+11,36%)

Hôm nay
+12.4 triệu (+1,01%)

So với VNINDEX
+3,2%

────────────────────────────────────

AI PORTFOLIO VIEW

Trạng thái       TÍCH CỰC
Health Score     78 / 100
Risk             Trung bình
Concentration    Cao
AI confidence    82%

✦ Có 2 thay đổi đáng chú ý hôm nay

[ Xem AI Brief ]

────────────────────────────────────

Danh mục

Mã      Tỷ trọng   P/L       Hôm nay    AI View
STB      31%      +18.2%     +0.27%      Tích cực ↑
FPT      24%       +8.7%     +1.41%      Tích cực →
HPG      20%       -3.1%     +2.20%      Theo dõi ↓
MWG      15%      +11.4%     +0.80%      Tích cực →
VNM      10%       +3.2%     -0.20%      Trung tính →
```

---

# 35. Portfolio Daily Brief

Một feature sticky mạnh:

```text
Morning Portfolio Brief

Overall:
Positive, risk unchanged.

STB — Important
Tin X có khả năng ảnh hưởng tích cực tới thesis.
AI confidence 72 → 79%.

HPG — Watch
Giá thép X giảm Y%; đây là risk mới đối với margin.

FPT — No material change
Không có thông tin mới làm thay đổi thesis.

Portfolio
Banking exposure hiện 47%.

Today to watch
10:00 — event X
14:00 — macro data Y
```

User có thể hiểu toàn danh mục trong 30 giây.

---

# 36. Living Investment Thesis

Mỗi mã không chỉ có "analysis".

Nó có một **thesis sống theo thời gian**.

Ví dụ:

| Field | Value |
|---|---|
| Current view | Positive / Neutral / Negative |
| Horizon | 3–6 tháng |
| Fundamental | 8.1/10 |
| Valuation | 7.2/10 |
| Momentum | 8.4/10 |
| Technical | 7.5/10 |
| News/Sentiment | 7.9/10 |
| Risk | Medium |
| Confidence | 76% |
| Key catalysts | X, Y, Z |
| Major risks | A, B |
| Thesis invalidation | Nếu X xảy ra |
| Last changed | timestamp |

Luồng:

```text
STB thesis v1
    ↓
new price
new financial data
new news
new corporate event
    ↓
Delta analysis
    ↓
STB thesis v2
```

AI không regenerate từ đầu mỗi lần.

---

# 37. Thesis Change

User cần thấy:

```text
AI changed its view on STB

Neutral → Positive

Why?

- Loan growth accelerated
- New material information appeared
- Price broke resistance with volume
- Valuation remains below historical percentile

Confidence: 72% → 81%
```

Đây là feature có khả năng tạo retention mạnh.

---

# 38. Thesis Invalidation

AI không chỉ nói:

> Bullish.

Nó phải nói:

> Khi nào thesis này sai?

Ví dụ:

```text
Current Thesis

Bull thesis:
ABC

Expected catalyst:
XYZ

Expected timeframe:
2–4 months

WHAT WOULD CHANGE OUR VIEW

1. Profit growth < X%
2. NIM falls below Y
3. Support Z breaks
4. Regulatory event X
5. Valuation exceeds Y
```

Sau đó hệ thống monitor chính các điều kiện này.

---

# 39. Stock Score vs Position Score

Phải có hai score khác nhau.

## Stock Score

> Mã này hấp dẫn như thế nào?

## Position Score

> Vị thế này có phù hợp với danh mục của user này không?

Ví dụ:

```text
STB Stock Score
82 / 100
Strong

STB Position Score
58 / 100
Overweight
```

Lý do:

```text
Quality              +++
Valuation            +++
Momentum             +++

BUT

Current allocation     37%
Bank exposure          55%
Correlation with MBB   0.82
Risk contribution      44%
```

Một cổ phiếu tốt không có nghĩa vị thế hiện tại của user là tốt.

---

# 40. Position Detail

Click STB trong Portfolio:

```text
STB · Trong danh mục của bạn

74.700     +0,27%

Vị thế của bạn

1.000 cp
Giá vốn       68.200
Giá trị       74.700.000
P/L           +9,53%
Tỷ trọng      31%

────────────────────

AI VIEW

Stock Score       82
Position Score    63

STB vẫn có outlook tích cực,
nhưng tỷ trọng hiện tại tương đối cao.

[ Xem thesis ]
[ Hỏi AI ]
```

Khác biệt giữa:

> phân tích STB

và:

> phân tích STB của tôi.

---

# 41. Scenario Engine

Backend simulation trước, AI chỉ giải thích.

Ví dụ user hỏi:

> Nếu VNINDEX giảm 10% thì danh mục tôi thế nào?

Engine:

```text
VNINDEX       -10%
Banks         -14%
Technology     -8%
Steel         -18%

Portfolio estimated:
-12.4%

Biggest contributor:
STB   -4.2%
HPG   -3.1%
```

AI giải thích why.

Có thể mở rộng:

- lãi suất +100 bps,
- USD/VND +3%,
- giá thép +10%,
- dầu lên $120,
- sector shock,
- foreign sell-off.

---

# 42. Portfolio Memory Model

Memory không chỉ là conversation history.

Nên lưu:

```text
User
│
├ Investment Profile
│  ├ risk tolerance
│  ├ investment horizon
│  ├ strategy
│  └ preferred sectors
│
├ Portfolio
│
├ STB
│  ├ position
│  ├ initial thesis
│  ├ current thesis
│  ├ thesis history
│  ├ alerts
│  └ user notes
│
└ Decisions
   ├ bought
   ├ sold
   ├ ignored AI
   └ reason
```

Sau vài tháng AI có thể phân tích hành vi đầu tư của chính user.

---

# 43. Decision Journal

Ví dụ:

```text
Buy 500 STB @ 52.2

Why?
[x] AI thesis
[x] Technical breakout
[ ] News
[ ] Personal research

Expectation:
STB → 60 within 4 months

Invalidation:
< 46
```

Sau này AI review:

> Thesis ban đầu đúng/sai ở đâu?

Feedback loop:

```text
Research
   ↓
Decision
   ↓
Outcome
   ↓
Review
   ↓
Better decision
```

---

# 44. Event-Driven Portfolio AI

Không nên deep-analyze liên tục.

Trigger deep analysis khi có material event:

```text
Price move abnormal
Volume spike
Technical breakout
New financial statement
New company disclosure
Major news
Management change
Dividend / corporate action
Sector event
Macro event
Valuation threshold
Thesis invalidation
```

Luồng:

```text
Market stream
    │
    ▼
Event Detector
    │
    ▼
Material Event?
    │
    YES
    ▼
Deep Analysis
    │
    ▼
Does thesis change?
    │
    YES
    ▼
Update thesis
    │
    ▼
Does portfolio risk change?
    │
    ▼
Notify / Brief user
```

Lợi ích:

- giảm inference cost,
- giảm noise,
- tạo signal chất lượng cao hơn.

---

# 45. Quant Engine phải đứng dưới LLM

Không để LLM tính các chỉ số quan trọng.

Architecture:

```text
                User Portfolio
                      │
                      ▼
             Portfolio Engine
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
 Market Engine   Fundamental     News Engine
                     Engine
       │              │              │
       └──────────────┼──────────────┘
                      ▼
                Feature Store
                      │
                      ▼
                Quant Engine
                      │
        ┌─────────────┼─────────────┐
        │             │             │
     Risk         Technical      Factors
     Engine        Engine         Engine
        │             │             │
        └─────────────┼─────────────┘
                      ▼
               Structured JSON
                      │
                      ▼
               AI Orchestrator
                      │
                      ▼
               Final Explanation
```

Nguyên tắc:

> **Code calculates. LLM interprets.**

---

# 46. Agent Architecture

Không cần over-engineer multi-agent ngay từ MVP.

Có thể bắt đầu bằng một orchestrator mạnh:

```text
Portfolio Orchestrator
       │
       ├ get_fundamentals()
       ├ get_market_data()
       ├ get_technicals()
       ├ search_news()
       ├ calculate_risk()
       ├ get_thesis()
       └ update_thesis()
```

Sau này mới logical split:

| Role | Responsibility |
|---|---|
| Equity Analyst | Fundamentals / company |
| Market Analyst | Price / technical / flow |
| News Analyst | News / filings |
| Risk Analyst | Challenge thesis |
| Portfolio Manager | Portfolio-level view |
| Supervisor | Final synthesis |

---

# 47. Hermes Agent — nên dùng thế nào

Hermes-like architecture đáng học cho:

- agent runtime,
- tool registry,
- memory,
- skills,
- subagents,
- scheduled tasks,
- long-running jobs,
- sandbox.

Nhưng không nên biến Hermes thành toàn bộ backend tài chính.

Architecture phù hợp:

```text
                    VISGNITE

 ┌─────────────────────────────────────────────┐
 │                 Web App                     │
 │                                             │
 │ Chat     Markets     News     Portfolio     │
 └───────────────────┬─────────────────────────┘
                     │
               AI Gateway
                     │
            Portfolio Orchestrator
                     │
         ┌───────────┴───────────┐
         │                       │
   Hermes-like runtime     Finance Engine
         │                       │
 Tools / Memory             ├ Market
 Skills                     ├ Fundamentals
 Subagents                  ├ Technical
 Cron                       ├ Risk
                            ├ Factors
                            └ Portfolio
```

**Finance Engine mới là IP / moat.**

Harness chỉ là infrastructure.

---

# 48. Tool Layer cho AI

Không để AI query DB tùy tiện.

Tạo explicit tools:

```text
get_market_overview()
get_stock_quote(symbol)
get_stock_profile(symbol)
get_stock_financials(symbol)
get_price_history(symbol)
get_sector_performance()
get_market_breadth()
get_foreign_flow()
get_latest_news()
search_news()
get_news_story(id)
get_related_news(symbol)
get_portfolio()
calculate_portfolio_risk()
get_current_thesis(symbol)
update_thesis(symbol)
run_scenario(...)
```

Backend trả normalized JSON.

Agent không cần biết data provider bên dưới là SSI, FiinTrade hay provider khác.

---

# 49. AI Chat Orchestrator — MVP

Ví dụ user hỏi:

> Vì sao VNINDEX hôm nay tăng?

Agent có thể gọi:

```text
get_market_overview()

get_sector_performance()

get_top_movers()

get_foreign_flow()

search_news(
   market,
   date=today
)
```

Sau đó trả:

- structured answer,
- citations,
- AI blocks.

Một agent mạnh là đủ ở MVP.

---

# 50. Model Modes

UI đang có `Visgnite Pro`.

Có thể phát triển:

```text
Visgnite Fast
Nhanh

Visgnite Pro
Phân tích sâu

Deep Research
Nghiên cứu chuyên sâu
```

Không cần expose underlying model vendor.

Visgnite nên sở hữu abstraction.

---

# 51. Citations

Finance AI không nên trả lời không nguồn.

Ví dụ:

```text
Doanh thu Q2 tăng 21% YoY. [1]

NIM phục hồi lên 3.6%. [2]
```

Footer:

```text
Nguồn

1. BCTC STB Q2/2026
2. Báo cáo nhà đầu tư STB
3. HOSE
4. Reuters
```

Hover citation có preview.

Citation là trust layer.

---

# 52. Data Freshness

Phải show timestamp / freshness rõ.

Market:

```text
STB
74,700

Realtime · 10:42:31
```

Fundamental:

```text
Q2/2026
Cập nhật 31/07/2026
```

News:

```text
17 phút trước
```

AI:

```text
Phân tích dựa trên dữ liệu đến 10:42
```

User luôn biết AI biết đến thời điểm nào.

---

# 53. AI Safety / Epistemics

Tránh product hóa quá sớm thành:

> "AI BUY / SELL".

Hướng tốt hơn:

```text
Evidence
   ↓
Thesis
   ↓
Risk
   ↓
Change
   ↓
Decision support
```

AI nên nói:

- positive / neutral / negative,
- potential impact,
- confidence,
- evidence,
- invalidation,
- uncertainty.

Không cần giả vờ chắc chắn.

---

# 54. Development Warnings

UI development hiện có card kiểu:

> Số liệu mẫu — API chưa tổng hợp...

Production không nên để warning chiếm attention.

Có thể hiển thị nhẹ hơn:

```text
Thanh khoản

21.410 tỷ

Một phần dữ liệu đang cập nhật ⓘ
```

Chi tiết đưa vào tooltip.

---

# 55. MVP Roadmap

## Phase 1 — Market Data Foundation

Build:

```text
Realtime / delayed quote
Indices
Market breadth
Sector
VN30
Foreign flow
Liquidity
Symbol search
Watchlist
Stock detail
```

Nguyên tắc:

> Không AI cũng phải dùng được.

---

## Phase 2 — News Intelligence

Build:

```text
News ingestion
Deduplication
Story clustering
Ticker tagging
Sector tagging
AI summarization
Why it matters
Potential impact
Source citations
Official disclosures
```

Lúc này platform trả lời được:

> What is happening?

và:

> Why?

---

## Phase 3 — AI Chat

Build:

```text
Chat
Tool calling
Streaming
AI Blocks
Citations
Context chips
Conversation history
Universal search
Market context
News context
Symbol context
```

Lúc này AI trả lời:

> What does it mean?

---

## Phase 4 — Portfolio AI

Build:

```text
Portfolio max ~5 stocks
Position + cost basis
Living thesis
Thesis history
Material event detection
Stock Score
Position Score
Risk
Daily Brief
Portfolio Chat
Simple Scenario Engine
```

Lúc này sản phẩm trả lời:

> What does it mean for me?

---

# 56. MVP Portfolio Scope

| Feature | MVP |
|---|---|
| Max 5 stocks | Yes |
| Quantity + cost basis | Yes |
| Market price | Yes |
| Fundamentals | Yes |
| Financial statements | Yes |
| News | Yes |
| Technical indicators | Yes |
| Stock AI thesis | Yes |
| Portfolio analysis | Yes |
| Thesis history | Yes |
| Material-change detection | Yes |
| Daily portfolio brief | Yes |
| Portfolio Chat | Yes |
| Scenario simulation | Simple V1 |
| Broker integration | Later |
| Auto trading | No |
| 10-agent orchestration | No |

---

# 57. Killer Product Loop

```text
User adds 5 stocks
        ↓
AI builds initial thesis
        ↓
Market changes
        ↓
System detects material event
        ↓
AI evaluates thesis delta
        ↓
"Something important changed"
        ↓
User opens app
        ↓
AI explains impact on portfolio
        ↓
User makes decision
        ↓
Decision stored
        ↓
AI learns portfolio history
```

Đây là loop biến Visgnite từ:

> website chứng khoán có chatbot

thành:

> **agentic financial intelligence platform**.

---

# 58. Ba primitive nên ưu tiên nhất

Nếu phải chọn những primitive quan trọng nhất để build sớm:

## 1. Context System

```text
market | symbol | news | sector | portfolio
```

Nối toàn bộ product.

## 2. AI Blocks

Biến AI response thành financial-native UX thay vì markdown chatbot.

## 3. Stock Detail

Là cầu nối tự nhiên giữa Market, News, AI và Portfolio.

Sau đó với Portfolio:

## 4. Living Thesis

AI opinion sống theo thời gian.

## 5. Material Change Detection

Chỉ trigger khi có điều thật sự đáng chú ý.

## 6. Position Score

Đánh giá mã trong context portfolio của từng user.

---

# 59. Product Principles

## Principle 1

> Market data và quant phải deterministic.

LLM không phải calculator.

## Principle 2

> AI phải có nguồn.

Không source → giảm trust.

## Principle 3

> Context everywhere.

User không cần nhắc lại "STB" trong mọi prompt.

## Principle 4

> News phải thành intelligence.

Không chỉ RSS feed.

## Principle 5

> Portfolio là Core.

Không phải một feature bị giấu trong sidebar.

## Principle 6

> AI is a layer, not a page.

AI phải có mặt trong Market, News, Stock Detail và Portfolio.

## Principle 7

> Build a financial workspace, not another chatbot.

---

# 60. North Star UX

Một user mở Visgnite lúc 9:30.

Họ thấy:

> VNINDEX +1.3%. Chứng khoán và ngân hàng đang dẫn dắt. Khối ngoại bán ròng 420 tỷ.

Click:

> **Tại sao?**

AI trả lời.

Click STB:

> **STB có hưởng lợi không?**

AI chuyển context.

Đọc một tin:

> **Tin này tác động thế nào tới STB?**

AI chuyển context.

Sau này có portfolio:

> **Tin này tác động thế nào tới danh mục tôi?**

AI trả lời.

Đó là lúc Visgnite trở thành:

> **Financial Intelligence Workspace**

thay vì:

> Chatbot + Bảng giá + News.

---

# 61. Recommended Build Order ngay từ UI hiện tại

Nếu phát triển trực tiếp từ UI hiện tại, thứ tự hợp lý:

1. **Khóa Information Architecture**
   - Hỏi AI
   - Thị trường
   - Danh mục
   - News là discovery/intelligence surface.

2. **Build Context System**
   - symbol
   - market
   - news
   - sector
   - portfolio.

3. **Build Universal Search + Stock Detail**

4. **Build News Intelligence Pipeline**
   - dedupe
   - cluster
   - entity tagging
   - source hierarchy
   - AI summary / why it matters / impact.

5. **Build AI Tool Layer**

6. **Build AI Blocks**

7. **Nối Ask AI vào mọi surface**

8. **Build Portfolio V1**
   - 5 mã
   - cost basis
   - thesis
   - risk
   - daily brief.

9. **Build Material Event Engine**

10. **Sau cùng mới tăng độ phức tạp agent**
    - subagents
    - long-running jobs
    - advanced research
    - skill learning.

---

# 62. Chốt định vị

Visgnite nên tiến hóa theo câu chuyện rất rõ:

```text
THỊ TRƯỜNG
"Đang xảy ra chuyện gì?"

TIN TỨC
"Tại sao?"

AI
"Nó có nghĩa gì?"

DANH MỤC
"Nó có nghĩa gì đối với tôi?"
```

Đây là flow sản phẩm nên được giữ xuyên suốt từ:

- UI,
- IA,
- backend,
- data model,
- agent architecture,
- branding,
- roadmap.

Nếu làm tốt, phần có giá trị nhất về lâu dài không phải model nào được dùng, mà là:

- market + fundamental + news data layer,
- user context,
- living thesis,
- portfolio intelligence,
- event graph,
- historical decision memory,
- trust/citation layer.

Đó mới là **moat của VisgniteAI**.

---

# 63. UX Deep Dive — Page Responsibilities

The key UX distinction:

> **Hỏi AI = intent-driven. Portfolio = state-driven.**

- **Hỏi AI** starts from a user question.
- **Portfolio** starts from persistent user state and should proactively surface what matters before the user asks.

This prevents the two most important surfaces from collapsing into two versions of the same screen.

## Mental model by page

| Page | Mental model | Core intent |
|---|---|---|
| Hỏi AI | Conversation workspace | "Tôi có một câu hỏi." |
| Thị trường | Market cockpit | "Đang xảy ra chuyện gì?" |
| Tin tức | Information discovery | "Chuyện gì đang đáng chú ý và tại sao?" |
| Stock Detail | Entity workspace | "Cho tôi hiểu mã này." |
| Portfolio | Personal command center | "Danh mục của tôi đang thế nào?" |

Rule:

> **Nếu thông tin tồn tại dù user chưa hỏi → Portfolio.**  
> **Nếu thông tin được tạo vì user đặt câu hỏi → Hỏi AI.**

---

# 64. UX — Hỏi AI

Hỏi AI phải giữ identity rõ ràng:

```text
Conversation-first
Whitespace
Adaptive
Exploratory
```

Không biến landing thành dashboard.

## 64.1. Landing

Chỉ nên có ambient market context nhẹ:

```text
Rise and shine

┌────────────────────────────────────────────┐
│ Hỏi về một mã, một ngành hay thị trường…  │
│                                            │
│ +                         Visgnite Pro     │
└────────────────────────────────────────────┘

VNINDEX +1.95%     VN30 +2.16%

Đáng chú ý hôm nay

Ngân hàng đang dẫn dắt thị trường
Khối ngoại bán ròng 1.240 tỷ
STB có 1 cập nhật mới

Gợi ý

Vì sao VNINDEX tăng?
Phân tích STB
Có gì mới với mã tôi theo dõi?
```

## 64.2. Ba trạng thái context

### No Context

```text
Hỏi về một mã, một ngành hay cả thị trường...
```

### Symbol Context

```text
[ STB × ]

Hỏi về STB...

Tại sao hôm nay STB tăng?
Định giá STB hiện tại thế nào?
Có tin gì mới?
So sánh STB với MBB.
```

### Portfolio Context

```text
[ ◇ Danh mục của tôi × ]

Hỏi về danh mục...

Mã nào đang rủi ro nhất?
Tại sao hôm nay tôi kém VNINDEX?
Có gì cần theo dõi ngày mai?
Nếu thị trường giảm 5% thì sao?
```

## 64.3. Context Stack

AI có thể nhận nhiều context cùng lúc:

```text
[ ◇ Portfolio × ]
[ STB × ]
[ 📰 Tin NHNN × ]
```

Ví dụ:

> Tin này ảnh hưởng vị thế STB trong danh mục của tôi thế nào?

## 64.4. Composer

Composer nên là context-aware command surface:

```text
┌────────────────────────────────────────────────────┐
│ [STB ×] [Tin NHNN ×]                              │
│                                                    │
│ Tin này ảnh hưởng STB thế nào?                    │
│                                                    │
│ +      Research ▾        Visgnite Pro ▾          │
└────────────────────────────────────────────────────┘
```

`+` có thể thêm:

- mã chứng khoán,
- tin tức,
- danh mục,
- file,
- báo cáo.

## 64.5. Response UX

Không trả markdown dump dài.

Text = interpretation.  
Financial blocks = evidence.

```text
AI explanation

──────────────────

STB
74.700 +0.27%

[ mini chart ]

P/B       1.42x
ROE       18.2%

──────────────────

Điểm chính
...

──────────────────

Nguồn
[1] HOSE
[2] BCTC Q2
```

## 64.6. Follow-up

Sau mỗi answer nên có contextual follow-up:

```text
Định giá sâu hơn
So với MBB
Rủi ro lớn nhất?
Tin gần đây
Ảnh hưởng tới danh mục?
```

## 64.7. Inline AI vs Full AI Workspace

### Inline AI

Dùng cho:

- Tại sao?
- Giải thích score này.
- Tin này ảnh hưởng gì?
- Vì sao risk tăng?

Mở side panel / popover ngay trong current page.

### Full AI Workspace

Dùng cho:

- deep analysis,
- comparison,
- multi-turn conversation,
- scenario exploration,
- deep research.

Context phải được preserve khi mở full chat.

## 64.8. Deep Research

Không phải mọi câu hỏi đều chạy agent dài.

Có thể có:

```text
Nhanh
Phân tích
Deep Research
```

Deep Research chỉ show work status:

```text
✓ Dữ liệu thị trường
✓ BCTC gần nhất
✓ Công bố doanh nghiệp
● Đang tổng hợp tin tức
○ Định giá tương đối
○ Kiểm tra luận điểm
```

Không hiển thị chain-of-thought nội bộ.

---

# 65. UX — Portfolio

Portfolio phải có identity khác hẳn Chat:

```text
Status-first
Structured
Persistent
Proactive
```

Portfolio phải **answer before asking**.

Above the fold cần trả lời:

```text
Performance
Risk
What changed
What matters
```

## 65.1. Portfolio Home

```text
Danh mục của tôi                         Cập nhật 10:42

1.248.500.000đ
+127.400.000đ (+11.36%)      Hôm nay +1.01%

so với VNINDEX
+3.2%

────────────────────────────────────────────

AI PORTFOLIO BRIEF

TÍCH CỰC                                  78 / 100

Danh mục tăng 1.01%, thấp hơn VNINDEX 0.94%.
STB và HPG đóng góp phần lớn mức tăng.

⚠ STB hiện chiếm 31% tổng danh mục.
● HPG có 1 thay đổi đáng theo dõi.

[ Hỏi AI về danh mục ]

────────────────────────────────────────────

Danh mục

STB      31%      +9.53%      +0.27%      Positive
FPT      24%      +8.72%      +1.41%      Positive
HPG      20%      -3.10%      +2.20%      Watch
MWG      15%      +11.4%      +0.80%      Positive
VNM      10%      +3.20%      -0.20%      Neutral
```

## 65.2. Hero của Portfolio = What Changed

Broker đã cho user thấy giá và P/L.

Visgnite phải cho thứ broker không có:

```text
Từ lần bạn xem gần nhất

2 thay đổi đáng chú ý

STB
Thesis vẫn tích cực.
Tỷ trọng tăng từ 27.8% → 31.1%.

HPG
Risk tăng nhẹ do giá nguyên liệu đầu vào.

FPT, MWG, VNM
Không có thay đổi đáng kể.
```

## 65.3. Since Last Visit

```text
Kể từ 17:42 hôm qua

Portfolio        +0.82%
VNINDEX          +1.03%

3 new events
1 thesis change
2 new company disclosures
```

## 65.4. Health Score

Nếu dùng score, score phải explainable:

```text
Portfolio Health
78 / 100

Diversification       64
Concentration         55
Quality               84
Valuation             76
Momentum              81
Risk                   69
```

Và support delta:

```text
78 → 74

Why?
STB concentration increased.
```

Không dùng arbitrary AI number.

## 65.5. Không spam chữ "AI"

Không cần:

```text
AI Score
AI Risk
AI News
AI View
AI Insight
AI Thesis
```

Nên để AI phần lớn invisible.

Chỉ dùng branding rõ cho những phần thực sự generated:

```text
✦ AI Brief
```

## 65.6. Portfolio subviews

Về lâu dài:

```text
Tổng quan
Vị thế
Rủi ro
Hoạt động
```

MVP có thể chỉ:

```text
Tổng quan | Vị thế
```

## 65.7. Position Detail

Không tạo một page hoàn toàn tách khỏi Stock Detail nếu có thể.

Khi user sở hữu STB:

```text
STB
74.700 +0.27%

◇ Trong danh mục · 31.1% · +9.53%

[ Tổng quan ]
[ Vị thế của tôi ]
[ Biểu đồ ]
[ Tài chính ]
[ Tin tức ]
[ AI ]
```

Trong `Vị thế của tôi`:

```text
Bạn sở hữu
1.000 cp

Giá vốn
68.200

Lợi nhuận
+9.53%

Tỷ trọng
31.1%

POSITION VIEW

Stock quality        Strong
Position fit         Watch

STB vẫn có thesis tích cực,
nhưng tỷ trọng hiện tại đã cao.

Living Thesis
Positive

Catalysts
...

Risks
...

Invalidation
...
```

## 65.8. Proactive events

Portfolio phải chủ động:

```text
Cần chú ý

STB
Tỷ trọng vượt 30%.

HPG
Một rủi ro mới xuất hiện.

MWG
KQKD mới đã được công bố.
```

Alert hierarchy:

```text
Critical
Important
FYI
```

Chỉ show 1–3 item đáng chú ý nhất.

## 65.9. Material Event card

```text
HPG                                      10:42

RISK CHANGED

Giá quặng tăng mạnh trong 3 phiên gần đây.

Tại sao đáng chú ý
Có khả năng gây áp lực lên gross margin.

Thesis
Positive → Positive

Risk
Medium → Medium-high

[ Chi tiết ] [ Hỏi AI ]
```

## 65.10. Thesis Timeline

```text
STB · Thesis History

23 Aug
Positive → Positive
Confidence 74 → 79
Reason: earnings / flow

18 Aug
Neutral → Positive
Reason: ...

07 Aug
Neutral
Initial thesis
```

## 65.11. Risk UX

Plain-language trước, quant sau:

```text
RỦI RO DANH MỤC

Trung bình-cao

Điểm đáng chú ý

31% nằm ở STB.
51% exposure liên quan tài chính.
STB và MBB có correlation cao.
```

Sau đó mới drill-down:

- sector exposure,
- position concentration,
- drawdown,
- beta,
- VaR,
- correlation.

## 65.12. Scenario UX

Portfolio có CTA structured:

```text
Mô phỏng kịch bản
```

Preset:

```text
VNINDEX -5%
VNINDEX -10%
USD/VND +3%
Lãi suất +1%
Banking -10%
```

Result do deterministic engine tính:

```text
VNINDEX -10%

Estimated portfolio impact
-12.4%

Main contributors

STB   -4.2%
HPG   -3.1%
FPT   -1.8%

Confidence
Medium

[ Hỏi AI giải thích ]
```

## 65.13. Decision Journal

Không bắt user viết diary dài.

Khi update position:

```text
Bạn vừa thêm 500 STB @ 72.4

Lưu lý do?         Optional

Thesis vẫn đúng
Giá hấp dẫn
Breakout
Theo tin
Khác
```

---

# 66. UX — Ask AI vs Portfolio Ownership Matrix

| Feature | Hỏi AI | Portfolio |
|---|:---:|:---:|
| Open-ended question | **Primary** | Secondary |
| Market Q&A | **Primary** | No |
| Deep stock research | **Primary** | Entry point |
| Compare stocks | **Primary** | Secondary |
| Portfolio P/L | Context | **Primary** |
| Allocation | Context | **Primary** |
| Portfolio risk | Explain | **Primary** |
| Daily brief | Can answer | **Primary** |
| Material events | Can research | **Primary** |
| Living thesis | Explain/edit | **Primary display** |
| Scenario | Conversation | **Structured tool** |
| Decision journal | Refer to | **Primary** |
| Multi-turn research | **Primary** | Hand off |
| Proactive alerts | No | **Primary** |
| Personal status | Context | **Primary** |

Core rule:

> **Chat produces insight. Portfolio persists intelligence.**

---

# 67. UX — Empty Portfolio Onboarding

Không show dashboard trống.

```text
Danh mục của bạn

Theo dõi tối đa 5 mã để Visgnite phân tích
liên tục những gì ảnh hưởng đến bạn.

[ + Thêm mã đầu tiên ]

Bạn sẽ nhận được:

Living thesis
Risk analysis
Material events
Daily brief
Portfolio chat
```

Add stock:

```text
Tìm mã

STB
Sacombank

Số lượng
[      ]

Giá vốn
[      ]

Ngày mua
Optional
```

Có thể cho option:

```text
Tôi chỉ muốn theo dõi thesis
```

Không hỏi risk profile dài ngay từ đầu.

Progressive profiling sau khi user đã có value.

---

# 68. UX Principle by Page

| Page | UX identity |
|---|---|
| Hỏi AI | **Think with Visgnite** |
| Market | **Scan the market** |
| News | **Understand what happened** |
| Stock | **Understand the company** |
| Portfolio | **Know what matters to you** |



---

# 69. Data Provider Strategy, Quota & Cost Control — Repo-Aware Revision

> Phần này thay thế cách tiếp cận quota generic trước đây. Repo hiện đã có nhiều foundation quan trọng; không build lại những thứ đã tồn tại.

## 69.1. Existing Architecture — xem như invariant, không build lại

Repo đã có:

| Capability | Existing implementation |
|---|---|
| Provider abstraction | `stocks/providers/contracts.py` với `MarketDataProvider`, `FundamentalDataProvider`, `ValuationDataProvider`, `ReferenceDataProvider`; adapters `vnstock_provider.py`, `fiinquant.py` |
| Central provider quota | `core/quota.py` — Redis arbiter cho account allowance và spacing |
| Background priority lanes | `core/quota.py`; collector lease > news lane > backfill/legacy; lane propagated bằng `ContextVar` |
| Provider → Visgnite → Users | Collector là nơi duy nhất gọi Provider Source; `providers/store.py` giữ last-known-good trong `ProviderSnapshot`; app đọc store |
| Cold-data vnstock | EOD collector, `catch_up_market_data`, `backfill_universe_history`, census |
| News ingestion once | `cafef_rss.py`, `cafef_article.py`, `core/news_lane.py` |
| Scheduler | `core/scheduler.py` + `is_trading_day` |
| Hard runtime provider guard | `core/provider_access.py::store_only_execution()` |

`store_only_execution()` là một architectural invariant rất mạnh:

```text
Application / request-serving path
          ↓
store_only_execution()
          ↓
Provider call attempted
          ↓
HARD FAIL
```

Nguyên tắc chính thức:

> **All request-serving paths are store-only. External provider access chỉ được phép trong collector/backfill/authorized ingestion contexts và được enforce ở runtime.**

Không cần build lại provider abstraction, central limiter hay Provider → Visgnite → Users.

---

# 70. P0 — Fix Multi-Window Quota Correctness

Vấn đề thực:

```text
60 req/minute
3000 req/hour
```

`1 request / second`:

```text
60 req/minute
3600 req/hour
```

=> vượt hourly cap 20% nếu sustain.

Do đó `ACCOUNT_SPACING_WITH_KEY = 1.0` chỉ đảm bảo minute burst, không đảm bảo hourly quota.

## 70.1. Không chỉ sửa spacing

Không nên đơn giản đổi toàn hệ thống thành `1.2s`.

Quota là multi-window.

Model đúng:

```text
minimum spacing
+
minute window
+
hour window
+
monthly window nếu provider có
```

Config nên biểu diễn quota như:

```yaml
vnstock:
  windows:
    - requests: 60
      seconds: 60
    - requests: 3000
      seconds: 3600

  safety_factor: 0.90
```

Runtime derive:

```text
60 / 60       = 1.000 req/s
3000 / 3600   = 0.833 req/s
```

Long-run bottleneck:

```text
0.833 req/s
≈ 50 rpm sustained
```

Với 90% safety margin:

```text
≈ 45 rpm sustained target
```

Minute burst vẫn có thể lên gần 60 nếu còn hourly budget.

## 70.2. Redis quota arbiter mở rộng

Concept:

```text
quota:vnstock:minute
quota:vnstock:hour
```

Acquire chỉ thành công nếu:

```text
minute budget available
AND
hour budget available
AND
spacing satisfied
```

Có thể implement bằng rolling-window sorted set hoặc time-bucket counters tùy enforcement semantics của upstream.

---

# 71. P0 — Contain `sys.exit()` at Provider Boundary

Một issue quan trọng của vnstock:

```text
quota exhausted
    ↓
sys.exit()
    ↓
SystemExit
    ↓
worker/process có thể chết
```

`SystemExit` không nằm dưới `Exception`.

Không thể dựa vào generic:

```python
except Exception:
```

Đúng boundary để normalize là provider adapter.

Concept:

```python
try:
    result = vnstock_call()
except SystemExit as exc:
    raise ProviderQuotaExhausted(...) from exc
```

Không rải `except SystemExit` khắp codebase.

Adapter phải map quirks upstream thành domain errors:

```text
ProviderQuotaExhausted
ProviderUnavailable
ProviderTimeout
ProviderMalformedResponse
```

Phía collector/scheduler chỉ xử lý domain error.

---

# 72. Redis Failure Policy — Giữ Fail-Closed

Nếu quota arbiter Redis chết, không được:

```text
"limiter lỗi → cứ gọi provider"
```

vì nhiều worker có thể cùng bypass quota.

Đúng policy:

```text
Quota state unavailable
        ↓
Do NOT call provider
        ↓
Collector pauses
        ↓
Serve last-known-good ProviderSnapshot
```

Graceful degradation trong repo này nghĩa là:

> **Phục vụ snapshot cũ có freshness metadata rõ ràng.**

Không phải bypass limiter.

---

# 73. P1 — Provider Data Budget & Observability

Repo đã có spacing/priority nhưng còn thiếu câu trả lời:

> Đã dùng bao nhiêu quota tháng/ngày/giờ?

Đặc biệt cần cho FiinQuant.

## 73.1. Usage ledger

Có thể lưu logical usage events:

```text
provider_usage

provider
operation
requests
symbols
timestamp
lane
success
latency
quota_cost
```

Không nhất thiết mỗi symbol là một row nếu request hỗ trợ batch.

## 73.2. Internal dashboard

Ví dụ:

```text
FiinQuant

Monthly requests
42,817 / 100,000      42.8%

Today's requests
2,381

Peak RPM
38 / 90

Realtime connections
0 / 1

Realtime symbols
0 / 33
```

VNStock:

```text
Minute window
21 / 60

Hourly window
1,930 / 3000

Projected hourly usage
2,640

Backfill backlog
127 jobs
```

## 73.3. Projection

Không chỉ show percentage hiện tại:

```text
42% used
```

mà thêm:

```text
At current usage:
projected month-end = 117,300
```

Budget states:

```text
Healthy     <70%
Watch       70–85%
Conserve    85–95%
Critical    >95%
```

---

# 74. P1 — Graceful Degradation Policy

Degradation phải là policy rõ ràng.

```text
NORMAL
Everything runs

CONSERVE
Reduce backfill / enrichment

HIGH
Only user-critical + portfolio + core market

CRITICAL
Store-only / existing snapshots
```

Ví dụ:

| Job | Normal | Conserve | High | Critical |
|---|---:|---:|---:|---:|
| Core market collector | ✓ | ✓ | ✓ | snapshot |
| Portfolio symbols | ✓ | ✓ | ✓ | snapshot |
| News enrichment | ✓ | ✓ | limited | pause |
| Census | ✓ | limited | pause | pause |
| Historical backfill | ✓ | pause | pause | pause |
| Experimental jobs | ✓ | pause | pause | pause |

Repo đã có lane priority, nên đây là extension tự nhiên.

---

# 75. P2 — Freshness Contract tới tầng AI

`SnapshotMetadata` đã có một phần nhưng freshness cần đi xuyên tới AI/service boundary.

Suggested normalized shape:

```json
{
  "data": {},
  "freshness": {
    "source": "vnstock",
    "sourceTimestamp": "...",
    "fetchedAt": "...",
    "ageSeconds": 124,
    "status": "fresh"
  }
}
```

## 75.1. Freshness status

Chuẩn hóa:

```text
LIVE
FRESH
DELAYED
STALE
UNKNOWN
```

Threshold phải theo data class.

Ví dụ:

- quote 30 giây tuổi có thể đã stale,
- BCTC 30 ngày tuổi vẫn có thể fresh nếu đó là reporting period mới nhất.

## 75.2. `analysis_as_of`

Mỗi AI analysis nên có logical cut-off:

```text
analysis_as_of:
2026-08-23T10:42:31+07:00
```

Và từng source:

```text
quote:         10:42:29
financials:    Q2/2026
news:          10:38
foreign_flow:  10:41
```

AI có thể nói:

> Dựa trên giá cập nhật đến 10:42 và BCTC Q2/2026...

Đây là trust feature.

---

# 76. Cache TTL ≠ Collector Frequency ≠ Data Validity

Không gộp các khái niệm này.

Ví dụ financial statement:

```text
collector refresh:
event-driven / daily check

storage:
permanent

API cache:
hours

AI freshness:
current reporting period
```

Một historical fact như:

```text
Q2/2026 revenue
```

không "expire".

Thứ có thể stale là:

> Hệ thống vẫn nghĩ Q2 là latest sau khi Q3 đã được công bố.

Do đó phải phân biệt:

```text
Data validity
Collector refresh cadence
Cache TTL
Staleness threshold
```

---

# 77. P3 — Shared Stock Intelligence vs Personal Portfolio Intelligence

Đây là contribution kiến trúc quan trọng nhất.

Không chạy full equity analysis per user.

## 77.1. Shared Stock Intelligence

```text
                 GLOBAL / SHARED

                  STB Intelligence
                        │
        ┌───────────────┼──────────────┐
        │               │              │
 fundamentals         events         thesis
 valuation            news           technical
        │               │              │
        └───────────────┼──────────────┘
                        │
                 Shared stock state
```

Base thesis:

```text
STB Base Thesis v17

Fundamental: positive
Valuation: neutral
Momentum: positive
Risks: ...
Catalysts: ...
Evidence: ...
```

Generate lại khi có material event, không theo số user.

## 77.2. Personal Position Intelligence

```text
STB Base Intelligence
+
user cost basis
+
position size
+
portfolio composition
+
investment horizon
=
User Position View
```

Ví dụ:

```text
User A: STB 31%, cost 68
User B: STB 12%, cost 72
User C: STB 42%, cost 55
```

Cùng base thesis, khác Position View.

## 77.3. Lợi ích

- giảm LLM cost,
- symbol-level dedup,
- thesis consistency,
- auditability,
- material-event processing một lần,
- dễ cache và persist.

100 user × 5 positions không đồng nghĩa 500 full analyses.

---

# 78. Symbol-Level Dedup

Ví dụ:

```text
User A: STB FPT HPG
User B: STB MBB HPG
User C: STB FPT VNM
```

Không:

```text
analyze STB × 3
```

Mà:

```text
STB shared intelligence
        ↓
User A position view
User B position view
User C position view
```

Đây là optimization lớn hơn nhiều so với việc chỉ giảm REST round-trips.

---

# 79. Agent Data Access — Tách thành ADR riêng

Ý tưởng aggregate tool như:

```text
get_stock_analysis_context()
```

có thể giảm LLM round-trip, nhưng hiện xung đột trực tiếp với quyết định kiến trúc trong `CLAUDE.md`:

> agent hiện cố ý không đọc first-party system stock data, chỉ dùng bộ web/memory tools hiện tại.

Do đó:

> **Không đưa aggregate stock tool vào quota chapter như một optimization nhỏ.**

Phải tạo ADR riêng:

```text
ADR:
Should the conversational agent gain first-party
Visgnite market-data tools?
```

Đây là thay đổi agent contract, không phải chỉ thay data plumbing.

Về dài hạn, nếu Visgnite muốn là AI-native stock platform, first-party stock/portfolio data tools nhiều khả năng vẫn cần; nhưng quyết định đó thuộc một phase khác.

---

# 80. FiinQuant Capacity phải được model như vector

Không nói đơn giản:

```text
FiinQuant limit = 33 stocks
```

33 là **realtime stream symbol ceiling** của free tier, không phải giới hạn chung cho historical REST.

Theo measurement đã có trong adapter:

```text
realtime stream:
33 symbols ceiling

historical:
~110 symbols measured working in one request

adapter:
MAX_BATCH_SYMBOLS = 100
```

Model capacity đúng hơn:

```text
FiinQuant capacity

requests_per_minute
monthly_requests
connections
stream_symbols
batch_symbols
```

Ví dụ:

### Historical workload

```text
1 REST request
100 symbols
```

### Realtime workload

```text
1 long-lived connection
30 stream slots
0 REST polling
```

---

# 81. FiinQuant Monthly Budget

`100k/month` có hai góc nhìn:

Calendar average:

```text
100,000 / 30
≈ 3,333 requests/day
```

Nếu workload chủ yếu chạy trong khoảng 22 phiên giao dịch:

```text
100,000 / 22
≈ 4,545 requests/trading day
```

Không dùng duy nhất một con số.

Vẫn cần budget theo calendar month vì còn:

- weekend backfill,
- financial ingestion,
- data repair,
- scheduled census,
- enrichment jobs.

---

# 82. Realtime — Future Infrastructure, không over-engineer sớm

Repo hiện:

```text
EOD collector
No market WebSocket
```

`agent/sse.py` là SSE cho agent, không phải market data stream.

Do đó chưa build:

```text
viewer_count
dynamic subscribe/unsubscribe
TTL-based stream churn
5-level subscription priority
```

## 82.1. Realtime V1

Khi cần bảng giá live:

```text
FiinQuant
   │
   │ one long-lived connection
   ▼
Realtime Collector
   │
   ▼
Market State
   │
   ▼
Internal SSE/WebSocket Gateway
   │
   ▼
Browsers
```

Universe ban đầu nên **static hoặc semi-static**.

Ví dụ:

```text
VN30
```

hoặc một fixed set core symbols.

Tránh churn/reconnect trên free tier chỉ có 1 connection.

## 82.2. Dynamic Subscription Manager — chỉ build khi có telemetry

Chỉ cần khi:

```text
actual user demand > stream symbol slots
```

Khi đó mới dựa vào dữ liệu thật:

- most-viewed symbols,
- churn rate,
- provider resubscription semantics,
- reconnect latency,
- active sessions,
- portfolio coverage.

---

# 83. Priority kỹ thuật mới

## P0

```text
VNStock hourly quota cap
+
SystemExit containment
```

Production correctness bug.

## P1

```text
Provider usage accounting
Budget projection
Degradation states
```

## P2

```text
Freshness metadata tới service / AI boundary
```

## P3

```text
Shared Stock Intelligence architecture
```

Phải có trước khi Portfolio AI scale.

## P4

```text
Personal Portfolio Intelligence
```

## P5

```text
Realtime transport
```

Chỉ khi product thực sự cần live board.

---

# 84. Revised Data Architecture

```text
                 EXTERNAL DATA

        VNStock                 FiinQuant
           │                        │
        REST                  REST / future WS
           │                        │
           └───────────┬────────────┘
                       ▼
               Existing Adapters
                       │
            Existing Provider Guard
                       │
               Redis Quota Arbiter
                       │
          + Multi-window Budget Control
                       │
             Existing Collectors
                       │
                  Normalizer
                       │
               ProviderSnapshot
                       │
              Freshness Contract
                       │
               Visgnite Data Layer
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Market         News         Stock
                                      │
                                      ▼
                              Shared Stock Intelligence
                                      │
                                      ▼
                              Personal Portfolio Intelligence
                                      │
                                      ▼
                                    AI
```

---

# 85. Updated Core Principles

```text
1. Request-serving paths remain store-only.
2. Provider access remains collector/ingestion only.
3. Quota is multi-window, not spacing-only.
4. Upstream SystemExit must be contained at adapter boundary.
5. Redis quota failure remains fail-closed.
6. Provider budget must be observable and projected.
7. Graceful degradation means serve last-known-good snapshots.
8. Freshness metadata must reach the AI layer.
9. Stock Intelligence is shared globally.
10. Portfolio Intelligence is personal and derived.
11. Realtime stream limit is separate from REST batch capacity.
12. Do not over-engineer dynamic subscriptions before live telemetry exists.
```

---

# 86. Revised Build Order

Given the current repo state:

```text
Existing provider foundation
        ↓
P0 quota correctness
        ↓
P1 provider budget observability
        ↓
P2 freshness contract
        ↓
P3 shared Stock Intelligence
        ↓
P4 Portfolio Intelligence
        ↓
P5 realtime transport when product requires it
```

Do **not** spend time rebuilding:

- provider contracts,
- adapter abstraction,
- central Redis quota arbitration,
- lane priority,
- collector-only access,
- ProviderSnapshot,
- vnstock cold-data collector,
- CafeF ingestion,
- scheduler.

The architecture should now evolve through **hardening and intelligence reuse**, not reimplementation.
