# API

The interactive OpenAPI reference is available at [`/api/docs/`](http://localhost:8080/api/docs/) when DevERP is running. The machine-readable schema is at `/api/schema/`.

All application endpoints are versioned under `/api/v1/`. Protected endpoints require a bearer access token returned by `POST /api/v1/auth/login/`; refresh it with `POST /api/v1/auth/token/refresh/`. List endpoints use page-number pagination and expose filtering, search, or ordering where supported by the resource.

## Core platform endpoints

| Area | Endpoints |
|---|---|
| Authentication | `POST /auth/login/`, `/auth/logout/`, `/auth/token/refresh/`, `/auth/password/reset/`, `/auth/password/reset/confirm/`, `/auth/2fa/setup/`, `/auth/2fa/confirm/`, `/auth/2fa/disable/` |
| Users and roles | `/users/`, `/users/me/`, `/roles/`, `/users/{id}/roles/` |
| User file exchange | `POST /users/import/`; `GET /users/export/?file_format=csv` or `?file_format=xlsx` |
| Audit | `GET /audit-logs/` |
| Notifications | `/notifications/`, `/notifications/unread-count/`, `/notifications/{id}/read/`, `/notifications/read-all/` |
| Company settings | `/company-settings/` |
| Saved filters and activity | `/saved-filters/`, `/activity-feed/` |
| Global search | `GET /search/?q={query}` |

The authentication, user, role, audit, notification, settings, saved-filter, and activity endpoints are relative to `/api/v1/`. Administrative writes are restricted to users with the Admin role. User notifications and private saved filters are scoped to their owner.

## Phase 2 HR endpoints

All routes in this section are relative to `/api/v1/hr/`.

| Area | Endpoints |
|---|---|
| Departments and designations | `/departments/`, `/designations/` |
| Employees | `/employees/`, `/employees/org-chart/`, HR/Admin-only `/employees/eligible-users/` |
| Emergency contacts | `/emergency-contacts/` |
| Employee documents | `/employee-documents/`, `/employee-documents/{id}/download/` |
| Attendance | `GET /attendance/`, `GET /attendance/monthly-summary/?year={year}&month={month}`, `POST /attendance/check-in/`, `POST /attendance/check-out/` |
| Leave | `/leave-types/`, `GET /leave-balances/`, `POST /leave-balances/{id}/adjust/`, `/leave-requests/`, `GET /leave-requests/calendar/?year={year}&month={month}`, `/leave-requests/{id}/approve/`, `/leave-requests/{id}/reject/` |
| Holidays | `/holidays/` |

Reads require authentication. HR or Admin can maintain department structure, leave types, balances, and holidays. Employees can view their own records and maintain their own emergency contacts and documents. Managers can see their own profile and direct reports. HR/Admin can access all employee records. Attendance check-in/out is limited to the signed-in employee. Only HR/Admin or the employee's direct manager can approve or reject a pending leave request.

Employee profiles are linked to existing active Employee-role DevERP user accounts. An Admin provisions the user account and assigns the Employee role in user management; HR or Admin selects an unlinked account from `/employees/eligible-users/` when creating the employee profile. This endpoint returns only active Employee-role accounts that do not yet have an employee profile.

`POST /attendance/check-in/` and `POST /attendance/check-out/` accept an empty JSON object. Late and early-departure flags use the `workday_start` and `workday_end` company settings (`HH:MM` strings), defaulting to 09:00 and 17:00. Leave requests calculate weekdays excluding company holidays. Monthly accrual is run by `python manage.py accrue_leave_balances --year YYYY --month MM`; the operation is safe to retry for a month.

Employee documents are limited to 10 MiB and supported PDF, PNG, JPEG, or DOCX file signatures. Downloads require authenticated access and employee-scope authorization.

## Phase 3 project delivery endpoints

All routes in this section are relative to `/api/v1/projects/`. List endpoints use the standard page-number pagination and support field filters, `search`, and `ordering` where available.

| Area | Endpoints |
|---|---|
| Clients and portal | `/clients/` |
| Projects | `/projects/`, `/projects/{id}/transition/`, `/projects/{id}/budget-summary/` |
| Milestones and sprints | `/milestones/`, `/milestones/{id}/transition/`, `/sprints/`, `/sprints/{id}/transition/`, `/sprints/{id}/backlog/`, `/sprints/{id}/burndown/` |
| Tasks | `/tasks/`, `/tasks/{id}/status/`, `/task-labels/`, `/task-comments/`, `/task-attachments/`, `/task-attachments/{id}/download/` |
| Timesheets | `/time-entries/`, `/time-entries/{id}/submit/`, `/time-entries/{id}/approve/`, `/time-entries/{id}/reject/`, `/time-submissions/`, `/time-submissions/{id}/approve/`, `/time-submissions/{id}/reject/` |
| Capacity and costs | `/resource-allocations/`, `/resource-allocations/capacity/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`, Finance/HR/Admin-only `/hourly-costs/` |
| Bugs, releases, project knowledge | `/bugs/`, `/bugs/{id}/status/`, `/release-notes/`, `/wiki-pages/`, `/documents/`, `/documents/{id}/download/` |

Managers can manage their managed/team projects and associated planning records; HR/Admin can access all internal project records. Employees see only their assigned tasks, own time entries, and related project records. Client-role accounts must be explicitly associated with a client via its portal users; they receive read-only access to that client, its projects, and project milestones. Client users cannot access internal tasks, sprints, comments, timesheets, or allocations.

Project, milestone, and sprint lifecycle changes use their `transition` actions rather than direct status edits. Task state changes use `POST /tasks/{id}/status/` with `{"status": "ready"}` (valid task states: `backlog`, `ready`, `in_progress`, `blocked`, `done`, `cancelled`). Project completion requires every task to be done or cancelled; milestone and sprint completion require their own tasks to be closed. Employees create draft time entries for their assigned tasks and submit them for review. Only HR/Admin or an authorized manager can approve or reject submitted time; rejection requires a decision note.

Task labels are assigned by label IDs in the task `labels` array. Task and project-document attachment creation uses multipart form data; supported private file types are signature-checked PDF, PNG, JPEG, and DOCX, limited to 10 MiB. Download actions require project/task scope and stream the file through the authenticated API. Sprint backlog returns the sprint's task list; burndown returns daily estimated-hours completed and remaining based on task completion timestamps. Both are bounded by the sprint's scheduled dates.

Create daily or weekly time submissions with `POST /time-submissions/`; creation submits the selected entry IDs together atomically. Example: `{"period_type":"weekly","period_start":"2026-09-28","period_end":"2026-10-04","entries":[12,13]}`. Weekly ranges must be Monday through Sunday. Approval or rejection applies consistently to every entry in the submission. Each time entry includes `is_billable` and an hourly-cost/currency snapshot. Finance/HR/Admin maintain effective-dated rates using `hourly_costs`; project budgets use `budget_currency` (defaulting to the configured base currency), and only rates in that currency are snapshotted and included in actual cost. Project summaries report unpriced hours. Automatic foreign-exchange conversion is not supported because the ERP has no FX-rate model. Resource capacity reports weekdays only, assumes eight base hours per workday, sums overlapping allocations, and flags allocations above 100%.

Bug records have severity and status workflows; only managers/HR/Admin can edit or archive them, while visible project employees may report bugs. Release notes may be published to associated client users. Wiki pages are internal; project documents are private unless their manager marks them `client_visible`.

## Project entity contract

All IDs and foreign keys are integer IDs. Paginated list responses use `{ "count", "next", "previous", "results" }`. Decimal fields are serialized as decimal strings. Timestamps are ISO-8601.

| Entity | Writable fields | Additional/read-only response fields |
|---|---|---|
| Client | `name`, `email`, `phone`, `website`, `address`, `notes`, `status`, `portal_users` | `id`, `created_at`, `updated_at`; client portal users receive no `notes` or `portal_users` |
| Project | `client`, `name`, `code`, `description`, `manager`, `start_date`, `end_date`, `estimated_hours`, `budget`, `budget_currency` | `id`, `client_name`, `manager_name`, `status`, `created_at`, `updated_at` |
| Milestone | `project`, `name`, `description`, `due_date` | `id`, `project_name`, `status`, `completed_at`, `created_at`, `updated_at` |
| Sprint | `project`, `name`, `goal`, `start_date`, `end_date` | `id`, `project_name`, `status`, `created_at`, `updated_at` |
| Task | `project`, `milestone`, `sprint`, `title`, `description`, `assignee`, `estimate_hours`, `priority`, `due_date` | `id`, `project_name`, `assignee_name`, `status`, `completed_at`, `created_at`, `updated_at` |
| Task labels | `name`, `color` (`#RRGGBB`) | `id`, timestamps |
| Task attachment | multipart `task`, `file` | `id`, `file_name`, `uploaded_by`, `created_at` |
| Task comment | `task`, `body` | `id`, `author`, `author_name`, `created_at`, `updated_at` |
| Time entry | `task`, `work_date`, `hours`, `description`, `is_billable` | `id`, `employee`, `employee_number`, `employee_name`, `task_title`, `project_name`, `hourly_cost_snapshot`, `hourly_cost_currency_snapshot`, `status`, `submitted_at`, `decided_at`, `approver`, `approver_name`, `decision_note`, `created_at`, `updated_at` |
| Time submission | `period_type`, `period_start`, `period_end`, `entries` (ID array) | `id`, `employee`, `employee_number`, `status`, `submitted_at`, `decided_at`, `approver`, `approver_name`, `decision_note`, `created_at` |
| Resource allocation | `project`, `employee`, `role`, `allocation_percent`, `start_date`, `end_date` | `id`, `project_name`, `employee_name`, `created_at`, `updated_at` |
| Employee hourly cost | Finance/HR/Admin only: `employee`, `hourly_cost`, `currency`, `effective_from`, `effective_to` | `id`, `employee_number`, `employee_name`, timestamps |
| Bug | `project`, optional `task`, `title`, `description`, reproduction/expected/actual behavior, `severity`, `assignee` | `id`, `reporter`, names, `status`, `resolved_at`, timestamps |
| Release note | `project`, `version`, `title`, `content`, `release_date`, `is_published` | `id`, timestamps |
| Wiki page | `project`, `title`, `slug`, `content` (Markdown/text) | `id`, timestamps |
| Project document | multipart `project`, `title`, `description`, `file`, `client_visible` | `id`, `file_name`, `uploaded_by`, `created_at` |

Project states: `planned`, `active`, `on_hold`, `completed`, `cancelled`; milestone states: `planned`, `in_progress`, `completed`, `blocked`; sprint states: `planned`, `active`, `completed`, `cancelled`. Priorities: `low`, `medium`, `high`, `urgent`. Time entry states: `draft`, `submitted`, `approved`, `rejected`. Submit and decision actions accept an empty object or `{"decision_note": "..."}` respectively; approve/reject use the latter payload.

Bug severities are `low`, `medium`, `high`, `critical`; statuses are `open`, `triaged`, `in_progress`, `fixed`, `verified`, `closed`, `wont_fix`. Bug status changes use `POST /bugs/{id}/status/` with a `status` field. Task estimates, project budgets, rates, hours, and allocation percentages are decimal values.

## Phase 4 CRM endpoints

All routes in this section are relative to `/api/v1/crm/`.

| Area | Endpoints |
|---|---|
| Leads | `/leads/`, `/leads/{id}/qualify/` |
| Contacts | `/contacts/` |
| Deals & Pipeline | `/deals/`, `/deals/{id}/stage/`, `/deals/pipeline-summary/` |
| Activities | `/activities/`, `/activities/{id}/complete/` |

Access to CRM endpoints is restricted to users with `Sales` or `Admin` roles (or superusers).

- **Leads**: Supports filtering by `status`, `source`, and `assigned_to`, and searching across company name, contact person, email, and phone. `POST /leads/{id}/qualify/` updates the lead status to `qualified` and optionally creates an opportunity `Deal` via `{"create_deal": true, "deal_title": "..."}`.
- **Contacts**: CRUD for customer contact records with search across first name, last name, organization, email, and phone.
- **Deals**: Sales pipeline tracking. Stage changes use `POST /deals/{id}/stage/` with `{"stage": "qualified|proposal|won|lost", "lost_reason": "...", "probability": 0-100}`. `GET /deals/pipeline-summary/` provides aggregated count and expected value totals per stage.
- **Activities**: Logs calls, meetings, emails, notes, and tasks linked to leads, contacts, or deals. `POST /activities/{id}/complete/` marks an activity completed with timestamp and actor tracking.

