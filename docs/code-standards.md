# Code Standards

## General Principles
- **YAGNI**: Don't build features until needed
- **KISS**: Prefer simple solutions
- **DRY**: Extract common patterns, avoid duplication

## Frontend (TypeScript/React)

### File Naming
- Components: `kebab-case.tsx` (e.g., `stock-chart.tsx`)
- Hooks: `use-kebab-case.ts` (e.g., `use-chart-data.ts`)
- Types: `kebab-case.types.ts`
- Utils: `kebab-case.ts`

### Component Structure
```tsx
// 1. Imports
import { useState } from 'react'

// 2. Types
interface Props {
  symbol: string
}

// 3. Component
export function StockChart({ symbol }: Props) {
  // hooks first
  const [data, setData] = useState(null)

  // handlers
  const handleClick = () => {}

  // render
  return <div>{symbol}</div>
}
```

### Best Practices
- Use `"use client"` only when needed
- Prefer Server Components by default
- Extract reusable logic to hooks
- Use barrel exports (`index.ts`) for public APIs

## Backend (Python/FastAPI)

### File Naming
- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Module Structure
```python
# router.py - HTTP endpoints
# service.py - Business logic
# repository.py - Data access
# schemas.py - Pydantic models
# models.py - SQLAlchemy models
```

### Best Practices
- Type hints on all functions
- Async by default for I/O operations
- Use dependency injection
- Validate all inputs with Pydantic

## Git Conventions

### Branch Naming
- `feature/short-description`
- `fix/issue-description`
- `refactor/what-changed`

### Commit Messages
```
type(scope): short description

- feat: new feature
- fix: bug fix
- refactor: code change (no feature/fix)
- docs: documentation
- test: tests
- chore: maintenance
```

## Testing

### Frontend
- Unit: Vitest for utilities/hooks
- Component: React Testing Library
- E2E: Playwright (if needed)

### Backend
- Unit: pytest
- Integration: pytest + TestClient
- Coverage target: 80%+

## API Design

### Endpoint Naming
- Use plural nouns: `/stocks`, `/users`
- Use kebab-case for multi-word: `/price-board`
- Nest resources logically: `/stocks/{symbol}/financials/ratios`

### Response Format
- Always return JSON
- Use consistent field naming (snake_case for Python responses)
- Include pagination for list endpoints

### Error Handling
```python
# Standard error response
{
    "detail": "Error message",
    "code": "ERROR_CODE"
}
```

## vnstock Integration

### Service Pattern
```python
# stocks/service.py
class StockService:
    def __init__(self):
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    async def get_history(self, symbol: str, ...):
        # Update symbol, fetch data
        self.stock.symbol = symbol
        return self.stock.quote.history(...)
```

### Data Source
- Primary: VCI (Vietnam)
- Always handle vnstock exceptions gracefully
