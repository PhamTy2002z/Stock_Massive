# Deployment Guide - Stock Massive

Cách chạy dự án ở môi trường development và production.

**Mô hình hiện tại:**

| Môi trường | Backend + Database | Frontend |
|------------|--------------------|----------|
| Development | Docker Compose (`db` + `api`) | Chạy trực tiếp trên máy (`next dev`, port 3000) |
| Production | Docker Compose (`api`, tùy chọn `db`) | Docker (`web`) |

Frontend **không** chạy trong Docker ở development: Next.js dev server trên host
có file watching gốc và rebuild nhanh hơn nhiều so với bind mount + polling.

---

## Development

### Prerequisites

- Docker 20.10+ và Docker Compose v2
- Node.js 20+ và pnpm 9+ (cho frontend)

### 1. Cấu hình environment

```bash
# Backend + database (các container trong docker-compose.yml)
cp .env.example .env

# Frontend (chạy trên host)
cp apps/web/.env.example apps/web/.env.local
```

Trong `.env`, tối thiểu cần đổi `AUTH_SECRET`:

```bash
openssl rand -base64 32
```

### 2. Khởi động backend trong Docker

```bash
docker compose up -d --build
# hoặc: pnpm dev:api:detach
```

Lệnh này chỉ start `db` + `api`. Container `api` tự chờ database healthy rồi
chạy `alembic upgrade head` trước khi start uvicorn (xem `apps/api/entrypoint.sh`).

Kiểm tra:

```bash
curl http://localhost:8000/health
docker compose ps
```

### 3. Khởi động frontend trên máy

```bash
pnpm dev:web:install   # chỉ cần lần đầu / khi dependencies đổi
pnpm dev:web           # tương đương: cd apps/web && pnpm dev
```

### 4. Truy cập

| Service | URL | Chạy ở đâu |
|---------|-----|------------|
| Frontend | http://localhost:3000 | Host (`next dev`) |
| API | http://localhost:8000 | Container `api` |
| API Docs (Swagger) | http://localhost:8000/docs | Container `api` |
| Database | localhost:5432 | Container `db` |

### 5. (Tùy chọn) Nạp dữ liệu mẫu

```bash
pnpm db:restore   # đọc data_export.sql vào database rỗng
```

---

## Scripts ở repo root

| Script | Việc nó làm |
|--------|-------------|
| `pnpm dev` | Start backend (detached) rồi chạy frontend trên host |
| `pnpm dev:api` | Start `db` + `api`, log ra terminal (foreground) |
| `pnpm dev:api:detach` | Start `db` + `api` ở background |
| `pnpm dev:web` | Chạy Next.js dev server trên host (port 3000) |
| `pnpm dev:web:install` | Cài dependencies cho `apps/web` |
| `pnpm build:web` | `next build` — **cần API đang chạy** (xem cảnh báo dưới) |
| `pnpm start:web` | Chạy bản build production của frontend trên host |
| `pnpm dev:full` | Chạy cả frontend trong Docker (`--profile full`) |
| `pnpm stop` | `docker compose down` |
| `pnpm stop:clean` | `docker compose down -v` — **xóa cả volume database** |
| `pnpm logs` / `logs:api` / `logs:db` | Follow logs |
| `pnpm db:migrate` | `alembic upgrade head` trong container `api` |
| `pnpm db:shell` | `psql` vào container `db` |
| `pnpm db:restore` | Nạp `data_export.sql` |
| `pnpm api:shell` | Shell vào container `api` |

> **Cảnh báo về `next build`**: một số trang (ví dụ
> `/analytics/volume-spikes`) fetch API trong lúc prerender. Nếu API không chạy,
> build fail với `TypeError: fetch failed` / `ECONNREFUSED`. Luôn start backend
> trước khi `pnpm build:web` hoặc build image `web` cho production.

---

## Chạy frontend trong Docker (tùy chọn)

Service `web` trong `docker-compose.yml` nằm sau profile `full`, nên
`docker compose up` bình thường sẽ không start nó:

```bash
docker compose --profile full up -d --build
```

Trong container, frontend gọi API qua service name (`INTERNAL_API_URL=http://api:8000/api/v1`)
cho server components, còn browser vẫn dùng `NEXT_PUBLIC_API_URL`.

---

## Environment variables

### `.env` (root) — cấu hình các container

Xem `.env.example` cho danh sách đầy đủ. Các biến quan trọng:

```env
# Database container + connection string mà api dùng
DATABASE_URL=postgresql://postgres:postgres@db:5432/stockmassive
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=stockmassive
POSTGRES_PORT=5432

# Auth (JWT) — bắt buộc đổi
AUTH_SECRET=<openssl rand -base64 32>

# CORS: origin của frontend đang chạy trên host
CORS_ORIGINS=http://localhost:3000
API_PORT=8000

# Optional
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
VNSTOCK_API_KEY=
SCHEDULER_ENABLED=true
```

Muốn dùng Postgres bên ngoài (managed): trỏ `DATABASE_URL` tới nó (thêm
`?sslmode=require` nếu host yêu cầu). `entrypoint.sh` nhận ra host khác `db`/`localhost`
và bỏ qua bước chờ, migration chạy non-blocking.

