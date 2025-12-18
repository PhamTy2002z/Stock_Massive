# Stock Massive

Stock analysis platform with real-time charting and data tables.

## Tech Stack

- **Frontend**: Next.js 14+, TypeScript, TailwindCSS, ShadCN/UI, TradingView Charts, TanStack Table
- **Backend**: FastAPI, Python 3.11+, SQLAlchemy 2.0
- **Database**: PostgreSQL 16
- **DevOps**: Docker, Docker Compose

## Project Structure

```
Stock_Massive/
├── apps/
│   ├── web/                 # Next.js frontend
│   │   └── src/
│   │       ├── app/         # App Router pages
│   │       ├── components/  # React components
│   │       ├── hooks/       # Custom hooks
│   │       ├── lib/         # Utilities
│   │       ├── services/    # API clients
│   │       └── types/       # TypeScript types
│   │
│   └── api/                 # FastAPI backend
│       └── src/
│           ├── api/         # API routes (versioned)
│           ├── auth/        # Auth module
│           ├── stocks/      # Stocks module
│           ├── core/        # Shared utilities
│           └── workers/     # Background tasks
│
├── packages/                # Shared code
│   ├── config/              # Shared configs
│   └── types/               # Shared TypeScript types
│
├── docker/                  # Docker configs
└── docs/                    # Documentation
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- pnpm (recommended)

### Development Setup

```bash
# Clone repository
git clone <repo-url>
cd Stock_Massive

# Start services with Docker
docker-compose up -d

# Frontend (in apps/web)
cd apps/web
pnpm install
pnpm dev

# Backend (in apps/api)
cd apps/api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Documentation

- [Tech Stack](docs/tech-stack.md)
- [System Architecture](docs/system-architecture.md)

## License

MIT