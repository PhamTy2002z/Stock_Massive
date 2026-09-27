# Connectors — báo cáo triển khai P1 → P4

Ngày 27/09/2026 · Branch `feat/user-connectors` (worktree
`/Users/typham/Dev/worktrees/Stock_Massive-user-connectors`), chưa merge vào `main`.

## Kết luận

Làm đủ P1–P4 theo phương án B và bốn quyết định của owner. Cả bốn cổng phase đều
đạt bằng test tự động:

- Backend: **1588 passed** (baseline 1507), trong đó 70 test connector mới.
- Web: **556 passed** (baseline 524). Lint, type-check và build sạch.

Hỏi thử trên dev **đạt**:

- **5 Turn có dùng connector đã hoàn tất**, cộng thêm 1 Turn kiểm tra cách ly của
  tài khoản B, và chấm đạt ở cả bốn tiêu chí.
- Lần chạy đầu bị route hết hạn mức giữa chừng; các câu còn thiếu đã được hỏi bù
  sau khi route có lại quota.
- Còn một phát hiện về hành vi model ở chế độ "nạp khi cần" (xem phần hỏi thử).

## Thay đổi theo phase

| Phase | Commit | Nội dung |
|---|---|---|
| Nền | `787dd4a` | Mang phần việc đã xong nhưng chưa commit của `feat/host-owned-numbers` (plan `260927-1018`) làm nền. Riêng bản sửa dở `settings-primitives.tsx` của phiên Settings được loại ra. |
| Plan | `3721417` | `proposal.md`, `plan.md`, 4 file phase. Ghi quyết định 1 vào `phase-10-conditional-capabilities.md` và `CLAUDE.md`. |
| P1 | `4fca704` | Package `apps/api/src/connectors/` gồm các module sau. |
| | | `models` và migration: 4 bảng. |
| | | `crypto`: MultiFernet. |
| | | `netguard`: `is_global`, pin IP ngay ở lần phân giải đầu, không follow redirect, override test không có biến env nào và bị từ chối ở production. |
| | | `mcp_client`: MCP SDK 2.0 qua Streamable HTTP, phân loại lỗi 401/403, 5xx và protocol. |
| | | `snapshot`: làm sạch tên, hậu tố hash, cap 50, kiểm schema, quét `threat_patterns`, fingerprint. |
| | | `policy`: annotation chỉ siết; tool ghi chỉ được `ask`/`deny`. |
| | | `overlay`: `ResolvedTool` riêng cho từng Turn, không đi qua registry global. |
| | | `service`, `router` (`/api/v1/connectors`). Grounding có `SourceKind.CONNECTOR`, và chỉ nguồn có `trusted_data` mới là bằng chứng. |
| P2–P4 backend | `62dba8c` | `oauth.py`: discovery RFC 9728/8414, DCR RFC 7591, PKCE S256, `state` chỉ dùng một lần, refresh dưới `SELECT … FOR UPDATE`. |
| | | Duyệt trong Turn: executor `approve()` chạy trước round timeout và không tính vào deadline. Có SSE `approval.requested`/`resolved`, `POST /turns/{id}/approvals/{call_id}`, và trường `client_capabilities` trong body Turn. |
| | | Chế độ nạp khi cần dùng cặp meta tool cố định; executor bóc lớp để lấy tool bên trong. |
| | | Snapshot thay đổi thì chuyển `needs_reconsent`, trong lúc chờ chỉ chạy các tool y hệt bản cũ. Breaker 3 lỗi mở 60 giây, gấp đôi mỗi lần, tối đa 15 phút; 401/403 thì park ngay. |
| | `56ff6e9` | Forward `CONNECTORS_*` trong `docker-compose.yml` và `.env.example`. Gộp `anyOf` gồm các kiểu đơn giản (lỗi tìm ra khi chạy với DeepWiki thật). |
| | `1bdc7d1` | **Lỗi tìm ra khi hỏi thử:** ở chế độ nạp sẵn, tool mức Cần duyệt bị loại khỏi schema gửi cho model (`may_allow`). Đã sửa và thêm test chặn tái phát. |
| P2–P3 web | `706b4b7` | Pane Cài đặt › Kết nối: tabs, Thêm, bảng 4 cột, trang chi tiết với quyền ba trạng thái (tool ghi khoá Cho phép). Submenu "+" › Kết nối, thẻ duyệt trong chat, reducer SSE, proxy thêm `connectors` và `PUT`. Chi tiết trong [reports/web-ui.md](reports/web-ui.md). |

## Acceptance a–g

