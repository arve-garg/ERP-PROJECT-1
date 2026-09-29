# Next Slice Workflow (`/next-slice`)

Execute this workflow when the user requests `/next-slice` or instructs you to proceed with the next slice.

## Procedure

1. **Context & Orientation**
   - Read `AGENTS.md` for hard constraints and working rules.
   - Read `PROGRESS.md` to identify the first unchecked slice in the roadmap.
   - Review relevant documentation (`docs/SPEC.md`, `docs/API.md`) and only the specific existing code files that the slice directly touches or integrates with.

2. **Planning & User Approval**
   - Prepare a concise implementation plan:
     - Files to create/touch (backend & frontend)
     - Data models & migrations
     - Services & business logic (in `services.py`)
     - Endpoints, permissions, and serializers
     - Frontend UI screens, routes, and navigation
     - Automated test strategy (backend coverage >= 80%, edge cases, frontend tests)
   - Present the plan to the user and **wait for user approval**. Do not write code before approval.

3. **Implementation**
   - **Backend**:
     - Create/update models inheriting `AuditedModel`.
     - Write migration (`python manage.py makemigrations <app>`).
     - Implement business logic in `services.py` inside `transaction.atomic` where appropriate.
     - Implement serializers, views, permissions, and url routing.
     - Mount app in `INSTALLED_APPS` and `backend/config/urls.py` if adding a new app.
     - Write comprehensive backend tests in `apps/<module>/tests/` or `apps/<module>/tests.py` verifying happy paths, permission boundaries, negative/edge cases, and audit logging.
   - **Frontend**:
     - Create modular feature components, hooks, and API client methods under `frontend/src/features/<module>/`.
     - Add routes to `frontend/src/app/router.tsx` with appropriate auth/role guards.
     - Add navigation entry in `frontend/src/components/layout/app-shell.tsx`.
     - Implement loading skeletons, empty states, error states, and responsive styling.
     - Add frontend tests verifying key rendering, interaction, and validation.

4. **Run Quality Checks**
   - Backend checks (run from `/backend`):
     ```powershell
     python -m ruff check .
     python -m ruff format --check .
     python -m mypy apps config
     python -m pytest --cov=apps --cov-fail-under=80
     ```
   - Frontend checks (run from `/frontend`):
     ```powershell
     npm run lint
     npx tsc -b
     npm test
     npm run build
     ```
   - Fix any issues until all checks pass cleanly.

5. **Documentation & Handoff**
   - Update `docs/API.md` with new endpoints and payload contracts.
   - Update `README.md` route table if new top-level routes or modules were introduced.
   - Mark the slice as completed `[x]` in `PROGRESS.md`.
   - Update `PROGRESS.md` sections (Decisions, Known gaps, Needs human) if applicable.
   - Commit the changes with message:
     ```
     Slice <id>: <title>
     ```
   - Stop and report the completed slice and outline the next slice.
