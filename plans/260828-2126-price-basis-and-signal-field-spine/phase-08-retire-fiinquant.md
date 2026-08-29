---
phase: 8
title: "Xoá FiinQuant và nghiệm thu"
status: done
priority: P1
effort: "6h"
dependencies: [4, 5, 6]
---

# Phase 08: Xoá FiinQuant và nghiệm thu

> **Sửa 2026-08-28 sau red-team.** Bốn sửa: (a) mọi lệnh DB phải **ghim host** —
> lỗi này đã xảy ra rồi trên chính máy này; (b) gỡ Phase 07 khỏi điều kiện chặn
> (R5 sai); (c) danh sách gỡ tên đi từ 5 file lên **11 file / 47 tham chiếu**,
> gồm `tests/conftest.py`; (d) đường phục hồi phải **thu hẹp theo bảng**, không
> phải restore toàn DB.

## Overview

Phase một chiều. 71.773 dòng FiinQuant (36.528 `market` + 35.245 `valuation`)
không lấy lại được — licence đã cắt. Chỉ chạy khi các phase trước xanh và mọi
phép đo đối chiếu đã ghi xong.

## Requirements

- Functional: 0 dòng `source = 'fiinquant'` trong `provider_snapshots` **của DB
  container**.
- Functional: mọi tên `fiinquant` gỡ khỏi đường phục vụ, `src/` lẫn `tests/`.
- Non-functional: backup **thu hẹp theo bảng**, đã restore thử, đếm khớp **số
  dòng cụ thể** — không phải "đếm lại".

## Architecture

### R6 — hai Postgres cùng tên, và cái rỗng thắng mặc định

Trên máy này có **hai** instance trả lời tên `stockmassive`:

| Nơi | `provider_snapshots` |
|---|---|
| brew Postgres, `127.0.0.1:5432` (mặc định của `psql`/`pg_dump` không tham số) | **0 dòng** |
| container `stockmassive-db-1` | 106.007 dòng, trong đó 71.773 fiinquant |

**Lỗi này đã xảy ra.** `backups/` đang giữ hai file cùng ngày 2026-08-28:
`pre-rename-signal-desk-260828.sql.gz` **17.398.824 B** và
`pre-rename-signal-desk-hostdb-260828.sql.gz` **46.349 B**. Cái thứ hai là một
dump của DB rỗng — hợp lệ về cú pháp, vô dụng về nội dung.

Một backup rỗng trước một phép xoá một chiều là mất dữ liệu vĩnh viễn, và không
có tín hiệu cảnh báo nào: dump chạy xong, restore chạy xong, đếm ra 0 và `0 = 0`
nên mọi cổng đều xanh.

**Luật của phase này:**

- Mọi lệnh chạm DB ghim `PGHOST`/`PGPORT` (hoặc `docker exec` tường minh). Không
  lệnh nào dựa vào mặc định.
- Mọi phép đếm so với **số cụ thể** viết sẵn trong plan, không so với chính nó.
- Phép xoá chạy trong transaction và **tự abort** nếu `ROW_COUNT ≠ 71773`.

### Đường phục hồi — thu hẹp, không phải toàn DB

Bản đầu: phát hiện lỗi ở bước smoke → "restore, tìm reader, làm lại". Nhưng smoke
lane chat **ghi** vào `agent_thread`, `agent_turn`, `agent_message`,
`agent_tool_call`, `agent_artifact`, `llm_call_usage`. Restore toàn DB xoá sạch
chính những dòng đó, cộng mọi `bar_daily` đã ingest từ lúc dump — trong khi tiền
LLM thì đã tiêu thật.

**Lấy hai backup:** một toàn DB (theo lệ), và một **`pg_dump -t provider_snapshots`**.
Đường phục hồi tài liệu hoá là nạp lại bảng đó vào DB đang chạy, tiến tới chứ
không lùi.

### Điều kiện vào — cổng cứng

| Cổng | Nguồn | Ghi chú |
|---|---|---|
| Phase 04 xong: 30 field khai projection, 7 field trả ba mã cũ | phase-04 | |
| Phase 05 xong **và** mean/median/**p95**/max của `close×volume` đã ghi | phase-05 bước 5 | chỉ đo được khi FiinQuant còn |
| Phase 06 xong **và** tỉ lệ phiên quyết được theo sàn đã ghi | phase-06 bước 7 | **không** so với FiinQuant — nó null 99,93% band |
| Backup **theo bảng** restore thử, đếm = 106.007 tổng / 71.773 fiinquant | phase này bước 1-3 | |

**Phase 07 KHÔNG còn là cổng.** R5 sai — 0 dòng `market_index` ở mọi source.

### Xoá gì

| Đối tượng | Dòng | Ai đọc sau 03-06 |
|---|---|---|
| `provider_snapshots` fiinquant/`market` | 36.528 | không ai — signals đã sang `bar_daily` |
| `provider_snapshots` fiinquant/`valuation` | 35.245 | **không ai, kể cả hôm nay** — zero reader, chỉ có type-map ở `providers/store.py:35` |
| `provider_snapshots` vnstock/`market` (2016-2021) | 31.160 | không ai sau 03 — nhưng **không vi phạm gì**, mặc định **giữ** |

### Gỡ tên — 11 file, 47 tham chiếu

`grep -rli fiinquant apps/api/{src,tests}` → **11 file**. Bản đầu kể 5, và **bỏ
hết tests**. Chỗ nguy hiểm nhất:

- `tests/conftest.py:22,28` — `if source is ProviderSource.FIINQUANT:`. Gỡ enum mà
  quên đây thì pytest vỡ ở **collection**, sau khi phép xoá đã commit. Không phải
  một test đỏ đọc được, mà là cả suite không chạy.
