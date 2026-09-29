# AGENTS.md - DevERP AI Agent Working Rules

DevERP is a 100% free and open-source ERP for IT/software services companies.

## Hard Constraints
- **Stack**: Django 5.2 + DRF + simplejwt + drf-spectacular + django-allauth + django-otp (TOTP 2FA) + django-q2 (ORM broker) + whitenoise (SQLite in dev, PostgreSQL in prod); React 18 + Vite + TypeScript (strict) + Tailwind 3 + TanStack Query + react-hook-form + zod + Recharts.
- **Zero Paid/Cloud Dependencies**: No paid APIs/SaaS, no payment gateways (manual recording), no SMS, no Redis. Must run via `docker compose up` and locally without Docker using SQLite.
- **Quality & Integrity**: No placeholders, stubs, TODOs, or fake logic. Every delivered feature works end-to-end. Never run destructive commands (`git reset --hard`, `git push --force`, `rm -rf`, dropping DBs). Never weaken or delete a test to make it pass.
- **Precision**: Money uses `Decimal` (never float) with base currency. Timezone-aware datetimes. Multi-step mutations execute inside `transaction.atomic`.
- **Security**: RBAC on every endpoint plus object-level scoping. Use roles from `apps.core`. Audit log business actions.

## Execution Rules
1. **Single Agent**: Use exactly ONE agent. Do not spawn parallel subagents. Do not use browser agent or screen recording unless requested.
2. **One Slice Per Session**: Work strictly one slice at a time, then stop.
3. **Approval First**: Before coding a slice, present a short implementation plan (files to touch, models, endpoints, screens, tests) and wait for user approval. Read only files the slice touches.
4. **End-to-End Scope**: Every slice delivers backend (model, migration, service in `services.py`, serializer, view, permissions, urls, tests) AND frontend (small modular files under `src/features/<module>/`, route in `router.tsx`, nav in `app-shell.tsx`).
5. **Oversized Files Caution**: `frontend/src/features/hr/hr-page.tsx`, `frontend/src/features/projects/projects-page.tsx`, and `backend/apps/projects/views.py` are oversized legacy files. Never open them in full; search for specific symbols. Do not append to them; create new feature files. They will be refactored only in slice 8e.
6. **Required Quality Checks**:
   - Backend (from `/backend`):
     ```powershell
     python -m ruff check .
     python -m ruff format --check .
     python -m mypy apps config
     python -m pytest --cov=apps --cov-fail-under=80
     ```
   - Frontend (from `/frontend`):
     ```powershell
     npm run lint
     npx tsc -b
     npm test
     npm run build
     ```
7. **Documentation & Handoff**: Update `docs/API.md` and `README.md` route tables with new endpoints. Check off slice in `PROGRESS.md`. Commit with `Slice <id>: <title>`.
8. **Needs Human**: If human intervention is required (e.g. system packages, credentials), document exact instructions in `PROGRESS.md` under "Needs human", complete everything else, and stop.
