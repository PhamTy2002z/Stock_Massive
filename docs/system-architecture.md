# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Next.js Frontend                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  ShadCN UI  │  │  TradingView │  │  TanStack Table    │  │
│  │  Components │  │  Charts      │  │  Data Tables       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Auth     │  │   Stocks    │  │   Background Jobs   │  │
│  │   Module    │  │   Module    │  │   (Celery/ARQ)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                      PostgreSQL                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Users    │  │   Stocks    │  │   Analysis Data     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Directory StructureStock_Massive/
├── apps/
│   ├── web/                      # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/              # App Router pages
│   │   │   ├── components/       # React components
│   │   │   ├── hooks/            # Custom hooks
│   │   │   ├── lib/              # Utilities
│   │   │   ├── services/         # API clients
│   │   │   └── types/            # TypeScript types
│   │   ├── public/
│   │   └── package.json
│   │
│   └── api/                      # FastAPI backend
│       ├── src/
│       │   ├── api/              # API routes (versioned)
│       │   ├── auth/             # Auth module
│       │   ├── stocks/           # Stocks module
│       │   ├── core/             # Shared utilities
│       │   ├── workers/          # Background tasks
│       │   └── main.py
│       ├── alembic/              # DB migrations
│       └── requirements.txt
│
├── packages/                     # Shared code
│   ├── config/                   # Shared configs
│   └── types/                    # Shared TypeScript types
│
├── docker/                       # Docker configs
├── docs/                         # Documentation
├── docker-compose.yml
└── README.md
```

## Data Flow

1. **User Request** → Next.js handles routing and SSR
2. **API Call** → Next.js calls FastAPI endpoints
3. **Business Logic** → FastAPI services process request
4. **Data Access** → Repository layer queries PostgreSQL
5. **Response** → Data flows back through layers

## Security Layers

- **Frontend**: HTTPS, CSP headers, XSS protection
- **API**: JWT auth, CORS, rate limiting, input validation
- **Database**: Connection pooling, parameterized queries
- **Infrastructure**: Docker network isolation
