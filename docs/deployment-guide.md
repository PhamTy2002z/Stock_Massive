# Deployment Guide - Stock Massive

> **Note**: Project chạy bằng Docker. Database sử dụng Supabase cloud PostgreSQL.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

---

## Quick Start (Development)

### 1. Clone Repository

```bash
git clone <repo-url>
cd Stock_Massive
```

### 2. Environment Setup

```bash
# Copy environment templates
cp .env.example .env
# Edit .env with your Supabase DATABASE_URL and AUTH_SECRET
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Run Database Migrations

```bash
docker-compose exec api alembic upgrade head
```

### 5. Access Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Production Deployment

### 1. Environment Setup

```bash
# Copy and configure production environment
cp .env.example .env

# Generate secure AUTH_SECRET
openssl rand -base64 32
```

**Required environment variables for production:**
- `DATABASE_URL` - Supabase database connection (session pooler)
- `AUTH_SECRET` - Secure authentication secret
- `CORS_ORIGINS` - Your production domain
- `NEXT_PUBLIC_API_URL` - Your API domain

### 2. Build and Deploy

```bash
# Build and start production containers
docker-compose -f docker-compose.prod.yml up -d --build

# Migrations run automatically via entrypoint script
```

### 3. Verify Deployment

```bash
# Check all services are running
docker-compose -f docker-compose.prod.yml ps

# Check API health
curl http://localhost:8000/health

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

---

## Docker Services

### docker-compose.yml Overview

| Service | Port | Image | Description |
|---------|------|-------|-------------|
| api | 8000 | ./apps/api | FastAPI backend |
| web | 3000 | ./apps/web | Next.js frontend |

> **Note**: Database chạy trên Supabase cloud, không có trong Docker Compose.

### Service Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Rebuild services
docker-compose up -d --build
```

---

## Environment Variables

Reference `.env.example` for all available variables. Key ones:

```env
# Database - Supabase (required)
DATABASE_URL=postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require
DATABASE_URL_DIRECT=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# API
AUTH_SECRET=your-secret-key-here
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Supabase (for auth)
NEXT_PUBLIC_SUPABASE_URL=https://[project-ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

---

## Supabase Database Connection

### Configuration

When using Supabase as database:

1. **DATABASE_URL** - Async connection (asyncpg) for API endpoints
2. **DATABASE_URL_DIRECT** - Sync connection (psycopg2) for Alembic migrations and background jobs

### SSL Requirements

Supabase requires SSL connections. The application automatically configures:
- `sslmode=require` for async connections
- SSL context for sync connections

### Environment Setup

```bash
# .env for Supabase
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres?sslmode=require
DATABASE_URL_DIRECT=postgresql+psycopg2://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres?sslmode=require
```

---

### Database Setup

Database PostgreSQL chạy trên Supabase cloud.

#### Run Migrations

```bash
# Chạy migrations với DATABASE_URL_DIRECT (direct connection)
docker-compose exec api alembic upgrade head

# Generate migration mới
docker-compose exec api alembic revision --autogenerate -m "description"

# Rollback migration
docker-compose exec api alembic downgrade -1

# Xem migration history
docker-compose exec api alembic history
```

#### Database Connection (Supabase)

```bash
# Kết nối qua psql (direct connection)
psql "postgresql://postgres:[PASSWORD]@db.[project-ref].supabase.co:5432/postgres"

# Hoặc sử dụng Supabase Dashboard SQL Editor
```

### Database Schema

Current tables:
- `stock_daily_ohlcv` - Daily OHLCV data for all symbols
- `intraday_bars` - 5-minute OHLCV bars for volume analysis
- `financial_statements` - Quarterly financial data with profit rankings

---

## Scheduled Jobs

### Intraday Data Collection

- **Schedule**: Daily at 15:30 ICT (after market close)
- **Function**: Collects tick data, aggregates to 5-min bars
- **Storage**: PostgreSQL `intraday_bars` table

### Daily OHLCV Collection

