# Phase 02 — Đường nhị phân qua proxy

## Đã sửa

- `apps/web/src/app/api/alpha-desk/[...path]/route.ts`
  - `attachments` vào `FORWARDED_RESOURCES`, kèm lý lẽ chủ quyền giống `artifacts`/`messages` (upstream `POST /attachments` + `GET /attachments/{id}`, ownership qua account lưu row, không qua request).
  - `forward`: đọc `Content-Type` request một lần (`requestContentType`), định nghĩa `isJsonRequest` (không có header **hoặc** `application/json` → JSON). Non-GET: JSON đọc `text()` như cũ; khác JSON đọc `arrayBuffer()`.
  - `send`/`dispatch` nhận thêm tham số `contentType`, forward nguyên header đó tới upstream (fallback `application/json` khi request không khai) — sửa luôn lỗi #3 (hardcode Content-Type) nêu trong phase file.
  - Vị ngữ response đổi tên: `path[0] === "assets"` → hàm `isJsonResponse` (whitelist theo Content-Type, không có header cũng tính là JSON để không đổi hành vi mặc định cũ). `!isJsonResponse(response)` đi `passthrough`.
  - `passthrough` copy thêm `Content-Disposition` và `X-Content-Type-Options` khi upstream có set (không tự bịa khi thiếu).
  - Docstring đầu file viết lại đoạn "Two bodies" thành "Two directions, three body shapes" phản ánh đúng ba nhánh hiện có.
- `apps/web/src/lib/alpha.ts`
  - `sendAlpha`: khi `init.body instanceof FormData` thì không set `Content-Type` (để browser tự tính boundary); path JSON giữ nguyên default `application/json`. Không đụng cookie/retry 401.

## Quyết định replay (bước 6)

**Chọn buffer.** Cả nhánh JSON (`text()`) lẫn nhánh nhị phân (`arrayBuffer()`) đều đọc **toàn bộ** body thành một giá trị phẳng (string / `ArrayBuffer`) trước khi gọi `send` lần đầu — không phải stream, nên `fetch` lần hai (retry sau 401) nhận lại đúng byte đó, không phải một stream đã cạn. Đây không phải quyết định mới: đường JSON đã buffer từ trước (`.text()`), bước này chỉ mở rộng đúng nguyên tắc đó sang nhị phân thay vì chọn nhánh "fail và bắt client thử lại". Lý do ghi tại chỗ đọc (`route.ts` trong `forward`, ngay trước dòng gán `body`) và trong docstring đầu file. Rủi ro RAM (Risk Assessment của phase file) đã note lại đúng cụm từ "một upload's bytes trong bộ nhớ trong thời gian một request" — không phải rủi ro mới, cùng bản chất với JSON buffer sẵn có, và trần bytes của phase 05 phải tính khoản này (đã ghi trong comment).

Test `binary-transport.test.ts` xác nhận buffer replay được: mock 401 rồi 200, so hash byte-for-byte của body gửi ở cả hai lần gọi `fetch`.

## Test

- Tạo mới: `apps/web/src/app/api/alpha-desk/binary-transport.test.ts` (9 case) — multipart POST byte-for-byte tới upstream (so SHA-256, không phải string) + boundary header sống sót; replay 401 giữ nguyên byte; GET nhị phân byte-for-byte về browser; `Content-Disposition`/`X-Content-Type-Options` sống sót qua `passthrough` và **không** bị bịa khi upstream không set (case `assets`); đường JSON gửi/nhận không đổi (body vẫn là string, không phải buffer); `attachments` được carry; resource lạ (`downloads/report.pdf`) vẫn 404 trước khi gọi `fetch`.
- Thêm hai case vào `apps/web/src/lib/alpha.test.ts` (đã có sẵn, không tạo mới): `FormData` không có `Content-Type` trong header gửi đi; body JSON thường vẫn có `Content-Type: application/json`.
- Test cũ (`proxy.test.ts`, `origin-check.test.ts`, `streaming-proxy.test.ts`) không sửa, chạy lại nguyên trạng — pass, xác nhận không hồi quy luật allowlist/origin/401-retry/event-stream.

## Kết quả 4 cổng

- `pnpm type-check`: **pass**.
- `pnpm lint`: **pass**.
- `pnpm test`: **pass** — 60/60 file, 750/750 test (bao gồm 9 test mới + 2 test mới thêm vào `alpha.test.ts`). Log "recharts could not build a scale…" trong `signal-desk-block-boundary.test.tsx` là console error của một component cố tình "Exploding" trong test error-boundary có sẵn, không liên quan thay đổi này — test đó vẫn nằm trong 750 pass.
- `pnpm build`: **chưa chạy**. Có `pnpm dev` đang chạy trên cổng 3000 (tiến trình `next dev` từ ~1:02AM sáng nay của phiên làm việc); build production sẽ ghi đè `.next` và làm dev server hiện tại mất CSS/gãy theo ghi nhận cũ của repo. Không tự ý dừng tiến trình người khác — cần user xác nhận dừng `pnpm dev` trước, hoặc tự chạy `pnpm build` khi rảnh cổng.

## Số dòng trong plan vs code thật

- `route.ts:66-75` (FORWARDED_RESOURCES) — khớp đúng dải dòng lúc bắt đầu.
- `route.ts:192` (đọc body) — khớp đúng.
- `route.ts:312-322` (dispatch hardcode Content-Type) — thực tế ở dòng 305-325 (hàm `dispatch` bắt đầu 305, khối header 313-321) — lệch nhẹ do các đoạn code phía trên dài hơn ước tính, không ảnh hưởng nội dung.
- `route.ts:223-225` (passthrough predicate cũ) — thực tế đúng dòng 223 (`if (path[0] === "assets") return passthrough(response)`), khớp.
- `lib/alpha.ts:197` (hardcode Content-Type) — khớp chính xác dòng 197.

## Ranh giới freeze

Không đụng file nào ngoài hai file `route.ts` + `lib/alpha.ts` và hai test file liên quan (`binary-transport.test.ts` mới, `alpha.test.ts` đã tồn tại từ trước — chỉ thêm case). Không đụng `SignalDeskToggle` hay bất kỳ surface UI nào khác.

Status: DONE_WITH_CONCERNS
Summary: Đường nhị phân qua proxy đã mở đủ bốn nhánh (request non-JSON buffer arrayBuffer + forward Content-Type, response non-JSON qua passthrough theo content-type, hai header mới sống sót, FormData không bị ép Content-Type); type-check/lint/test đều pass, build chưa chạy vì có dev server đang mở cổng 3000.
Concerns/Blockers: `pnpm build` chưa chạy được — cần user xác nhận dừng `pnpm dev` (PID 52339/52337/54339 nhóm tiến trình `next dev -p 3000`) trước khi build, hoặc tự chạy `pnpm build` lúc dev server rảnh cổng.
