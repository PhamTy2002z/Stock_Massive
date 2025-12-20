# Phase 1: Supabase Setup

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Phase**: 1 of 5
- **Dependencies**: None
- **Next Phase**: [phase-02-schema-migration.md](./phase-02-schema-migration.md)

## Overview
**Date**: 2025-12-21
**Description**: Create Supabase project and obtain connection credentials
**Priority**: P1
**Status**: done
**Completed**: 2025-12-21 01:33
**Effort**: 30min

## Key Insights
- Supabase provides two connection modes: Direct (port 5432) and Pooler (port 6543)
- Transaction mode pooler (6543) recommended for application connections
- Session mode (5432) required for migrations and DDL operations
- SSL certificates required for secure connections
- Connection string format differs from local PostgreSQL

## Requirements
- Supabase account (free tier sufficient for development)
- Access to Supabase dashboard
- Note-taking tool for credentials (use password manager)

## Architecture Changes
None - this phase only provisions infrastructure

## Related Code Files
None yet - credentials will be used in Phase 3

## Implementation Steps

### Step 1: Create Supabase Project
1. Navigate to https://supabase.com/dashboard
2. Click "New Project"
3. Configure project:
   - **Name**: `stock-massive` or `stock-massive-dev`
   - **Database Password**: Generate strong password (save securely)
   - **Region**: Choose closest to deployment (e.g., `ap-southeast-1` for Vietnam)
   - **Plan**: Free tier for development
4. Wait for project provisioning (2-3 minutes)

### Step 2: Obtain Connection Credentials
1. Navigate to Project Settings > Database
2. Document the following:

**Direct Connection (Session Mode - Port 5432)**
```
Host: db.<project-ref>.supabase.co
Database: postgres
Port: 5432
User: postgres.{project-ref}
Password: [your-password]
```

**Pooler Connection (Transaction Mode - Port 6543)**
```
Host: aws-0-ap-southeast-1.pooler.supabase.com
Database: postgres
Port: 6543
User: postgres.{project-ref}
Password: [your-password]
```

**Connection Strings**:
```bash
# For migrations (Session mode)
DATABASE_URL_MIGRATION="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"

# For application (Transaction mode - pooled)
DATABASE_URL="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres"
```

### Step 3: SSL Certificate Configuration
1. In Project Settings > Database, find "SSL Certificate"
2. Download or copy the certificate
3. Save to secure location (will be configured in Phase 3)
4. Note: Supabase enforces SSL, connection will fail without it

### Step 4: Test Connection
Using psql or any PostgreSQL client:
```bash
# Test direct connection
psql "postgresql://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres?sslmode=require"

# Verify connection
SELECT version();
SELECT current_database();
```

Expected output: PostgreSQL 15.x (Supabase version)

### Step 5: Document Project Details
Create a secure note with:
- Project Reference ID
- Project URL
- Database passwords
- Connection strings (both modes)
- Region
- Created date

## Todo List
- [ ] Create Supabase project via dashboard
- [ ] Save database password securely
- [ ] Document project reference ID
- [ ] Copy direct connection string (port 5432)
- [ ] Copy pooler connection string (port 6543)
- [ ] Download/copy SSL certificate
- [ ] Test connection with psql
- [ ] Verify PostgreSQL version
- [ ] Document all credentials securely
- [ ] Proceed to Phase 2

## Success Criteria
- Supabase project created and active
- Can connect via psql using both direct and pooler connections
- All credentials documented securely
- SSL certificate obtained
- PostgreSQL version confirmed (15.x)

## Risk Assessment
**Low Risk**
- Supabase provisioning is automated and reliable
- Free tier sufficient for development/testing
- Can delete and recreate project if issues occur

**Potential Issues**:
- Region selection affects latency (choose wisely)
- Password must be saved before leaving setup page
- Connection limits on free tier (60 connections)

## Security Considerations
- **Never commit credentials** to git
- Use environment variables for all secrets
- Store passwords in password manager
- SSL required for all connections
- Consider IP allowlisting for production (Supabase Pro feature)
- Rotate passwords periodically

## Connection Limits by Tier
| Tier | Direct Connections | Pooler Connections |
|------|-------------------|-------------------|
| Free | 60 | 200 |
| Pro | 200 | 3000 |
| Team | 400 | 6000 |

## Next Steps
After completing this phase:
1. Proceed to [Phase 2: Schema Migration](./phase-02-schema-migration.md)
2. Keep credentials accessible for Phase 3 configuration
3. Do not modify local PostgreSQL yet (parallel operation during migration)

## Unresolved Questions
1. Production vs development project strategy (separate projects recommended)
2. Backup strategy for Supabase (automatic daily backups on Pro tier)
3. Monitoring and alerting setup (Supabase dashboard provides basic metrics)
