<h1 align="center">VisgniteAI ⚡</h1>

<p align="center">
  <strong>Phân tích sâu một nhúm cổ phiếu Việt Nam bạn thực sự quan tâm — không phải màn hình theo dõi cả thị trường.</strong>
</p>

<p align="center">
  <a href="CONTEXT.md">Từ vựng</a> ·
  <a href="docs/adr/">ADR</a> ·
  <a href="docs/specs/">Spec</a> ·
  <a href="CLAUDE.md">Quy ước repo</a> ·
  <a href="docs/agents/">Agent docs</a> ·
  <a href="LICENSE">MIT</a>
</p>

---

## Đây thực ra là gì?

Bạn chọn vài mã (tối đa 10 mã / tài khoản). Hệ thống dựng số liệu, chỉ số và biểu đồ cho **đúng những mã đó** — báo cáo tài chính, sức khoẻ tài chính, dòng tiền, khối ngoại, đột biến khối lượng, so với ngành.

Ba điều định hình toàn bộ kiến trúc:

- **Universe có trần 100 mã.** Hệ thống chỉ cam kết thu thập cho tập mã trong Universe. Trần là van an toàn cho collector, không phải hạn mức bán cho người dùng — nên nó không xuất hiện trong giao diện.
- **Request của người dùng không bao giờ chạm nhà cung cấp.** Một `Collector` chạy sau phiên là nơi duy nhất gọi ra ngoài; endpoint đọc từ `Snapshot` đã chuẩn hoá. Đúng một ngoại lệ được nêu tên: tin tức theo mã, xem [ADR 0001](docs/adr/0001-universe-va-phuc-vu-tu-snapshot.md).
- **Provider cắt theo `Capability`, không cắt theo nhà cung cấp.** FiinQuant là Main Source cho `market` + `valuation`; vnstock giữ `fundamental` + `reference`. Lý do đo đạc cụ thể nằm ở [ADR 0002](docs/adr/0002-main-cover-cat-ngang-capability.md).

> Sản phẩm **có** đưa nhận định vùng giá cụ thể, kèm miễn trừ trách nhiệm. Cách nó làm điều đó mà không bịa số: mọi con số do code tính, mô hình chỉ diễn giải — chi tiết ở [ADR 0010](docs/adr/0010-statistical-bar-for-computed-signal-fields.md).

Thuật ngữ in đậm ở trên (`Universe`, `Snapshot`, `Capability`, `Main Source`, `Cover Source`, `Adapter`, `Collector`) có định nghĩa chuẩn trong [`CONTEXT.md`](CONTEXT.md). Dùng đúng từ đó khi đặt tên biến, hàm, file.

---

## Bạn làm được gì với nó

- **Mở một mã và thấy toàn bộ hồ sơ.** Giá, khối lượng, cổ đông lớn, ban lãnh đạo, giao dịch nội bộ, 3 báo cáo tài chính (bản gọn và bản chi tiết), tỷ số, Piotroski F-Score, FCF.
- **Hỏi "mã này đang lệch gì so với ngành".** `sector-peers` xếp mã cạnh 5 mã cùng ngành trên cùng bộ chỉ số.
- **Bắt đột biến khối lượng, kèm mức độ nhìn thấy được.** `signals/volume-spikes` chấm đột biến cho hai phạm vi có biên — 50 mã lợi nhuận dẫn đầu và toàn Universe — và nói thẳng nó thấy được bao nhiêu phần của phạm vi đó (`coverage`), dữ liệu mới đến đâu (`freshness`), mã nào không đánh giá được và vì sao (`issues`).
- **Đọc một phiên qua `Snapshot`.** `/{symbol}/snapshot` và `/{symbol}/series/*` phục vụ thẳng từ store, mỗi điểm mang theo nguồn và tuổi dữ liệu.
- **Xem hiệu suất ngành theo kỳ.** ICB Level 2, các mốc 1D → 1Y, có endpoint refresh cho quản trị viên.
- **Chạy toàn bộ stack bằng một lệnh.** `pnpm dev` — backend + database trong Docker, Next.js chạy thẳng trên máy để có file watching native.

