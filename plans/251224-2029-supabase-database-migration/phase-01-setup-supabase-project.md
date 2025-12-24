# Phase 1: Setup Supabase Project

## Context
- **Parent:** [plan.md](./plan.md)
- **Research:** [researcher-01-supabase-sqlalchemy-config.md](./research/researcher-01-supabase-sqlalchemy-config.md)

## Overview

| Property | Value |
|----------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 15 min |

Create Supabase project and obtain connection credentials.

## Key Insights

- Region **Singapore (ap-southeast-1)** recommended for Vietnam users
- Need 2 connection strings: Session mode (runtime) + Direct (migrations)
- Free tier: 500MB storage, pauses after 7 days inactive

## Requirements

### Functional
- Create Supabase project
- Obtain connection strings for both runtime and migrations
- Configure project settings

### Non-Functional
- Use Singapore region for low latency
- Enable SSL connections

## Related Code Files

**Files to modify:** None (external setup)

**Files to reference:**
- `apps/api/src/core/config.py` - understand current env vars

## Implementation Steps

### Step 1: Create Supabase Account & Project

1. Go to [supabase.com](https://supabase.com) → Sign up/Login
2. Create New Project:
   - **Name:** `stock-massive` (or preferred name)
   - **Database Password:** Generate strong password, save securely
   - **Region:** Singapore (`ap-southeast-1`)
   - **Plan:** Free tier
3. Wait for project provisioning (~2 minutes)

### Step 2: Obtain Connection Strings

1. Go to Project Settings → Database
2. Copy **Session mode** connection string (port 5432):
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
3. Copy **Direct connection** string (for migrations):
   ```
   postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
   ```

### Step 3: Prepare Environment Variables

Create/update local `.env` file with:

```bash
# Supabase Database (Runtime - Session pooler)
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# Supabase Database (Migrations - Direct connection)
DATABASE_URL_DIRECT=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
```

### Step 4: Verify Connection

```bash
# Test connection (requires psql installed)
psql "$DATABASE_URL" -c "SELECT version();"
```

## Todo List

- [ ] Create Supabase account (if not exists)
- [ ] Create new project with Singapore region
- [ ] Copy Session mode connection string
- [ ] Copy Direct connection string
- [ ] Update local `.env` with credentials
- [ ] Verify connection with psql

## Success Criteria

- [ ] Supabase project created and active
- [ ] Both connection strings obtained
- [ ] Can connect via psql command
- [ ] Credentials stored in `.env`

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Wrong region selected | Double-check before creating, can't change later |
| Password lost | Store in password manager immediately |

## Security Considerations

- Never commit `.env` with Supabase credentials
- Use strong database password (16+ chars, mixed case, numbers, symbols)
- `.env` already in `.gitignore` (verify this)

## Next Steps

→ [Phase 2: Configure Backend Connection](./phase-02-configure-backend-connection.md)
