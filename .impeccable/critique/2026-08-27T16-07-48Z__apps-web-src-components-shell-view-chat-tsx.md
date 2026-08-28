---
target: "toàn bộ UI/UX trang chat hiện tại trong Image #1"
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 5
timestamp: 2026-08-27T16-07-48Z
slug: apps-web-src-components-shell-view-chat-tsx
---
Method: dual-agent (A: /root/design_review · B: /root/detector_evidence)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | Trạng thái gửi, huỷ, retry và refusal khá tốt; empty state không cho biết phiên thị trường, độ mới dữ liệu hay khả năng hiện tại. |
| 2 | Match System / Real World | 2 | Copy về mã/ngành/thị trường đúng domain, nhưng “Evening”, “Visgnite Pro” và icon waveform không khớp ngôn ngữ/tác vụ của nhà đầu tư Việt. |
| 3 | User Control and Freedom | 3 | Có stop, retry, edit/resend, tìm và mở hội thoại; delete không có undo và nhiều nút dẫn vào luồng không thể hoàn thành. |
| 4 | Consistency and Standards | 2 | Token, spacing và visual language nhất quán; chevron không mở selector, waveform lại có nghĩa “gửi”, trigger bật menu toàn item disabled. |
| 5 | Error Prevention | 2 | Chặn gửi rỗng và giữ draft; vẫn cho mở Share không thể chia sẻ, xoá thread thiếu recovery, cảnh báo đầu tư không có ở lần vào đầu tiên. |
| 6 | Recognition Rather Than Recall | 2 | Composer và lịch sử hiện rõ; title bị cắt, thiếu prompt starters và ngữ cảnh/timestamp khiến user phải nhớ thread nào chứa nghiên cứu gì. |
| 7 | Flexibility and Efficiency | 2 | Có Enter-to-send, Cmd/Ctrl+K, history và resend; thiếu visible accelerators, tổ chức history cho power user và thao tác nhanh theo ticker. |
| 8 | Aesthetic and Minimalist Design | 2 | Bình tĩnh, sạch và có craft; khoảng trống quá lớn cùng roadmap controls disabled khiến màn hình giống prototype chưa hoàn thiện. |
| 9 | Error Recovery | 3 | Refusal, partial output, stop và retry tốt; clipboard fail im lặng, không có “về câu trả lời mới nhất”, share chỉ báo dead-end sau khi click. |
| 10 | Help and Documentation | 1 | Placeholder là hướng dẫn duy nhất; Help bị disabled, không có ví dụ câu hỏi, cấu trúc đầu ra hay giải thích evidence contract. |
| **Total** | | **22/40** | **Acceptable — nền tảng ổn, cần cải thiện đáng kể trước khi trải nghiệm hoàn chỉnh.** |

## Design Specificity Verdict

**Kết luận: có bản sắc ở lớp thị giác, còn generic ở lớp trải nghiệm.** Cool-slate palette, Newsreader greeting, Visgnite mark và nhịp compact tạo cảm giác được thiết kế có chủ đích. Nhưng cấu trúc “sidebar lịch sử + lời chào + composer giữa màn hình + model label + share” có thể thay logo để trở thành bất kỳ AI chat nào. Điểm khác biệt thật của VisgniteAI — dữ liệu Việt Nam theo thời điểm, nguồn, độ chắc chắn, phản biện, điều kiện vô hiệu — gần như không xuất hiện trước câu hỏi đầu tiên.

**LLM assessment:** Medium-low specificity. Màn hình đẹp hơn một template thô nhưng chưa kể được câu chuyện “evidence-backed investment research desk”.

**Deterministic scan:** Detector sạch ở cả `view-chat.tsx` và 17 file trong `components/shell`: 0 finding, exit code 0. Đây là tín hiệu tốt về các anti-pattern mà detector biết, không phải bằng chứng UX đã hoàn chỉnh. Scan không thể phát hiện dead affordance theo product truth, title truncation, khoảng trống thiếu nhiệm vụ hay reassurance đến quá muộn.

**Visual overlay:** Không có overlay đáng tin cậy. Browser preflight cho phép mutation, nhưng fresh context bị redirect tới `/login?next=%2F`; inject detector ở đó sẽ annotate sai surface. Screenshot đăng nhập sẵn được dùng làm visual fallback.

## Overall Impression

Đây là một shell có gu và nền tảng engineering tốt, nhưng empty state đang truyền đạt “AI chat tối giản” thay vì “bàn nghiên cứu đầu tư có bằng chứng”. Cơ hội lớn nhất không phải thêm decoration; đó là biến vùng trống thành một research launchpad rất nhẹ, cho user biết nên hỏi gì, hệ thống trả lời theo chuẩn nào và dữ liệu đang mới đến đâu.

## What’s Working

