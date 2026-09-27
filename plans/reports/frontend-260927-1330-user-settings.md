# Frontend — Cài đặt người dùng (260927)

Trạng thái: xong phía web. Không còn hàng `soon` nào trong Cài đặt. Hàng nào không làm được thì đã gỡ khỏi giao diện. API backend (memory, `/auth/*` mới, `DELETE /threads`) chưa có trên dev (proxy chuyển tiếp được nhưng upstream trả `{"detail":"Not Found"}`), nên UI hiện lỗi hoặc toast chứ không dựng dữ liệu giả.

## Từng hàng làm gì

**Chung**
- Giao diện › Chế độ màu: giữ nguyên (next-themes).
- Giao diện › Chuyển động `Hệ thống | Giảm`: lưu `motion` trong `alpha-desk.preferences`. Khi chọn Giảm, `<html data-motion="reduced">` được đặt ngay lúc chọn. Một script inline trong `<head>` của `layout.tsx` đặt thuộc tính này trước lần vẽ đầu tiên. Trong `globals.css` có khối `[data-motion="reduced"] *` tắt mọi animation, transition và smooth scroll của CSS, vì các biến thể `motion-safe:`/`motion-reduce:` của Tailwind chỉ đọc media query. Ba chỗ đang tự kiểm tra `matchMedia` bằng JS nay đi qua `motionReduced()`: hiệu ứng hiện câu trả lời từng chữ, thời gian đóng inspector và animation của biểu đồ.
- Hội thoại › Signal Desk mặc định: giữ nguyên. Vì `SIGNAL_DESK_PAUSED = true` nên cả section không được render.
- Thông báo › Thông báo khi có câu trả lời (`notifyOnAnswer`): khi bật sẽ gọi `Notification.requestPermission()`. Nếu bị từ chối thì công tắc vẫn tắt và bị vô hiệu, mô tả ghi "Trình duyệt đang chặn thông báo…". Trình duyệt không có `Notification` thì công tắc bị vô hiệu và có câu giải thích.
- Thông báo › Âm báo khi xong (`soundOnAnswer`): phát hai nốt sine ngắn qua WebAudio, không cần file âm thanh. Âm được phát thử một lần ngay khi bật.
- Điểm kích hoạt: `hooks/use-live-turn.ts`, là nơi duy nhất client biết một Turn đã kết thúc (không mở thêm SSE). Chỉ báo cho Turn mà lần mount này thấy đang chạy, và chỉ khi `document.hidden`. Turn bị hủy thì không báo. `tag` là turnId, bấm vào thông báo sẽ `window.focus()`.

**Tài khoản**
- Hồ sơ: ảnh đại diện dùng chữ cái đầu như trước. Họ và tên lưu khi blur hoặc Enter nếu có thay đổi và không rỗng; nếu lỗi thì trả lại giá trị cũ và báo toast. Tên gọi (rỗng thì gửi `null`). Phong cách đầu tư là `<select>` native có `appearance-none` và icon chevron. Hướng dẫn riêng có bộ đếm `n/1500`, nút Hủy/Lưu chỉ hiện khi có sửa đổi. Mỗi thao tác chỉ gửi đúng key của nó. Khi PATCH thành công thì ghi user trả về vào cache `queryKeys.currentUser` và báo toast "Đã lưu".
- Bảo mật: Email kèm nút chép. Đổi mật khẩu dùng form inline với 3 trường `type=password` và `autoComplete` phù hợp. Client kiểm tra mật khẩu mới ≥ 8 ký tự, khác mật khẩu cũ và khớp ô nhập lại. Lỗi 400 hiện "Mật khẩu hiện tại không đúng". Khi thành công, server action ghi cặp token mới vào cookie httpOnly. Đăng xuất khỏi mọi thiết bị dùng xác nhận 2 bước: `logoutAllAction` xóa cookie, sau đó gọi `signOut()` giống menu tài khoản.
- Token nằm trong cookie httpOnly, nên ba thao tác ghi tài khoản chạy qua server action `app/(auth)/account-actions.ts`. File này kiểm tra lại mọi đối số và chỉ cho qua các key đã biết. Nó dùng `withAccessToken` (trong `lib/auth/bearer.ts`), cơ chế thử lại một lần sau khi xoay token giống proxy.

**Bộ nhớ** (pane mới, icon `Brain`)
- Công tắc Cho phép ghi nhớ ghi `preferences.memory_enabled` bằng optimistic update, hoàn lại nếu lỗi.
- Section "Đã ghi nhớ (n)": `useInfiniteQuery` với key `queryKeys.memoryFacts`, phân trang theo offset. Offset tiếp theo là số mục đã tải, nên xóa một mục không làm lệch trang. Mỗi dòng có tiêu đề, nội dung giới hạn 2 dòng, dòng meta (mã, nguồn có link `noopener noreferrer`, "Số liệu ngày" và "Ghi nhớ ngày" dạng dd/mm/yyyy theo giờ HCM dùng `formatVietnamDate`) và nút Xóa ghi nhớ. Có skeleton khi tải, trạng thái rỗng, nút Thử lại khi lỗi và "Xem thêm". Xóa toàn bộ dùng xác nhận 2 bước.