| | Tiêu chí | Test chứng minh |
|---|---|---|
| a | User A gắn thì B không thấy | `test_connectors_core.py::test_other_users_never_see_a_connector`; `test_connectors_router.py::test_add_list_edit_and_remove_without_ever_returning_the_key` |
| b | Chặn thì không có trong schema; Cần duyệt thì chờ; từ chối hoặc hết giờ thì `APPROVAL_REQUIRED` | `test_connectors_core.py::test_policy_shapes_what_is_offered`; `test_connectors_approvals.py::test_allow_once_runs_the_call_and_asks_again_next_time`, `::test_always_runs_the_call_and_keeps_allow_for_that_tool`, `::test_deny_and_timeout_both_reach_the_model_as_approval_required`, `::test_waiting_for_the_reader_is_not_charged_to_the_turn_deadline` |
| c | Từ chối localhost / 10.x / 169.254.169.254, kể cả qua redirect và DNS | `test_connectors_netguard.py::test_a_private_address_is_refused`, `::test_a_public_name_that_resolves_private_is_refused`, `::test_a_redirect_is_never_followed`, `::test_the_first_answer_is_pinned_so_a_rebinding_dns_is_never_asked_again` |
| d | Đọc connector xong thì `remember_fact` bị chặn | `test_connectors_core.py::test_a_connector_read_blocks_remember_fact` |
| e | Đổi mô tả hoặc thêm tool thì cần xác nhận lại; tool mới không tự được cho phép | `test_connectors_change.py::test_a_changed_description_waits_for_the_user_and_only_unchanged_tools_run`, `::test_a_new_tool_is_proposed_not_offered_and_starts_at_ask`, `::test_a_stale_snapshot_is_checked_in_the_background_at_turn_start` |
| f | Server chết giữa Turn thì Turn vẫn settle, trạng thái hiện lỗi | `test_connectors_change.py::test_a_server_that_dies_mid_turn_leaves_a_settled_turn_and_an_error_status`, `::test_repeated_failures_open_the_breaker_and_success_closes_it`, `::test_a_refused_credential_parks_the_connector_without_a_retry` |
| g | Không có token plaintext trong DB | `test_connectors_core.py::test_no_plaintext_secret_in_the_database` (header, query `?api_key=`, xoá thì mất credential) |

## Edge case bổ sung

| Edge case | Test |
|---|---|
| Tên trùng sau khi làm sạch hoặc cắt còn 64 ký tự | `test_connectors_units.py::test_names_that_collide_after_cleaning_get_a_hash_suffix_not_an_overwrite`, `::test_names_that_collide_after_cutting_to_64_characters_stay_distinct` |
| Quá N=50 tool | `test_connectors_units.py::test_only_the_first_fifty_tools_are_kept_and_the_rest_are_counted`; UI: `connectors-pane.test.tsx` (truncated) |
| Schema không hợp lệ; kết quả không phải văn bản hoặc quá cỡ | `test_connectors_units.py::test_a_schema_outside_the_executor_subset_drops_the_tool_with_a_reason`; `test_connectors_core.py::test_an_oversized_or_non_text_result_is_cut_and_says_why` |
| Hai Turn refresh cùng một OAuth token | `test_connectors_oauth.py::test_connect_with_pkce_then_refresh_once_then_disconnect` (hai service, hai engine, đúng 1 lần refresh) |
| Tắt hoặc xoá connector khi đang chờ duyệt | `test_connectors_approvals.py::test_switching_a_connector_off_settles_its_waiting_call[disable\|delete]` |
| Nhiều lời gọi cần duyệt song song | `test_connectors_approvals.py::test_two_calls_in_one_round_are_approved_independently` |
| Xoay vòng key (MultiFernet) | `test_connectors_units.py::test_a_rotated_key_still_opens_tokens_written_under_the_old_one` |
| DNS rebinding | `test_connectors_netguard.py::test_the_first_answer_is_pinned_so_a_rebinding_dns_is_never_asked_again`, `::test_a_dns_answer_that_turns_private_at_connect_time_is_refused` |
| Override chỉ dùng được trong test, bị từ chối ở production | `test_connectors_netguard.py::test_the_private_host_override_is_refused_in_production`, `::test_no_environment_variable_opens_private_hosts` |
| Client không hiểu sự kiện duyệt thì deny ngay | `test_connectors_approvals.py::test_an_app_that_cannot_draw_the_card_is_refused_at_once` |
| Nạp khi cần không đổi prefix | `test_connectors_tool_access.py::test_on_demand_loads_a_tool_as_a_result_and_the_tool_list_never_moves`, `::test_on_demand_prefix_is_the_same_for_every_account_whatever_it_attached` |
| Server không giả được envelope `trusted_data` | `test_connectors_grounding.py::test_a_web_page_cannot_forge_the_connector_envelope`, `::test_an_untrusted_connector_figure_stays_unverified_even_when_it_matches` |

