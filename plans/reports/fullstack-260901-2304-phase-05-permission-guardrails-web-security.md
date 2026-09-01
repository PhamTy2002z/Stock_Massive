# Phase 5 — Permission, guardrails, web security

Ngày 2026-09-01. Nhánh
`feat/phase-05-permission-guardrails-web-security`, bắt đầu từ Phase 4
`cae8732`. Thực hiện không dùng subagent theo yêu cầu của product owner.

## Outcome

Capability chỉ dispatch sau khi arguments khớp chính JSON Schema frozen và
policy typed cho capability/resource trả `allow`. No-match/unknown deny;
last matching rule thắng; `ask` chỉ hợp lệ cho write effect thật và settle bằng
`approval_required`, không giả lập approval.

Permission không thay chỗ cho availability/kill switch, tenant authorization,
sandbox hay content guardrail. Một successful untrusted external read chỉ ghi
một bit taint content-light; write hoặc unknown-effect về sau trong cùng Turn bị
chặn trước handler. Write rõ ràng trước external read vẫn chạy như cũ.

## Thay đổi chính

- Thêm `agent/permissions.py` cho rule, decision và Turn permission state;
  registry freeze rule/resource cùng schema/handler và chỉ offer capability có
  thể allow.
- Thêm validator cho JSON Schema subset đang ship; keyword không hỗ trợ fail ở
  registration, argument sai fail trước handler.
- Thêm outbound credential guard trước search provider, DNS, download và từng
  redirect; trace projection redact đệ quy, persistence lặp lại redaction như
  cửa phòng thủ cuối.
- Mở rộng threat normalization có bound cho HTML/percent/base64, zero-width và
  bidi; advisory scanner exception/timeout vẫn trả `unknown` và giữ answer.
- Web lane charge Redis allowance toàn fleet và theo normalized domain chỉ trên
  real cache miss; cache hit/single-flight hit không spend allowance. Per-Turn
  logical ceiling và Phase 10 scale owner giữ nguyên.

## Acceptance evidence

| Contract | Bằng chứng |
|---|---|
| Rule typed, last-match-wins, no-match/unknown deny | policy unit tests + dispatch resource recheck |
| Global deny/approval-only không được offer | resolved-surface adversarial tests |
| Frozen schema fail-closed trước handler | invalid missing/extra/type/range corpus |
| Untrusted read không leo thang thành memory write | same-Turn read→write test; explicit write-first control |
| Không raw secret qua egress/trace | pre-I/O URL/query tests; executor và direct-persistence trace tests |
| Fleet/domain + per-Turn bounds | Redis domain isolation/cache-hit test + existing executor/loop ceilings |
| Encoded/bidi signal, scanner fail-open | percent/HTML/base64/zero-width/bidi and scanner failure tests |
| Permission/approval/auth tách biệt | typed refusal tests, `AuthorizationDenied` dispatch test |
| Không làm vỡ public contract | full backend/web gates; không migration/endpoint/event mới |

Adversarial threshold đóng ở **0 permission escalation**, **0 raw secret trong
trace**, **0/20 benign false-positive blocks**. Suite adversarial có 25 test và
đạt toàn bộ.

## Verification

```text
pytest tests/test_agent_security_adversarial.py -q
25 passed

focused security suite
257 passed, 8 warnings

pytest -q
1401 passed, 3 deselected, 169 warnings

pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test
39 files, 458 passed

pnpm --dir apps/web build
Compiled successfully

python3 -m compileall -q apps/api/src apps/api/golden apps/api/tests
git diff --check
clean
```

Warnings không mới và không che failure: fixture auth dùng HMAC key ngắn;
WebSocket legacy deprecation; jsdom không implement canvas context; Next báo
ESLint plugin chưa được detect. Tất cả command trả exit code 0.

## Review và ranh giới

Self-review dùng roadmap Phase 5 + plan làm spec và `cae8732` làm fixed point.
Hai lỗi phát hiện trong review đã được sửa và test khóa: final wildcard deny
phải shadow earlier allow khi quyết định offer schema; content taint phải đến
từ untrusted read, không từ một write stub có metadata không thực tế. Không còn
finding blocker/high.

Không có một chiều cửa nào bị mở: catalog vẫn là `web_search`, `fetch_url`,
`session_search`, `remember_fact`, `recall_facts`; default permission không
đổi; không migration, thay đổi retention, endpoint, SSE event, approval UI hay
sandbox. Phase 6 là phase tuần tự kế tiếp.