---

## Đang chạy · Đang nối dây · Đã chốt hướng, chưa có code

| ✅ Đang chạy | 🚧 Đang nối dây | 💭 Đã chốt hướng, chưa có code |
|---|---|---|
| 49 REST endpoint (stocks · auth · jobs · signals) | Dòng tiền / khối ngoại — adapter và cột snapshot đã có, chưa có collector hay endpoint nào dùng | **Alpha Desk**: agent gọi tool, stream câu trả lời, Thread bền, Widget — [spec 0002](docs/specs/0002-alpha-desk-product.md) |
| Auth tự host: JWT + bcrypt, refresh token xoay vòng, phát hiện tái sử dụng | Chỉ số kỹ thuật và lịch sử giá dài hạn — `DAILY_OHLCV_ENABLED` mặc định tắt vì quota | `prepare_bars()` + Signal Registry + bảng Corporate Action — [ADR 0006](docs/adr/0006-raw-price-basis-with-read-time-adjustment.md), [ADR 0010](docs/adr/0010-statistical-bar-for-computed-signal-fields.md) |
| `Snapshot` / `SnapshotStore` phục vụ thật: `/{symbol}/snapshot`, `/series/market`, `/series/valuation` | Tin tức theo mã — nguồn đã chọn, chưa persist | Watchlist + Analysis mỗi Trading Day — [spec 0003](docs/specs/0003-intelligent-quant-architecture.md) §A2 |
| **Trading Day** suy từ dữ liệu, **Warm-up**, **Backfill** có backoff công bằng | | Biểu đồ nến (chưa có renderer; OHLC thì đã phục vụ) |
| **Profit Ranking Census** + **Cohort Version**: 50 mã lợi nhuận dẫn đầu, seat trong Universe | | CI/CD (chưa có `.github/workflows` — cổng kiểm tra hiện là quy tắc người) |
| **Volume Spike** phục vụ theo Signal Scope, có coverage / freshness / issues | | |
| Cache Redis nhận biết giờ giao dịch + rate limit sliding window | | |
| Scheduler (APScheduler) + job status API + khôi phục job lỡ khi khởi động | | |
| 43 file test backend (`pytest`) · 6 file test frontend (Vitest, gồm cả component) | | |

<sub>Cột 🚧 nghĩa là mã đã tồn tại nhưng chưa nằm trên đường đi của request thật. Cột 💭 đã có spec và ADR chốt xong — xem <a href="docs/specs/0003-intelligent-quant-architecture.md">spec 0003</a> để biết thứ tự milestone.</sub>

---

## Bắt đầu

Chọn đường phù hợp với bạn.

### Tôi chỉ muốn chạy thử

Cần **Docker 20.10+** (kèm Compose v2), **Node 20+**, **pnpm 9+**.

```bash
git clone <repo-url> && cd Stock_Massive

cp .env.example .env                          # container: db + api
cp apps/web/.env.example apps/web/.env.local  # host: frontend

# Bắt buộc: sinh AUTH_SECRET
openssl rand -base64 32   # dán vào AUTH_SECRET trong .env

pnpm dev:web:install   # chỉ lần đầu
pnpm dev               # api + db trong Docker, web trên host
```

| Service | URL | Chạy ở |
|---|---|---|
| Frontend | http://localhost:3000 | Host (`next dev`) |
| API | http://localhost:8000 | Container `api` |
| API Docs (Swagger) | http://localhost:8000/docs | Container `api` |
| Database | localhost:5432 | Container `db` (PostgreSQL 16) |

Database khởi tạo rỗng — `api` tự chạy migration khi khởi động, còn dữ liệu thì do collector nạp dần. Nếu ai đó đưa bạn bản dump, đặt tên `data_export.sql` ở root rồi `pnpm db:restore`; **file này không kèm trong repo**.