UI Cài đặt còn được kiểm tra thêm trên trình duyệt thật (Playwright, web :3010 → API :8002, tài khoản test B). Thêm URL tuỳ chỉnh DeepWiki gửi POST; đổi một tool sang Chặn gửi PUT; "Cho phép" bị khoá với tool ghi; Ngắt kết nối có bước xác nhận trong app rồi gửi DELETE.

## Hỏi thử trên dev

**Môi trường.** API riêng của branch chạy ở cổng 8002. Cổng 8001 đang có stack "strict" khác nên không dùng.
- Image dẫn xuất từ `stockmassive-api` và cài thêm `mcp` và `cryptography`. Build image đầy đủ không được vì `vnstock==4.0.5` không có trên PyPI, lỗi này có sẵn từ trước.
- DB là bản clone `stockmassive_connectors`.
- Hai tài khoản test là A (7195) và B (7196).
- Connector thật: Context7 và DeepWiki, cả hai là URL tuỳ chỉnh không cần xác thực.

| Turn ID | Câu hỏi (A) | Chế độ | Kết quả | Chấm |
|---|---|---|---|---|
| `dc969f59-f320-46c4-a1ce-0400975dc6e3` | Context7: hàm vnstock lấy báo cáo tài chính | nạp khi cần | complete | Quyền đúng: `resolve-library-id` hiện thẻ duyệt, cho phép một lần thì trả 204, B thử duyệt thì 404; `query-docs` là Cho phép. Ledger ghi `connector:context7/resolve-library-id` và `connector:context7/query-docs`. Câu trả lời không có số nên không cần nhãn. |
| `538161dd-f14b-4a0b-a8cc-49a43657cf31` | cùng câu (lần 2) | nạp khi cần | complete | 3 thẻ duyệt, B thử cả 3 đều 404. Context7 vượt timeout 20 giây ba lần; Turn chuyển sang web và vẫn settle, đúng tinh thần acceptance f. |
| `c991a69a-f6cc-48f1-aeac-0fa8f1131711` | DeepWiki: cấu trúc wiki thinh-vu/vnstock | nạp sẵn | complete | Tool ghi (không có `readOnlyHint`) bị khoá ở Cần duyệt và hiện thẻ. Ledger ghi `connector:deepwiki/read_wiki_structure` kèm `observedAt`. Có nhãn "chưa kiểm chứng". |
| `a717a638-8dd0-40ae-9984-5b3abc0a7010` | DeepWiki: rolling window của pandas | nạp sẵn | complete | Nhánh từ chối: 2 thẻ bị từ chối, model nhận `approval_required`, server không bị gọi. 5 số model tự viết đều mang nhãn "chưa kiểm chứng" (`not_in_sources`). |
| `a9295c17-f69e-481c-bdaa-3f8060c2a2e7` | Giá VNM + Context7 | nạp sẵn | incomplete (`route_error` 402) | `get_market_data` ok; "Luôn cho phép" được lưu thành `resolve-library-id: allow`; tool chạy ok. Route hết hạn mức trước khi viết xong câu trả lời. |
| `75d25a49…`, `a998e817…`, `ee78660f…`, `9c1d9569…`, `60cdb96b…` | các câu còn lại, cả câu của B | — | incomplete | Route: 402 hết hạn mức; hoặc 400 từ route Claude (`tools.0: minimum/maximum not supported`, thuộc tool base). Đã hỏi bù ở các dòng dưới. |
| `edb9791a-c08c-4854-8879-3968585c7e9c` | Hỏi bù câu 4: giá VNM + Context7 | nạp sẵn | complete | `get_market_data`, `resolve-library-id`, `query-docs` đều ok. Không hiện thẻ, vì "Luôn cho phép" đã lưu từ `a9295c17`. Giá được kiểm là grounded `[1 · phiên 25/09/2026]` từ nguồn kbs; ledger có `kbs/VNM` và hai nguồn connector. |
| `106adc29-ee5d-44a0-b02d-d87e2394ac1a` | Tài khoản B: dùng Context7 | — | complete | Cách ly: B không có tool connector nào nên chỉ dùng web (4 lời gọi `web_search`/`fetch_url`, 0 connector). |
| `cf43838f…`, `805c171e…`, `c126f2b3-09fe-400a-8b3e-7ebc5f9c95c7` | Hỏi bù câu 5: "Theo wiki DeepWiki…" | nạp khi cần | complete | **Phát hiện:** model (`kiro-glm-5`) không gọi `search_connector_tools` mà dùng web. Ở `cf43838f`, model còn khẳng định đã "tìm trên Context7" dù không có lời gọi nào. Đã thêm tên các connector đang bật vào runtime tail (ngoài prefix được cache), nhưng model vẫn chọn web. Khi câu hỏi viết "Dùng kết nối …" (`dc969f59`, `538161dd`) và ở chế độ nạp sẵn (`c991a69a`, `a717a638`, `edb9791a`), connector được dùng đúng. |