- **Visual foundation có kỷ luật:** cool tonal ladder, amber được tiết chế, serif/sans phân vai rõ, không rơi vào casino/neon fintech.
- **Primary action dễ thấy:** greeting và composer có hierarchy rõ, measure 680px dễ đọc, placeholder chạm đúng ba scope “mã / ngành / thị trường”.
- **In-conversation resilience tốt:** draft vẫn dùng được khi answer chạy, có stop, partial output, reasoning status, refusal rõ, retry, sources/canvas và reduced-motion support.

## Priority Issues

### 1. [P1] Empty state không biểu đạt lợi thế evidence-led

**Why it matters:** User không biết câu trả lời sẽ khác chatbot phổ thông ở đâu, cũng không biết một prompt tốt trông như thế nào. Điều này làm giảm activation và trust ngay lần đầu.

**Fix:** Đặt cluster hơi cao hơn tâm màn hình. Dưới composer thêm 3–4 starter theo task, không theo feature: “Tóm tắt thị trường hôm nay”, “Phân tích luận điểm cho một mã”, “So sánh hai mã”, “Tìm yếu tố có thể phủ định luận điểm”. Mỗi starter hứa ngắn gọn output như “nguồn · thời điểm · rủi ro”. Collapse sau khi conversation bắt đầu.

**Suggested command:** `$impeccable onboard`

### 2. [P1] Affordance trông dùng được nhưng dẫn tới ngõ cụt

**Why it matters:** Share mở dialog rồi báo API chưa có endpoint; title menu chứa toàn item disabled; Attach chứa bảy item disabled; “Visgnite Pro” có chevron nhưng chỉ là span. Mỗi lần click làm user học rằng UI không đáng tin.

**Fix:** Chỉ render action có hành vi thật. Ẩn Share đến khi thread shareable và endpoint tồn tại; bỏ chevron khỏi label tĩnh; bỏ menu toàn disabled; chuyển roadmap previews sang một surface thông tin riêng nếu thật sự cần.

**Suggested command:** `$impeccable distill`

### 3. [P1] Sidebar history là một bức tường title ít thông tin

**Why it matters:** User quay lại nghiên cứu cũ phải scan hơn 14 dòng đồng hạng, nhiều title bị cắt và không có ticker, thời gian hay trạng thái. Đây là chi phí lặp lại mỗi ngày đối với power investor.

**Fix:** Group theo “Hôm nay / 7 ngày qua / Cũ hơn”; thêm ticker chip và timestamp/as-of khi có thật; chỉ mở một số dòng ban đầu rồi “Xem thêm”; title đầy đủ qua accessible tooltip; ẩn section “Đã ghim” khi rỗng và không đặt watchlist disabled vào nhóm này.

**Suggested command:** `$impeccable layout`

### 4. [P1] Reassurance cho tác vụ tài chính đến sau lần cam kết đầu tiên

**Why it matters:** Opening state chưa nói nguồn, as-of time, độ không chắc chắn hay boundary “research support, not trading advice”. Disclaimer chỉ xuất hiện ở composer docked sau khi thread đã tồn tại, đúng lúc user đã gửi câu hỏi high-stakes.

**Fix:** Thêm một dòng trust copy dưới opening composer: câu trả lời nêu nguồn, thời điểm dữ liệu và bất định; không phải khuyến nghị giao dịch. Khi dữ liệu live có sẵn, hiển thị market/data freshness thực, không hard-code.

**Suggested command:** `$impeccable clarify`

### 5. [P1] Mobile navigation chưa có mô hình drawer đúng

**Why it matters:** Reducer tự đóng sidebar dưới 768px, nhưng khi user mở lại, sidebar 274px trở thành một cột flex trong viewport. Ở màn 390px, main chỉ còn khoảng 116px thay vì sidebar overlay/drawer; core chat bị bóp vỡ.

**Fix:** Dưới 768px, render sidebar thành fixed drawer có scrim, focus trap, Escape/backdrop close và body/main không đổi width. Kiểm tra composer, inspector full-screen, thread list và touch targets ở 390/430px trong cùng một pass.

**Suggested command:** `$impeccable adapt`

## Còn thiếu gì để hoàn thiện UX