### Tôi cần debug Python

Backend chạy thẳng trên máy, `db`/`redis` vẫn lấy từ Docker:

```bash
pnpm dev:api:detach          # chỉ db + redis + api container
cd apps/api && make dev      # uvicorn --reload trên host, port 8000
```

### Tôi muốn mọi thứ trong Docker

```bash
pnpm dev:full   # docker compose --profile full up
```

### Tôi chạy nhiều worktree song song

Đặt `API_PORT` / `WEB_PORT` khác nhau, thêm `COMPOSE_PROJECT_NAME`, và **sửa `CORS_ORIGINS` cho khớp origin mới của web** — quên bước cuối thì trình duyệt bị chặn CORS mà không có lỗi rõ ràng.

---

## Cấu hình

Mọi giá trị đều có default chạy được cho dev. Tham chiếu đầy đủ ở [`.env.example`](.env.example). Ba biến đáng chú ý:

- **`AUTH_SECRET`** — bắt buộc, không có default an toàn.
- **`VNSTOCK_API_KEY`** — không có thì quota là **20 req/phút**, có thì **60**. Đây là điểm nghẽn thật của hệ thống; vì nó mà `DAILY_OHLCV_ENABLED` và `SECTOR_HISTORICAL_ENABLED` mặc định **tắt**.
- **`FIINQUANT_USERNAME` / `FIINQUANT_PASSWORD`** — gói free chỉ cho **một session đồng thời**, nên chỉ collector được đăng nhập.

---

## Kiến trúc

```
┌──────────────────────────────────────────────────────────────┐
│  apps/web — Next.js 15 App Router (host, port 3000)          │
│  (auth) login/register  ·  (dashboard) Market Map, Stock 360 │
│  TanStack Query · ShadCN/Radix · Recharts · next-themes      │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST /api/v1
┌───────────────────────────▼──────────────────────────────────┐
│  apps/api — FastAPI (container, port 8000)                   │
│  src/auth/            JWT + bcrypt, refresh rotation         │
│  src/stocks/          vertical slice theo domain              │
│    market price company financial analytics trading signals  │
│    providers/         Adapter · contracts · SnapshotStore    │
│    trading_day · warmup · census · cohort · collector        │
│  src/core/            config cache redis scheduler ratelimit │
└──────┬─────────────────────────┬──────────────────┬──────────┘
       │                         │                  │
┌──────▼───────┐        ┌────────▼──────┐   ┌───────▼─────────┐
│ PostgreSQL16 │        │ Redis/Upstash │   │ Provider Source │
│ (Alembic)    │        │ TTL theo giờ  │   │ vnstock ·       │
│              │        │ giao dịch     │   │ FiinQuant       │
└──────────────┘        └───────────────┘   └─────────────────┘
                                              ▲
                                     chỉ Collector được gọi tới đây
```

Mỗi domain trong `src/stocks/` là một lát dọc đầy đủ: `router.py` (HTTP) → `service.py` (nghiệp vụ) → `schemas/` (Pydantic) → `models.py` (SQLAlchemy). Adapter là nơi **duy nhất** được biết hình dạng dữ liệu thô của nhà cung cấp.

`src/stocks/signals/` là chỗ khác một chút: nó trả lời *cái gì là đúng* — tính toán trên dữ liệu đã lưu, không gọi ra ngoài, và sẽ là nơi `prepare_bars()` cùng Signal Registry sống.

<details>
<summary><strong>Sơ đồ thư mục</strong></summary>