Chấm tổng theo log Turn và DB:
- **Quyền được áp đúng** ở mọi Turn.
- **Nhãn "chưa kiểm chứng"** xuất hiện đúng chỗ. Có một ghi chú: số nhỏ không kèm đơn vị như "5.2" (số mục) cố ý không được khớp với bất kỳ nguồn nào, nên ledger ghi lý do `not_in_sources` thay vì `untrusted_connector`. Nhãn vẫn đúng.
- **Ledger ghi đủ** connector, tool và `observedAt`.
- **Không lộ tool giữa hai tài khoản:** B có 0 connector và 0 lời gọi tool connector; B cố duyệt thẻ của A thì 404 cả 4 lần.

## Migration và dependency

- **Migration** `c4e9a2f71b35_add_user_connectors`: chỉ thêm 4 bảng.
  - Backup trước khi chạy: `~/Dev/backups/stockmassive-260927-1337-before-connectors.dump` (pg_dump của DB dev chính).
  - Chỉ chạy trên bản clone `stockmassive_connectors`, đã thử upgrade → downgrade → upgrade; số dòng users và agent_turn không đổi.
  - **DB dev chính không bị đụng.** API của cây chính chạy `alembic upgrade head` khi boot và sẽ từ chối một head lạ.
  - Migration của phiên Settings (`ce858b22360a`, `users.preferences`) cũng nối vào `e6a21b7c4d90`. Hai phiên đã thống nhất: bên nào merge sau thì đổi `down_revision` sang head của bên kia.
- **Dependency mới** trong `requirements.txt`: `mcp==2.0.0` (kéo theo `httpx2`) và `cryptography>=44,<51`.
- **Setting mới:** `CONNECTORS_ENABLED`, `CONNECTORS_ENCRYPTION_KEYS`, `CONNECTORS_CUSTOM_URL`, `CONNECTORS_CUSTOM_URL_USERS`, `CONNECTORS_CALL_TIMEOUT_SECONDS`, `CONNECTORS_MAX_RESULT_CHARS`, `CONNECTORS_OAUTH_REDIRECT_URL`, `CONNECTORS_WEB_RETURN_URL`. Mặc định đều tắt.

## Rủi ro còn lại

1. **Hub duyệt chỉ chạy trong một tiến trình.** Khi API chạy nhiều worker sau cùng một Turn thì phải chuyển sang Redis pub/sub (có `ponytail:` note trong `approvals.py`).
2. **Mỗi lần gọi mở một phiên MCP mới** (initialize + request). Latency sẽ gấp đôi so với khi pool phiên.
3. **Tool ghi của connector chỉ chạy được trong Turn chưa đọc nội dung ngoài.** Lý do là luật escalation có sẵn; mình giữ nguyên để không làm yếu lớp chống prompt injection. Ví dụ "đọc Notion rồi ghi lại" sẽ bị chặn dù user đã duyệt.
4. **Sau một lần bị từ chối, model có thể thử một tool khác** cùng connector (Turn `a717a638`). Mỗi lần thử vẫn phải qua thẻ duyệt.
5. **Tập schema được hỗ trợ còn hẹp.** Không hỗ trợ `$ref`, `oneOf`, hoặc `anyOf` phức tạp; tool dùng chúng bị bỏ, kèm lý do hiện trên UI.
6. **OAuth mới được thử với server giả theo spec MCP.** Provider thật có thể khác ở bước discovery.
7. **Pane Kết nối đang đăng ký theo shape Settings cũ.** Khi modal Settings mới của phiên kia merge, cần đăng ký lại ở hai chỗ có comment `connectors pane: re-register…`.
8. **Flyout của composer** có thể tràn trên màn hình rất hẹp.
9. **Ở chế độ "nạp khi cần", model có thể bỏ qua connector**, tuỳ cách người dùng
   đặt câu. Model cũng có thể khẳng định sai là đã dùng connector (xem các Turn hỏi
   bù câu 5). Chế độ "nạp sẵn" không gặp vấn đề này. Có thể cân nhắc mặc định "nạp
   sẵn" khi tổng số tool connector còn nhỏ.

## Chưa làm / cần quyết

- **Hỏi bù ít nhất 1 câu** khi route LLM dev có lại hạn mức, để đủ 5 Turn hoàn tất. Script đã có sẵn; thêm một câu của B cho kiểm tra cách ly ở mức Turn.
- **Merge vào `main`:** chờ bạn duyệt, theo mục "Hỏi trước khi".
- **Catalog đang rỗng.** Thêm connector thật vào danh mục hoặc đặt `trusted_data=true` là quyết định của bạn.
