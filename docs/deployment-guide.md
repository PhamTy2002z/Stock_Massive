# Deployment Guide - Stock Massive

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- pnpm (for frontend)

---

## Quick Start (Docker)

### 1. Clone Repository

```bash
git clone <repo-url>
cd Stock_Massive
```

### 2. Environment Setup

```bash
# Copy environment templates
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Access Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432

---

## Docker Services

### docker-compose.yml Overview

| Service | Port | Image | Description |
|---------|------|-------|-------------|
| db | 5432 | postgres:16-alpine | PostgreSQL database |
| api | 8000 | ./apps/api | FastAPI backend |
| web | 3000 | ./apps/web | Next.js frontend |

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

# Remove volumes (reset database)
docker-compose down -v
```

---

## Local Development

### Frontend (apps/web)

```bash
cd apps/web

# Install dependencies
pnpm install

# Start development server
pnpm dev

# Build for production
pnpm build

# Start production server
pnpm start

# Lint code
pnpm lint
```

### Backend (apps/api)

```bash
cd apps/api

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=src
```

---

## Environment Variables

### Backend (apps/api/.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stock_massive

# JWT (when auth is implemented)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:3000

# Scheduler
SCHEDULER_ENABLED=true
```

### Frontend (apps/web/.env)

```env
# API URL
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Docker Environment

When running with Docker, the API URL should point to the Docker service name:

```env
# apps/web/.env for Docker
NEXT_PUBLIC_API_URL=http://api:8000/api/v1
```

---

## Database Setup

### Run Migrations

```bash
cd apps/api

# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

### Database Connection

```bash
# Connect via psql
psql -h localhost -U postgres -d stock_massive

# Via Docker
docker-compose exec db psql -U postgres -d stock_massive
```

### Database Schema

Current tables:
- `intraday_bars` - 5-minute OHLCV bars for volume analysis

---

## Scheduled Jobs

### Intraday Data Collection

- **Schedule**: Daily at 15:30 ICT (after market close)
- **Function**: Collects tick data, aggregates to 5-min bars
- **Storage**: PostgreSQL `intraday_bars` table

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
# Check if database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Verify connection string
psql "postgresql://postgres:postgres@localhost:5432/stock_massive"
```

**vnstock import errors**

```bash
# Ensure vnstock is installed
pip install vnstock>=3.0.0

# Check Python version (requires 3.11+)
python --version

# Reinstall vnstock
pip uninstall vnstock
pip install vnstock>=3.0.0
```

**Frontend build errors**

```bash
# Clear cache and reinstall
rm -rf node_modules .next
pnpm install
pnpm build
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

### Database Health

```bash
docker-compose exec db pg_isready -U postgres
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
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100 api
```

### Log Locations (Local Development)

- **API**: Console output (uvicorn)
- **Web**: Console output (next dev)
- **Database**: Docker logs

---

## Backup and Restore

### Database Backup

```bash
# Backup
docker-compose exec db pg_dump -U postgres stock_massive > backup.sql

# Restore
docker-compose exec -T db psql -U postgres stock_massive < backup.sql
```

### Volume Backup

```bash
# List volumes
docker volume ls

# Backup volume
docker run --rm -v stock_massive_postgres_data:/data -v $(pwd):/backup alpine tar cvf /backup/postgres_backup.tar /data
```
