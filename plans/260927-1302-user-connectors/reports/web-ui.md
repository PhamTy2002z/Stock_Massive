# Web UI — Connectors (P2 Settings + P3 duyệt/composer)

Ngày 27/09/2026 · worktree `feat/user-connectors` · chưa commit.

## File mới

- `apps/web/src/lib/connectors/types.ts` — kiểu wire của `/connectors` (Connector, tool, catalog, pending…).
- `apps/web/src/lib/connectors/api.ts` — client: list/add/PATCH/PUT tool/refresh/accept/DELETE/preferences/oauth start; `safeAuthorizeUrl` chỉ cho điều hướng http(s).
- `apps/web/src/lib/connectors/copy.ts` — nhãn tiếng Việt (trạng thái, xác thực, loại, quyền, Truy cập công cụ), ánh xạ `reason` → câu tiếng Việt, lý do dropped.
- `apps/web/src/lib/connectors/open-pane.ts` — yêu cầu mở Settings đúng pane Kết nối (composer + OAuth return); đọc/xoá query `connector`, `connector_status`, `connector_reason`.
- `apps/web/src/components/connectors/use-connectors.ts` — TanStack Query (`queryKeys.connectors`) + mọi write; kết quả write thay bản cache, không đoán lạc quan.
- `apps/web/src/components/connectors/connectors-pane.tsx` — pane: tabs Của bạn/Khám phá, nút Thêm (Từ danh mục; URL tuỳ chỉnh chỉ khi `custom_url_allowed`), bảng 4 cột, danh mục, form URL tuỳ chỉnh (Không/Khoá/OAuth), thông báo khi `enabled=false`, banner kết quả OAuth.
- `apps/web/src/components/connectors/connector-detail.tsx` — trang chi tiết: ← Kết nối của bạn, bật/tắt, Làm mới, Đăng nhập lại (OAuth) / Cập nhật khoá (header), Ngắt kết nối với xác nhận in-app, Quyền công cụ theo nhóm chỉ đọc/ghi có đếm + chọn hàng loạt, control ba trạng thái, tool ghi khoá "Cho phép" kèm lý do, ghi chú "Máy chủ tự khai báo…", truncated, dropped, diff pending + Xác nhận thay đổi.
- `apps/web/src/components/connectors/connectors-menu.tsx` — submenu "+" › Kết nối: Quản lý kết nối, toggle từng connector (`menuitemcheckbox`), Truy cập công cụ (`menuitemradio`, có dấu chọn + mô tả), ghi chú "có hiệu lực từ lượt hỏi sau". Không vẽ gì khi tính năng tắt.
- `apps/web/src/components/connectors/approval-card.tsx` — thẻ duyệt: tên kết nối + display, nhãn Chỉ đọc/Ghi dữ liệu, arguments_preview monospace (cuộn, giới hạn cao), Cho phép một lần / Luôn cho phép (chỉ khi `can_always`) / Từ chối, đếm ngược theo `expires_at`, chờ `approval.resolved`; 404/409 có câu báo.
- `apps/web/src/components/connectors/use-connector-return.ts` — khi URL có `connector_status`: xoá query, mở Settings › Kết nối.
- `apps/web/src/components/connectors/test-fixtures.ts` — fixture + stub `fetch` theo method/path dùng chung cho test.

## File sửa

