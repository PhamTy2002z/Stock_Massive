---
phase: 2
title: "Đường nhị phân qua proxy"
status: done
priority: P1
effort: "4h"
dependencies: [1]
---

# Phase 02: Đường nhị phân qua proxy

## Overview

Mở một đường nhị phân qua proxy Next **trước** khi kho đính kèm chốt contract.
Bản đầu để việc này là "một câu hỏi ở bước 1 của phase UI" — trong khi nó là bốn
lỗi xác định, một trong đó im lặng, và nó quyết định cả hình dạng endpoint.

## Requirements

- Functional: `POST` nhị phân đi được từ browser tới FastAPI nguyên bytes; `GET`
  nhị phân về được browser nguyên bytes.
- Non-functional: luật auth + retry 401 hiện có không bị phá; đường JSON hiện có
  không đổi một byte payload nào.

## Architecture

### Bốn lỗi, đọc từ code

| # | Lỗi | Chỗ |
|---|---|---|
| 1 | `attachments` không trong `FORWARDED_RESOURCES` → 404 *"Unknown Alpha Desk resource"* trước khi tới bất kỳ câu hỏi transport nào | `route.ts:66-75` |
| 2 | `const body = ... await request.text()` — UTF-8 hoá body request, phá boundary multipart | `route.ts:192` |
| 3 | `dispatch` hardcode `"Content-Type": "application/json"` cho mọi request chuyển tiếp | `route.ts:312-322` |
| 4 | `passthrough` chỉ cho `path[0] === "assets"`; còn lại `await response.text()` → **ảnh hỏng trong im lặng** | `route.ts:223-225` |

Lỗi 4 là lỗi nguy hiểm nhất vì nó không có status code, không có log. Và chính
docstring của file, `:39-45`, đã tả đúng nó cho favicon: *"`await response.text()`
decodes the upstream body as UTF-8 text, which is exactly wrong for an image — it
would replace bytes the decoder cannot represent and hand the browser a corrupted
favicon."*

Lỗi thứ năm ở tầng client: `lib/alpha.ts:197` cũng hardcode
`"Content-Type": "application/json"`, nên một `FormData` không bao giờ có boundary.

### Ràng buộc phải giữ: replay của retry 401

`route.ts:192` có bình luận: *"Read once: a request body is a stream and cannot be
replayed into the retry."* Một body nhị phân muốn replay được thì phải **buffer**.
Đây là ràng buộc thật, không phải chi tiết: quyết định giữa "buffer để replay
được" và "nạp trùng token rotation thì fail và client thử lại" phải lấy ở đây,
có ghi lý do.

## Related Code Files

- Modify: `apps/web/src/app/api/alpha-desk/[...path]/route.ts`
- Modify: `apps/web/src/lib/alpha.ts` — một lối gửi không-JSON
- Create/Modify: test cho route proxy (kiểm repo có test cho `route.ts` chưa; nếu chưa, đây là test đầu tiên của nó)

## Implementation Steps

1. `attachments` vào `FORWARDED_RESOURCES`, **kèm lý lẽ chủ quyền** như mọi entry
   khác trong danh sách đó có.
2. Đường request: với method không-GET và `Content-Type` không phải JSON, đọc
   `await request.arrayBuffer()` và chuyển tiếp nguyên `Content-Type` của request
   (gồm boundary). Đường JSON giữ nguyên `await request.text()`.
3. Đường response: đổi vị ngữ của `passthrough` từ so tên resource sang **so
   content type** — mọi response không phải `application/json` và không phải event
   stream đi qua `passthrough`. Đừng thêm một tên resource hardcode thứ hai.
4. `passthrough` hiện chỉ copy `Content-Type` + `Cache-Control`. Thêm
   `Content-Disposition` và `X-Content-Type-Options` vào danh sách copy — phase 05
   sẽ đặt hai header đó và chúng phải sống sót qua proxy.
5. `lib/alpha.ts`: khi `init.body` là `FormData`, **không** đặt `Content-Type` —
   để browser tự đặt kèm boundary. Giữ mọi luật khác (cookie, 401 retry).
6. Quyết định replay: buffer body để replay được, hoặc khai rằng nạp trùng token
   rotation sẽ fail và client thử lại. Viết lý do vào bình luận cạnh `:192`.
7. Test: một `POST` nhị phân về tới upstream **byte-for-byte** · một `GET` nhị
   phân về browser byte-for-byte · một `POST` JSON cho payload y như trước (chống
   hồi quy im lặng) · một resource ngoài allowlist vẫn 404.

## Success Criteria

- [ ] `POST` multipart đến FastAPI nguyên bytes (so hash)
- [ ] `GET` nhị phân về browser nguyên bytes (so hash)
- [ ] Đường JSON cho payload không đổi (test so sánh)
- [ ] `Content-Disposition` + `X-Content-Type-Options` sống sót qua `passthrough`
- [ ] Quyết định replay có ghi lý do trong code
- [ ] `pnpm type-check` `lint` `test` `build` pass

## Risk Assessment

**Rủi ro: buffer body nhị phân làm proxy ăn RAM theo số request đồng thời.**
uvicorn chạy **một** worker (`loop.py:164`) và pool 15 connection
(`router.py:22-24`); Next route cũng không phải chỗ giữ nhiều MB.
*Tín hiệu:* RSS của process web tăng theo số nạp song song.
*Phản ứng đã định:* nếu chọn buffer thì trần bytes của phase 05 phải tính cả chỗ
này, không chỉ tính theo token. Nếu không chọn buffer thì nạp trùng token rotation
fail — và đó là một lỗi người dùng thấy được, thử lại được, rẻ hơn hẳn.

**Rủi ro: đổi vị ngữ `passthrough` làm lọt một response JSON qua đường nhị phân.**
*Tín hiệu:* một endpoint JSON bỗng trả về không parse được ở client.
*Phản ứng:* vị ngữ viết theo hướng **cho phép JSON đi đường cũ** (`if json →
text()`), không theo hướng liệt kê cái gì là nhị phân. Danh sách trắng cho đường
cũ, không danh sách đen cho đường mới.