```
Stock_Massive/
├── apps/
│   ├── api/                      # FastAPI + SQLAlchemy + Alembic
│   │   ├── src/
│   │   │   ├── auth/             # router · service · security · models
│   │   │   ├── core/             # config cache redis scheduler ratelimit
│   │   │   │                     # trading_calendar · vnstock_client
│   │   │   ├── stocks/
│   │   │   │   ├── market/ price/ company/ financial/ analytics/ trading/
│   │   │   │   ├── signals/      # Volume Spike, tính từ phiên đã lưu
│   │   │   │   ├── providers/    # contracts.py · fiinquant.py · store.py
│   │   │   │   ├── shared/ schemas/ models.py
│   │   │   │   ├── snapshot_router.py series_view.py universe.py
│   │   │   │   ├── trading_day.py warmup.py backfill.py
│   │   │   │   ├── census.py cohort.py listing_roster.py
│   │   │   │   ├── collector.py collector_schedule.py
│   │   │   │   └── jobs.py jobs_router.py intraday_collector.py
│   │   │   └── main.py
│   │   ├── alembic/  tests/  prototypes/  Makefile
│   ├── web/                      # Next.js App Router
│   │   └── src/
│   │       ├── app/(auth)/ app/(dashboard)/ app/analytics/ app/api/
│   │       ├── components/ hooks/ services/ lib/ config/ types/
│   │       └── middleware.ts
├── docs/adr/                     # quyết định kiến trúc (16)
├── docs/specs/                   # spec triển khai (3)
├── docs/research/                # ghi chép primary-source (8)
├── docs/agents/                  # hợp đồng làm việc cho agent
├── CONTEXT.md                    # từ vựng chung (50 mục)
├── docker-compose.yml            # dev: db + redis + api (web sau profile `full`)
└── docker-compose.prod.yml       # prod: api + web (db sau profile `db`)
```

</details>

---

## API

49 endpoint, đều dưới `/api/v1`. Swagger đầy đủ ở http://localhost:8000/docs.

**`/auth`** (5) — access token ngắn hạn; refresh token là chuỗi đục, lưu dạng hash, xoay vòng mỗi lần dùng.

| | |
|---|---|
| `POST /register` `POST /login` | trả về cặp token |
| `POST /refresh` `POST /logout` | xoay vòng · thu hồi |
| `GET /me` | cần `Authorization: Bearer` |

**`/signals`** (1) — `GET /signals/volume-spikes?scope=profit_leaders|universe` — đột biến khối lượng cho một Signal Scope, kèm coverage, freshness, và danh sách mã không đánh giá được.

**`/jobs`** (8) — `GET /status` · `GET /collector` · `GET /backfill` poll tiến độ; `POST /trigger/collector` · `/trigger/backfill` · `/trigger/warmup` · `/trigger/market-catchup` · `/trigger/profit-census` (admin).

<details>
<summary><strong><code>/stocks</code> — 35 endpoint theo domain</strong></summary>

**snapshot** (3) — `GET /{symbol}/snapshot` · `/{symbol}/series/market` · `/{symbol}/series/valuation` — đọc thẳng từ store, mỗi điểm mang nguồn và tuổi dữ liệu

**market** (6) — `GET /symbols` · `/symbols/group/{group}` · `/symbols/search` · `/sector-performance` · `/fund-certificates` · `/vn30-overview`

**price** (7) — `GET /{symbol}/history` · `/{symbol}/intraday` · `/market-indices` · `/price-board` · `/{symbol}/volume-analysis` · `/{symbol}/volume-anomalies` · `POST /intraday/collect` (admin)

**company** (6) — `GET /{symbol}/company` · `/{symbol}/detail` · `/{symbol}/shareholders` · `/{symbol}/officers` · `/{symbol}/insider-deals` · `/{symbol}/ratio-summary`

**financial** (9) — `GET /{symbol}/financials/ratios` · `/income` · `/income-statement` · `/balance-sheet` · `/balance-sheet-detailed` · `/cash-flow`, cộng `/{symbol}/health-score` · `/{symbol}/trend-metrics` · `/{symbol}/fcf-analysis`

