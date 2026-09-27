# P4 — Change detection, circuit breaker

## Requirements

Rug-pull: a snapshot whose fingerprint changed puts the connector in
`needs_reconsent`; only previously accepted, unchanged tools keep running; new or
changed tools start at the strictest allowed action. Breaker per connector:
repeated failures open it for a cool-off; 401/403 park it (`needs_auth`) without
retry. Server death mid-Turn settles the Turn with what arrived.

## Steps

1. Refresh (manual, and lazily when the snapshot is older than 1 h at Turn start
   in the background) computes a new snapshot; on change store it as
   `pending_snapshot`, set `needs_reconsent`, keep serving the accepted tools that
   are byte-identical; "Xác nhận" in the UI accepts it.
2. `service.record_failure/success`: 3 consecutive transient failures → open for
   60 s, doubling to 15 min; auth failure → `needs_auth`, overlay leaves it out.
3. UI: status column shows Lỗi / Cần đăng nhập lại / Cần xác nhận; detail shows the
   diff (added / changed / removed tools).

## Validation

- e: `test_connectors_change.py` (description change, added tool → not allowed).
- f: `test_connectors_resilience.py` (server killed mid-Turn → Turn settles, status
  `error`; breaker opens; 401 parks immediately, no second request).