- `tests/test_provider_contracts.py` — 26 tham chiếu, gồm `:308,319,320,321`
  khẳng định `main_source(Capability.MARKET_INDEX) is ProviderSource.FIINQUANT`.
- `tests/test_price_band.py` (7), `tests/test_trading_day.py:1`.
- `src/studies/entry_condition_review.py:21` — **địa phận plan Study**.
- `src/stocks/providers/normalize.py:52` — surface CLAUDE.md để **freeze**; nếu
  buộc phải đụng thì đó là tín hiệu dừng, xin amendment, không sửa thầm.
- `src/stocks/providers/__init__.py:3`, `src/stocks/trading_day.py:30` (docstring).

**Bẫy ownership map:** `SourceOwnership.validate_distinct_sources`
(`contracts.py:144-149`) raise khi `cover is main`. VALUATION hiện
`main=FIINQUANT, cover=VNSTOCK` — đổi main sang vnstock mà giữ cover là raise lúc
import. Phải **bỏ cover**, không chỉ đổi main. Ba mục cùng trỏ fiinquant: MARKET,
VALUATION, MARKET_INDEX.

`realtime/{contracts:32, policy:52,56}` — enum song song, không reader sống. Gỡ
nếu sạch; nếu kéo theo gì thì để lại và ghi lý do (`realtime/*` vẫn freeze).

## Related Code Files

- Modify: `apps/api/src/stocks/providers/{contracts,store}.py`,
  `apps/api/src/stocks/schemas/snapshot.py`
- Modify: `apps/api/tests/{conftest,test_provider_contracts,test_price_band,test_trading_day}.py`
- Modify: `apps/api/src/stocks/realtime/{contracts,policy}.py` (nếu gỡ được sạch)
- Modify: `CLAUDE.md` — mục "Không còn tồn tại" ghi dòng dữ liệu đã xoá
- Data: `provider_snapshots` — DELETE có điều kiện
- Không tạo alembic revision cho schema; **cân nhắc** một data revision (xem rủi ro)

## Implementation Steps

1. `pg_dump` toàn DB **có ghim host container** vào `backups/`; không commit
   (kiểm `.gitignore:86` trước — đã có).
2. `pg_dump -t provider_snapshots` riêng, cùng cách ghim host.
3. Restore bản (2) vào DB tạm; khẳng định **106.007** dòng tổng và **71.773** dòng
   fiinquant. Số khác → dừng, không phải "đếm lại".
4. Xác nhận đủ bốn cổng ở bảng "Điều kiện vào".
5. Ghi số trước khi xoá theo `(source, capability)` vào phase report.
6. `BEGIN; DELETE FROM provider_snapshots WHERE source='fiinquant'; ` — kiểm
   `ROW_COUNT = 71773`, **abort nếu khác**, rồi mới `COMMIT`.
7. `make test` — chạy trên host, ghim `DATABASE_URL` vào DB container.
8. Gỡ tên theo danh sách 11 file; chạy lại `make test` + `tests/studies/`.
9. Smoke lane chat thật: hỏi vài câu chạm `get_field` trên mã declared; khẳng
   định 22 field ra số và 8 field trả đúng mã refusal.
10. Cập nhật `CLAUDE.md` và `docs/roadmap.md`.

## Success Criteria

- [ ] `SELECT count(*) ... WHERE source='fiinquant'` = 0 **trên DB container**,
      lệnh ghim host
- [ ] `grep -ril fiinquant apps/api/src apps/api/tests` không còn ở đường phục vụ
- [ ] 22 field ra số, 8 field trả đúng mã refusal, trên smoke lane chat thật
- [ ] Backup **theo bảng** đã restore thử, đếm khớp 106.007 / 71.773, đường dẫn
      ghi trong phase report
- [ ] `make test` + `tests/studies/` + bốn cổng web xanh
- [ ] `CLAUDE.md` ghi dòng dữ liệu đã xoá

## Risk Assessment

- **R6 backup rỗng.** *Tín hiệu:* dump nhỏ bất thường (~46 KB thay vì ~17 MB),
  hoặc restore đếm ra 0. *Phản ứng:* bước 3 so với **số cụ thể** chính là để bắt
  cái này; đừng bao giờ so một phép đếm với chính nó.
- **R3 xoá một chiều.** Không có cảnh báo sớm. *Phản ứng:* bước 2-3 là biện pháp
  duy nhất; không bỏ qua vì "dump chạy xong rồi".
- **Vỡ collection sau khi đã xoá.** `tests/conftest.py:28` dùng enum sắp gỡ.
  *Tín hiệu:* pytest không collect được, không phải test đỏ. *Phản ứng:* bước 8
  gỡ tên **sau** khi `make test` ở bước 7 đã xanh, để phân biệt được lỗi dữ liệu
  với lỗi gỡ tên.
- **Một reader bị bỏ sót.** *Tín hiệu:* test xanh nhưng smoke ở bước 9 trả refusal
  ở field lẽ ra có số. *Phản ứng:* nạp lại bảng từ backup (2) vào DB đang chạy —
  **không** restore toàn DB, nó sẽ xoá chính transcript vừa chứng minh lỗi.
- **Gỡ enum kéo vào `realtime/*` hoặc `providers/normalize.py` đang freeze.**
  *Tín hiệu:* import lỗi ở module freeze. *Phản ứng:* để lại, ghi lý do. Xoá dữ
  liệu là mục tiêu; gỡ tên chỉ là dọn.
- **Không có bản ghi replay được của phép xoá.** Bản đầu ghi "không tạo alembic
  revision". Hệ quả: không môi trường nào khác tái hiện được, không ai review
  được nó như review một migration. *Cân nhắc* đóng gói thành data revision —
  đánh đổi với luật "alembic đã commit thì không sửa", nên là quyết định, không
  phải mặc định.