**analytics** (3) — `GET /analytics/sector-peers` · `/analytics/sector-historical` · `POST /analytics/sector-historical/refresh`

**trading** (1) — `GET /{symbol}/intraday-order-stats`

</details>

Danh sách endpoint nào đọc store và endpoint nào còn gọi provider trong request nằm ở [`docs/serving-path.md`](docs/serving-path.md).

**Rate limit** (sliding window, bật mặc định): 100 req/60s cho endpoint thường, **20 req/60s** cho endpoint nặng — mọi thứ đụng báo cáo tài chính hoặc quét khối lượng đều nằm nhóm nặng.

---

## Frontend

| Route | Trạng thái |
|---|---|
| `/` — Market Map | ✅ chỉ số, VN30, hiệu suất ngành |
| `/analytics/deep-dive` — Stock 360 | ✅ tìm mã, header, tabs (Overview · Finance · Shareholders · Volume) |
| `/analytics/volume-spikes` — Trends & Signals | ✅ hai Signal Scope, dải coverage luôn hiện, bảng mã không đánh giá được |
| `/settings` | ✅ |
| `/login` · `/register` | ✅ session bằng cookie httpOnly |

Alpha Desk sẽ là tab đầu tiên và là nơi Watchlist sống — chưa có code, spec ở [`docs/specs/0002-alpha-desk-product.md`](docs/specs/0002-alpha-desk-product.md).

---

<details>
<summary><strong>Lệnh hay dùng</strong></summary>

Nguồn sự thật: [`package.json`](package.json) ở root, [`apps/api/Makefile`](apps/api/Makefile), [`apps/web/package.json`](apps/web/package.json).

```bash
# Chạy
pnpm dev                # api+db trong Docker, web trên host  ← mặc định
pnpm dev:api            # chỉ backend, foreground
pnpm dev:api:detach     # chỉ backend, detached
pnpm dev:full           # tất cả trong Docker
pnpm stop               # docker compose down
pnpm stop:clean         # down -v — XOÁ LUÔN volume database

# Log
pnpm logs · logs:api · logs:db

# Database
pnpm db:migrate         # alembic upgrade head (api cũng tự chạy khi khởi động)
pnpm db:shell           # psql vào container db
pnpm db:restore         # nạp data_export.sql (không kèm trong repo)
pnpm api:shell          # bash vào container api

# Tạo migration mới — chạy tại apps/api, cần DB đang lên
alembic revision --autogenerate -m "mô tả"

# Frontend
pnpm build:web          # cần API đang chạy, xem cảnh báo bên dưới
pnpm start:web
```

> `pnpm build:web` báo `fetch failed` / `ECONNREFUSED` khi API tắt — vài trang analytics fetch trong lúc prerender. Bật backend trước.

</details>

<details>
<summary><strong>Triển khai production</strong></summary>

Production chạy **cả hai** app trong Docker (`stockmassive-api`, `stockmassive-web`).

```bash
docker compose -f docker-compose.prod.yml up -d --build

# Tự host luôn Postgres trên cùng máy:
docker compose -f docker-compose.prod.yml --profile db up -d --build
```

Bắt buộc: `DATABASE_URL` và `AUTH_SECRET`.

</details>

---

## Đóng góp

Ba quy tắc này là bắt buộc, cả người lẫn agent.

**1. Nhánh** — `develop` là nhánh tích hợp. Mọi tính năng / sửa lỗi tách nhánh riêng từ `develop`, làm trong **git worktree**, rồi merge ngược về `develop`. `main` được protected, chỉ nhận merge từ `develop`.

**2. Cổng kiểm tra trước khi báo xong**

```bash
cd apps/api && make test                              # backend
cd apps/web && pnpm type-check && pnpm lint \
            && pnpm test && pnpm build                # frontend
```

Phần nào không chạy được thì **nói rõ phần đó** — đừng im lặng bỏ qua.