- **Schedule**: Daily at 17:00 ICT
- **Function**: Collects daily OHLCV data for all symbols
- **Storage**: PostgreSQL `stock_daily_ohlcv` table

### Financial Statements Collection

- **Schedule**: Weekly on Sunday at 02:00 ICT
- **Function**: Fetches quarterly income statements, ranks by net profit
- **Storage**: PostgreSQL `financial_statements` table

### Job Status Monitoring

- **Endpoint**: `GET /api/v1/jobs/status`
- **Purpose**: Poll background job progress
- **Implementation**: In-memory store with startup recovery

To manually trigger collection:

```bash
curl -X POST "http://localhost:8000/api/v1/stocks/intraday/collect?symbols=VCB&symbols=FPT"
```

---

## Production Deployment

### Build Images

```bash
# Build all images
docker-compose -f docker-compose.prod.yml build

# Build specific service
docker-compose build api
```

### Production Checklist

- [ ] Set strong SECRET_KEY
- [ ] Configure proper CORS_ORIGINS
- [ ] Enable HTTPS
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Review security headers
- [ ] Configure rate limiting

### Recommended Production Stack

- **Reverse Proxy**: Nginx or Traefik
- **SSL**: Let's Encrypt
- **Database**: Managed PostgreSQL (AWS RDS, etc.)
- **Hosting**: AWS, GCP, or DigitalOcean
- **Monitoring**: Prometheus + Grafana

### Production Environment Variables

```env
# Backend
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/stock_massive
SECRET_KEY=<strong-random-key>
CORS_ORIGINS=https://yourdomain.com
SCHEDULER_ENABLED=true

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

---

## Troubleshooting

### Common Issues

**Port already in use**

```bash
# Find process using port (Linux/macOS)
lsof -i :3000
lsof -i :8000

# Find process using port (Windows)
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Kill process
kill -9 <PID>          # Linux/macOS
taskkill /PID <PID> /F # Windows
```

**Database connection failed**

```bash
# Check API logs for connection errors
docker-compose logs api | grep -i database

# Verify DATABASE_URL in .env is correct
# Test connection with psql
psql "$DATABASE_URL_DIRECT"
```

**vnstock import errors**

```bash
# Kiểm tra logs của API container
docker-compose logs api

# Rebuild API container
docker-compose up -d --build api
```

**Frontend build errors**

```bash
# Rebuild web container
docker-compose up -d --build web

# Xem logs
docker-compose logs web
```

**API not responding**

```bash
# Check API logs
docker-compose logs api

# Verify API is running
curl http://localhost:8000/health

# Check CORS configuration
curl -I http://localhost:8000/api/v1/stocks/symbols
```

---

## Health Checks

### API Health

```bash
curl http://localhost:8000/health
```

### Database Health (Supabase)

```bash
# Test connection
psql "$DATABASE_URL_DIRECT" -c "SELECT 1"

# Or check via Supabase Dashboard
```

### Full Stack Check

```bash
# Check all services
docker-compose ps

# Expected output: all services "Up" and "healthy"
```

### Verify API Endpoints

```bash
# List symbols
curl http://localhost:8000/api/v1/stocks/symbols

# Get market indices
curl http://localhost:8000/api/v1/stocks/market-indices

# Get stock detail
curl http://localhost:8000/api/v1/stocks/VCB/detail
```

---

## Logs and Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f web

# Last 100 lines
docker-compose logs --tail=100 api
```

### Log Locations (Local Development)

- **API**: Console output (uvicorn)
- **Web**: Console output (next dev)

---

## Backup and Restore

### Database Backup (Supabase)

Supabase cung cấp automated backups. Để backup thủ công:

```bash
# Backup qua psql
pg_dump "$DATABASE_URL_DIRECT" > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql "$DATABASE_URL_DIRECT" < backup.sql
```

Xem thêm: [Supabase Backups Documentation](https://supabase.com/docs/guides/platform/backups)