- `app/api/alpha-desk/[...path]/route.ts` — thêm `connectors` vào `FORWARDED_RESOURCES` (có comment) và **export `PUT`** (proxy trước đây không có PUT; tool policy + preferences cần).
- `lib/alpha-desk/api.ts` — `createTurn` gửi `client_capabilities: ["approvals"]`; thêm `answerApproval(turnId, callId, decision)`.
- `lib/alpha-desk/types.ts` — 2 event mới, `ApprovalRequest`, `ApprovalDecision`, `SnapshotData.approvals`.
- `lib/alpha-desk/live-turn.ts` — `LiveTurn.approvals`: thêm/xoá theo requested/resolved, thay nguyên từ snapshot, rỗng khi Turn kết thúc; `readApproval` phòng thủ (effect lạ → coi là ghi).
- `components/shell/settings-dialog.tsx` — 1 entry pane `connectors` (nhóm Cấu hình) + khởi tạo pane chọn từ `peekConnectorsPane()`; cả hai chỗ mang comment `// connectors pane: re-register in the new Settings modal shape when it lands`.
- `components/shell/composer.tsx` — `AttachMenu` nhận slot tuỳ chọn `connectors`; composer truyền `<ConnectorsMenu />`.
- `components/shell/view-chat.tsx` — gọi `useConnectorReturn()`; vẽ `ApprovalCards` dưới draft đang chạy.
- Ngoài danh sách được giao nhưng bắt buộc để chạy được: `hooks/use-live-turn.ts` (đăng ký 2 event SSE có tên — EventSource không bắn event có tên nếu không subscribe), `lib/alpha-desk/transcript.ts` (DraftEntry mang `approvals`, `turnId` — optional), `lib/query-keys.ts` (key `connectors`).

## Test đã thêm

- `components/connectors/connectors-pane.test.tsx` (12): bảng + nhãn; pane khi tắt; thêm URL tuỳ chỉnh (POST body đầy đủ); ẩn URL tuỳ chỉnh khi không được phép; thêm từ danh mục (`{catalog_id}`); refusal `url_refused` hiện câu tiếng Việt; PUT quyền 1 tool; tool ghi không chọn được Cho phép + mô tả aria + không lộ `mcp__`; chọn hàng loạt bỏ qua tool đã đúng; ngắt kết nối qua xác nhận in-app → DELETE, `window.confirm` không được gọi; pending/truncated/dropped + POST accept; banner OAuth thất bại.
- `components/connectors/connectors-menu.test.tsx` (4): toggle → PATCH `{enabled:false}`; Truy cập công cụ → PUT `/connectors/preferences`; Quản lý kết nối yêu cầu mở pane; không vẽ khi tắt.
- `components/connectors/approval-card.test.tsx` (6): mỗi nút gửi đúng decision tới `/turns/{id}/approvals/{call_id}` rồi chờ; tool ghi không có Luôn cho phép, nhãn ghi, preview mono, đếm ngược; 409 cho phép thử lại; hết hạn thì khoá.
- `lib/connectors/open-pane.test.ts` (4): đọc/xoá query OAuth return; `safeAuthorizeUrl` chặn `javascript:`.
- `lib/alpha-desk/live-turn.test.ts` (+4, describe "approval cards"): requested/resolved, effect lạ + thiếu call_id, khôi phục từ `snapshot.approvals`, rỗng khi kết thúc.
- `lib/alpha-desk/api.test.ts` (+2, describe "connector approvals"): `client_capabilities: ["approvals"]`; `answerApproval` path/body.

## Lệnh đã chạy

- `pnpm --dir apps/web install --frozen-lockfile` — ok (worktree chưa có node_modules).
- `pnpm --dir apps/web lint` — sạch.
- `pnpm --dir apps/web type-check` — sạch.
- `pnpm --dir apps/web test` — 52 file, 556 passed, 4 skipped (trước thay đổi: 48 file, 524 passed).
- `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build` — build thành công. Build ghi lại `next-env.d.ts` trỏ `.next-verify`; đã `git checkout` trả về như cũ.
- Không chạy dev server / e2e; không còn tiến trình nền.

## Ghi chú / giới hạn

- Mở pane từ ngoài dùng một biến module (`open-pane.ts`) vì Settings giữ pane trong state riêng; khi Settings modal mới về thì đăng ký lại theo shape mới.
- OAuth return mở overlay ở task kế (`setTimeout 0`) vì effect khôi phục view của shell chạy sau và đóng mọi overlay.
- Flyout composer mở sang phải menu "+"; trên màn rất hẹp có thể tràn — đổi sang dạng drill-in nếu cần.
- Không cập nhật phase file (trạng thái plan do orchestrator quản).