**3. Commit** — Conventional Commits, mô tả thay đổi kỹ thuật. Giữ ngoài index: secrets, `.env`, dữ liệu nhạy cảm, dump database, file sinh tự động.

---

## Dành cho agent

Đọc theo thứ tự này trước khi sửa code:

1. **[`CLAUDE.md`](CLAUDE.md)** — quy ước repo, lệnh chạy, cổng kiểm tra.
2. **[`CONTEXT.md`](CONTEXT.md)** — từ vựng chung, 50 mục. Đặt tên biến / hàm / file theo đúng từ ở đây; mỗi mục có kèm danh sách *Avoid*.
3. **[`docs/adr/`](docs/adr/)** — 16 ADR. Đọc cái nào chạm tới vùng bạn sắp làm: 0001–0002 ranh giới phục vụ và Capability · 0003–0005 cohort, census, Warm-up · 0006 Price Basis và điều chỉnh lúc đọc · 0007–0016 lớp agent (loop, tool catalog, statistical bar, transport, budget, guardrail, eval).
4. **[`docs/specs/`](docs/specs/)** — spec triển khai. `0001` là nền dữ liệu (M0–M2 đã build), `0002` sản phẩm Alpha Desk, `0003` kiến trúc Intelligent Quant với milestone A1–A7.
5. **[`docs/agents/`](docs/agents/)** — [eval battery](docs/agents/eval-battery.md): `make eval` chạy trên DB riêng, và quy trình đóng băng lại Eval Fixture.

Vài cái bẫy đã có người dẫm:

- `apps/api/AGENTS.md` do **vnstock tự sinh**, không phải quy ước của repo này. Bỏ qua nó.
- Root lockfile rỗng và đây **không phải pnpm workspace**. `apps/web` có `package.json` + lockfile riêng; script ở root chỉ là wrapper quanh `docker compose` và `pnpm --dir apps/web`.
- Đừng thêm lời gọi provider vào đường phục vụ request. Chỉ `Collector` được gọi ra ngoài — xem [ADR 0001](docs/adr/0001-universe-va-phuc-vu-tu-snapshot.md) và [`docs/serving-path.md`](docs/serving-path.md).
- `core/trading_calendar.is_trading_day` chỉ biết thứ trong tuần, **không có lịch nghỉ lễ**. Nó trả lời "hôm nay có nên chạy cycle không". Đừng dùng nó để đóng nhãn ngày cho một `Snapshot` hay một tín hiệu — **Trading Day** suy từ dữ liệu, ở `stocks/trading_day.py`.
- `stock_daily_ohlcv` **không phải** kho lịch sử: trung vị 72 phiên/mã, có lỗ bảy tháng, và giá tính bằng nghìn đồng trong khi `provider_snapshots` giữ VND. Cửa sổ trailing phải đọc `provider_snapshots`.
- Trước khi chạy job nặng, nhớ quota vnstock 20 req/phút. `make test` không đụng mạng; các job nền thì có.

---

## Nó không phải cái gì

- **Không phải màn hình theo dõi cả thị trường.** Universe trần 100 mã là cố ý, không phải giới hạn tạm thời — và mọi tín hiệu đều nói rõ nó thấy được bao nhiêu phần phạm vi của mình.
- **Không phải nơi mô hình tự tính số.** Số do code tính, mô hình chỉ diễn giải; field nào không qua được thanh chắn thống kê thì không được đăng ký, nên không có đường nào tới mô hình.
- **Không phải tư vấn đầu tư cá nhân.** Có nhận định vùng giá, không có phân bổ vốn hay đòn bẩy theo hoàn cảnh của bạn — hệ thống không biết tài sản, kỳ hạn hay mức chịu lỗ của ai.
- **Chưa xong.** Cột 🚧 và 💭 ở trên là thật.

---

<p align="center"><sub>MIT · dữ liệu từ <a href="https://vnstocks.com">vnstock</a> và <a href="https://fiinquant.vn">FiinQuant</a></sub></p>