| Khu vực | Thiếu hiện tại | Trạng thái hoàn thiện nên có |
|---|---|---|
| Activation | Prompt starters, ví dụ đầu ra, trust contract | User hiểu trong 5 giây nên hỏi gì và sẽ nhận loại bằng chứng nào |
| Market context | Session/data freshness/as-of ở opening | Status động từ dữ liệu thật, không badge trang trí hoặc hard-code |
| Composer | Send semantics rõ, selector thật hoặc label tĩnh, keyboard hint, ít nhất một attach action thật | Không chevron giả; arrow send quen thuộc; `Enter gửi · Shift+Enter xuống dòng`; desktop autofocus có chủ đích |
| History | Recency groups, ticker/context, thời gian, full-title access | Tìm lại thesis cũ mà không phải nhớ title bị cắt |
| Long conversation | Scroll-to-latest/new-content affordance | Khi user cuộn lên trong lúc stream, có nút báo nội dung mới và quay về cuối |
| Destructive/recovery | Undo delete, copy failure feedback | Thread nghiên cứu không mất vĩnh viễn vì một click; action lỗi nói rõ cách xử lý |
| Sources/trust | Answer-level as-of/freshness summary nổi bật hơn | Figure quan trọng luôn gắn nguồn, thời điểm và quality state, không buộc mở panel để biết |
| Responsive | Sidebar drawer, 44px touch targets, safe areas | One-handed mobile không bóp main column; composer không va bàn phím/safe-area |
| Accessibility/i18n | Việt hoá ARIA strings, menu keyboard behavior, contrast disabled text | Screen reader nghe cùng ngôn ngữ với UI; menu hỗ trợ chuẩn; roadmap text không thành noise mờ |
| Product polish | Loại dev tool khỏi production/stakeholder capture | Bottom-corner Agentation/canvas fixture chỉ tồn tại trong dev và không che account/composer |

## Cognitive Load

**4/8 checklist failures → high cognitive load, dù canvas nhìn rất quiet.**

- Fail — Chunking: 14+ history rows gần như đồng hạng.
- Fail — Minimal choices: toàn sidebar có khoảng 18 destination/item; Attach mở 7 lựa chọn và tất cả đều disabled.
- Fail — Working memory: title bị truncate buộc user nhớ nội dung thread.
- Fail — Progressive disclosure: roadmap control luôn hiện trong daily workspace.
- Pass — Single focus, grouping, visual hierarchy và one-thing-at-a-time ở empty state.

Decision points vượt bốn option: conversation selection (14+), sidebar-wide navigation (~18), attachment menu (7).

## Emotional Journey

- **Entry peak:** Lời chào cá nhân hoá bằng Newsreader tạo sự ấm áp và khác biệt.
- **Orientation valley:** “Evening” phá Vietnamese-first flow; khoảng trống lớn không cung cấp bằng chứng rằng đây là research desk nghiêm túc.
- **Commitment gap:** Không reassurance trước câu hỏi đầu tư đầu tiên.
- **Waiting:** Reasoning status, cancel, refusal, retained partial output và retry là phần mạnh nhất.
- **End-state risk:** Share kết thúc bằng “API chưa có endpoint”; ngõ cụt này dễ được nhớ hơn lời chào đẹp.

## Persona Red Flags

**Alex — power investor:** Flat history và title bị cắt làm chậm việc quay lại luận điểm cũ; thiếu ticker/as-of metadata; không có path nhanh theo mã. Cmd/Ctrl+K và Enter-to-send là điểm cộng nhưng chưa đủ cho daily research.

**Jordan — first-time investor:** Không có ví dụ câu hỏi tốt, không giải thích nguồn/as-of/uncertainty; dễ hiểu “Visgnite Pro” là selector trả phí và waveform là voice input; click thử các affordance lại gặp toàn “Sắp ra mắt”.

**Sam — accessibility-dependent user:** Icon controls có accessible name/focus ring khá tốt, nhưng 28–34px nhỏ cho motor/touch use, menu custom thiếu arrow-key semantics, một số ARIA label vẫn tiếng Anh, disabled microcopy có nguy cơ contrast thấp và history dài tạo linear traversal tốn kém.

## Minor Observations

- “Trò chuyện mới” lặp ở sidebar và top bar nhưng sidebar không có active state tương ứng.
- Greeting tiếng Anh trong UI Vietnamese-first nên đổi thành “Chào buổi tối…” hoặc một câu Việt tự nhiên hơn.
- Waveform icon nên dành cho voice; send nên dùng arrow/paper-plane trừ khi voice thực sự tồn tại.
- Account name và hàng cuối sidebar đang bị dev toolbar che trong screenshot; source xác nhận Agentation/canvas fixture đã gate theo production, nên đây là artifact của môi trường dev chứ không phải detector finding.
- Opening cluster nên nằm trên optical center một chút; hiện tại khoảng trống phía trên/dưới đọc như unfinished hơn là calm.
- Clean detector không phủ nhận các vấn đề này: detector chỉ trả 0 rule finding ở source, còn phần lớn finding là product truth, interaction promise và IA.

## Questions to Consider

- Nếu moat của VisgniteAI là bằng chứng theo thời điểm, tại sao user không thấy bất kỳ dấu hiệu nào về điều đó trước câu hỏi đầu tiên?
- Daily workspace có nên quảng bá roadmap bằng disabled controls, hay chỉ nên chứa các hành động có thể hoàn tất ngay?
- Empty state sẽ thay đổi thế nào nếu mục tiêu là dạy một thói quen nghiên cứu đầu tư tốt trong 10 giây?
- Với mobile, sidebar nên là navigation drawer tạm thời hay một surface điều hướng thay thế hoàn toàn?
