# Phase 1: Core Setup & Configuration

**Status:** Pending
**Priority:** High

## Context

- [plan.md](plan.md) - Main plan
- Codebase is greenfield - no existing patterns

## Overview

Set up project configuration, install vnstock, and create core utilities.

## Requirements

1. Install vnstock library
2. Create settings module with pydantic-settings
3. Set up logging configuration

## Implementation Steps

### 1.1 Add vnstock to requirements.txt
```
vnstock>=3.0.0
```

### 1.2 Create core/config.py
- Use pydantic-settings for env var management
- Define Settings class with validation

### 1.3 Create core/dependencies.py
- FastAPI dependency injection setup

## Todo List

- [ ] Add vnstock to requirements.txt
- [ ] Create apps/api/src/core/config.py
- [ ] Create apps/api/src/core/dependencies.py
- [ ] Test import and basic vnstock functionality

## Success Criteria

- `from vnstock import Vnstock` works
- Settings load from environment
- No import errors on app startup

## Risk Assessment

- **Low**: vnstock is well-maintained library
- Network dependency for data fetching

## Next Steps

Proceed to [phase-02-stock-data-service.md](phase-02-stock-data-service.md)