### `apps/web/.env.local` — cấu hình frontend trên host

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_SITE_URL=http://localhost:3000
# INTERNAL_API_URL chỉ cần khi frontend chạy trong Docker
```

`INTERNAL_API_URL` được server components / route handlers ưu tiên, fallback về
`NEXT_PUBLIC_API_URL`, rồi `http://localhost:8000/api/v1`
(`apps/web/src/lib/api.ts`, `apps/web/src/lib/auth/api.ts`).

Đổi port frontend thì phải sửa `CORS_ORIGINS` trong `.env` cho khớp, nếu không
request từ browser bị API chặn.

---

## Database

### Migrations

Container `api` tự chạy `alembic upgrade head` khi start. Chạy tay:

```bash
pnpm db:migrate
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic downgrade -1
docker compose exec api alembic history
```

### Tables hiện có

| Table | Nội dung |
|-------|----------|
| `users` | Tài khoản (email + bcrypt hash) |
| `refresh_tokens` | Refresh token đã hash, rotate mỗi lần dùng |
| `stock_daily_ohlcv` | OHLCV ngày cho toàn bộ symbol |
| `stock_intraday_bars` | Bar 5 phút cho volume analysis |
| `financial_statements` | Báo cáo tài chính theo quý + ranking lợi nhuận |

### Backup / restore

```bash
# Backup (database trong Docker)
docker compose exec -T db pg_dump -U postgres stockmassive > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker compose exec -T db psql -U postgres -d stockmassive -v ON_ERROR_STOP=1 < backup.sql
```

Luôn backup trước khi chạy migration thay đổi schema.

---

## Scheduled jobs

Bật/tắt bằng `SCHEDULER_ENABLED`. Giờ mặc định lấy từ
`apps/api/src/core/config.py` (giờ Việt Nam):

| Job | Thời điểm | Kết quả |
|-----|-----------|---------|
| Intraday collection | 15:30 hàng ngày | `stock_intraday_bars` |
| Daily OHLCV | 16:00 hàng ngày | `stock_daily_ohlcv` |
| Sector historical | 15:45 hàng ngày | Cache hiệu suất ngành |
| Financial statements | 02:00 Chủ nhật | `financial_statements` |

Theo dõi tiến độ: `GET /api/v1/jobs/status`. Trạng thái scheduler:
`GET /scheduler/status`.

Trigger tay:

```bash
curl -X POST "http://localhost:8000/api/v1/stocks/intraday/collect?symbols=VCB&symbols=FPT"
```

---

## Production

Chi tiết từng bước trên VPS: [VPS Deployment Guide](vps-deployment-guide.md).

Tóm tắt:

```bash
cp .env.example .env      # điền DATABASE_URL, AUTH_SECRET, CORS_ORIGINS, NEXT_PUBLIC_API_URL
docker compose -f docker-compose.prod.yml up -d --build
```

- `api` và `web` chạy thành 2 container riêng (`stockmassive-api`, `stockmassive-web`),
  cùng network `stockmassive-network`, build từ `Dockerfile.prod` của từng app.
- `DATABASE_URL` và `AUTH_SECRET` là **bắt buộc** — compose fail nếu thiếu.
- Mặc định **không có** container database: `DATABASE_URL` phải trỏ tới Postgres
  bạn tự quản lý. Muốn self-host Postgres trên cùng máy, thêm profile `db`:

```bash
docker compose -f docker-compose.prod.yml --profile db up -d --build
```

- `NEXT_PUBLIC_API_URL` là **build arg** của image `web`; đổi giá trị này phải
  rebuild image `web`, không chỉ restart.

### Checklist trước khi live

- [ ] `AUTH_SECRET` random, không dùng giá trị mẫu
- [ ] `POSTGRES_PASSWORD` mạnh (nếu dùng profile `db`)
- [ ] `CORS_ORIGINS` trỏ đúng domain production
- [ ] `NEXT_PUBLIC_API_URL` trỏ đúng domain API và đã rebuild `web`
- [ ] `DEBUG=false`
- [ ] HTTPS + reverse proxy đã cấu hình
- [ ] Backup database đã setup
- [ ] Rate limiting và Redis (nếu dùng) đã kiểm tra

---

## Troubleshooting

**Port đã bị chiếm**

```bash
lsof -i :3000
lsof -i :8000
lsof -i :5432
```

Đổi `API_PORT` / `POSTGRES_PORT` trong `.env` thay vì kill process của stack khác.
Chạy nhiều worktree song song: set `COMPOSE_PROJECT_NAME` khác nhau.

**API không kết nối được database**

```bash
docker compose logs api | grep -i -E "database|migration"
docker compose ps db
pnpm db:shell
```

**Frontend gọi API bị lỗi CORS**

`CORS_ORIGINS` trong `.env` phải chứa đúng origin của frontend
(`http://localhost:3000`). Sửa xong cần `docker compose up -d api` để container
nhận biến mới.

**`pnpm build:web` fail với `fetch failed`**

Backend chưa chạy. Start `docker compose up -d` rồi build lại.

**Lỗi import vnstock**

```bash
docker compose logs api
docker compose up -d --build api
```

---

## Health checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/scheduler/status
curl http://localhost:8000/api/v1/stocks/symbols
curl http://localhost:8000/api/v1/stocks/market-indices
curl -I http://localhost:3000
```