**Quyền riêng tư**
- Xuất dữ liệu: gọi `listThreads` rồi `fetchThread` với tối đa 3 request cùng lúc, nút hiện "Đang xuất 3/12…". Sau đó đọc hết các trang memory facts và tải về `visgnite-du-lieu-YYYY-MM-DD.json` (ngày theo giờ VN) qua Blob; object URL được revoke sau khi tải.
- Xóa toàn bộ hội thoại dùng xác nhận 2 bước, gọi `DELETE /threads`. Sau đó cache danh sách được đặt rỗng, bỏ mọi `["thread", id]`, gọi `desk.newThread()` (cùng hàm sidebar dùng khi xóa hội thoại đang mở) và invalidate.

**Hạn mức**: giữ nguyên.

## Đã gỡ và lý do
- Sắc màu tăng / giảm và thẻ Xem trước: gỡ, lý do ở mục tiếp theo.
- Phông chữ số liệu; Gợi ý sau mỗi câu trả lời; Tự động đặt tên; Ngôn ngữ trả lời: gỡ theo yêu cầu.
- Âm thanh ở mục Hội thoại chuyển sang mục Thông báo. Email và "Im lặng ngoài phiên": gỡ.
- Đổi email, Xác thực hai bước, Phiên đang hoạt động (cũ): gỡ.
- Lưu lịch sử, Tự động xóa: gỡ.
- Các primitive `SoonBadge`, prop `soon`, `SelectStub`, `TextFieldStub` đã bị xóa. `SEGMENT_TRACK`/`segmentItem` chuyển thành nội bộ. Primitive mới: `TextField`, `SelectField`, `ConfirmAction` (dùng chung cho cả 3 thao tác phá hủy), hằng `FIELD`, và `PillAction` thêm `type`/`label`/`autoFocus`/tone `danger-filled`.

## Quyết định về quy ước màu: GỠ
Biểu đồ không thể đổi màu theo CSS token:
- `components/signal-desk/signal-desk-panel.tsx` vẽ bằng `echarts.init(..., { renderer: "canvas" })`. Canvas không đọc được `var(--positive)`.
- Cùng file đó (dòng 18–21) ghi rằng theme của ECharts được merge *dưới* option, nên "every colour… Flint chose still wins". Vì vậy một theme không thể ghi đè màu nến của Flint.
- `lib/flint/compile-visual.ts` (dòng 13–18) và CLAUDE.md cấm chỉnh sửa hoặc xử lý thêm output của Flint.

Nếu vẫn làm, việc đổi `--positive`/`--negative` qua `data-convention` sẽ chỉ đổi màu chữ và chip, còn biểu đồ vẫn theo chiều ngược lại. Như vậy tệ hơn là không có tùy chọn nào.

## Kiểm chứng
- `pnpm --dir apps/web type-check`: sạch.
- `pnpm --dir apps/web lint`: sạch.
- `pnpm --dir apps/web test`: 49 file, 550 passed, 2 skipped.
- Test mới trong `settings-dialog.test.tsx`: PATCH chỉ gửi key thay đổi (tên, phong cách, hướng dẫn); không gửi khi không đổi hoặc rỗng; hoàn lại khi bị từ chối; danh sách bộ nhớ hiển thị và gọi `deleteMemoryFact(7)`; xác nhận 2 bước (xóa bộ nhớ, xóa hội thoại, đăng xuất mọi thiết bị) cần đủ 2 lần bấm và có thể Hủy; thông báo không bật khi quyền bị từ chối; đổi mật khẩu (kiểm tra ở client và lỗi 400); Chuyển động đặt hoặc bỏ `data-motion`.
- Test mới khác: `answer-alert.test.ts` và các test motion trong `preferences.test.ts`, gồm cả việc chạy script khởi động.
- `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build`: thành công.
- Dev server :3000 (không khởi động lại): script chuyển động có trong `<head>`; `/api/alpha-desk/memory/facts` được proxy chuyển tiếp, upstream trả 404 vì backend chưa gắn route.

## Ngoài danh sách file được giao (cần xác nhận)
- `app/api/alpha-desk/[...path]/route.ts`: thêm `memory` vào allowlist. Không có dòng này thì trình duyệt không tới được `/memory/*`.
- `hooks/use-revealed-text.ts`, `components/shell/inspector.tsx`, `components/signal-desk/signal-desk-panel.tsx`: mỗi file sửa một dòng để dùng `motionReduced()`. Nếu không, chế độ "Giảm" sẽ không dừng hiệu ứng hiện chữ của câu trả lời như mô tả của hàng đã hứa.
- File mới: `app/(auth)/account-actions.ts`, `lib/alpha-desk/answer-alert.ts` (+test), `components/settings/memory-section.tsx`.

## Còn mở
- `view-chat.tsx` (không được sửa) vẫn gọi `scrollTo({behavior:"smooth"})` dựa trên media query của hệ thống. CSS không chặn được smooth scroll gọi từ JS, nên ở chế độ Giảm transcript vẫn cuộn mượt.
- Thông báo cho Turn thất bại dùng câu "Câu hỏi chưa được trả lời. Mở lại để thử lại." thay vì "Câu trả lời đã sẵn sàng.", vì câu đó sẽ sai.
- Chú thích `.vg-figure` trong `globals.css` vẫn nói màu tăng/giảm "can be swapped by the reader". Câu này không còn đúng, nhưng nằm ngoài khối motion nên tôi không sửa.
