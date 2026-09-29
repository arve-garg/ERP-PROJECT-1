# DevERP Progress Tracker

Tracking implementation progress across DevERP phases and delivery slices.

## Previous Phases (Completed)
- [x] **Phase 1: Core Platform Foundation** - Custom user, role-based access control, audit logging, in-app notifications, company settings, saved filters, activity feed, global search, auth + TOTP 2FA, React responsive app shell.
- [x] **Phase 2: Human Resources (HR)** - Departments, designations, employee profiles, emergency contacts, employee documents, attendance check-in/out & monthly summary, leave types, balances, accrual command (`accrue_leave_balances`), leave requests & approvals, holiday calendar.
- [x] **Phase 3: Projects & Delivery** - Clients, projects (budget, currencies, manager, status workflow), milestones, tasks (kanban, status transitions, labels, comments, attachments), sprints with backlog & burndown, timesheets (entries, submissions, approvals), resource allocations & capacity, bug tracking, release notes, project documents & wiki, employee hourly cost snapshots.

---

## Remaining Slices (Phases 4-8)

### Phase 4: CRM & Finance
- [x] **Slice 4a: CRM** - Leads, contacts, deals pipeline as Kanban (new, qualified, proposal, won, lost), CRM activities/notes, follow-up dates with due/overdue indicators.
- [ ] **Slice 4b: Quotes & Deal Conversion** - Quotes with line items, tax, discounts, PDF generation via WeasyPrint, deal-won conversion into Client + Project.
- [ ] **Slice 4c: Finance Core & Invoicing from Time** - Finance app setup, project/role billing rates, sequential invoice generation from approved billable un-invoiced time entries or milestones, double-invoicing prevention in atomic transaction.
- [ ] **Slice 4d: Payments, Credit Notes & Invoice PDF** - Manual payment recording with invoice allocation, credit notes, invoice PDF rendering via WeasyPrint.
- [ ] **Slice 4e: Recurring Invoices & Reminders** - Recurring invoice schedules, automated overdue reminders via django-q2 scheduled tasks.

### Phase 5: Payroll & Recruitment
- [ ] **Slice 5a: Payroll** - Salary structures, allowances, deductions, taxes, monthly payroll runs with approval lock, PDF payslips, employee-scoped view.
- [ ] **Slice 5b: Recruitment** - Job postings, applicant pipeline kanban (applied, screened, interview, offer, hired, rejected), resume upload, interview scheduling and notes, offers.

### Phase 6: Expenses, Accounting & Profitability
- [ ] **Slice 6a: Expenses & Vendor Bills** - Expense claims with receipt uploads and approvals, vendor management, vendor bills.
- [ ] **Slice 6b: Double-Entry Ledger & Financial Statements** - Chart of accounts, double-entry ledger journal entries, trial balance, profit & loss statement, balance sheet.
- [ ] **Slice 6c: Tax & Project Profitability** - GST/VAT tax summary report, project profitability calculation (revenue minus employee hourly cost from time entries minus expenses).

### Phase 7: Support, Client Portal & IT Assets
- [ ] **Slice 7a: Helpdesk & Support** - Support tickets with priorities, categories, assignees, canned responses, public replies vs internal notes, SLA timers with breach flags.
- [ ] **Slice 7b: Knowledge Base & Client Portal** - Public/internal knowledge base articles & categories with search, client portal view (scoped to client's own tickets, invoices, and projects).
- [ ] **Slice 7c: Assets & IT Licences** - Asset register (hardware devices, assignment history), software licenses and seats, subscription renewals with 30-day alerts.

### Phase 8: Analytics, Hardening & Final Deliverables
- [ ] **Slice 8a: Executive Dashboard** - High-level KPIs (revenue, receivables, utilization, headcount, pipeline health) with chart & data table fallbacks.
- [ ] **Slice 8b: Analytics & ML Risk Models** - Scikit-learn models for attrition risk and project delay risk scores with plain-language factor explanations.
- [ ] **Slice 8c: Report Exports** - Scheduled and on-demand report exports to PDF and Excel (openpyxl).
- [ ] **Slice 8d: Synthetic Demo Data** - Management command `seed_demo_data` populating realistic synthetic company dataset (~60 employees, 2 years of history).
- [ ] **Slice 8e: Cleanup, Accessibility, ERD & Documentation** - Split oversized legacy files (`hr-page.tsx`, `projects-page.tsx`, `projects/views.py`), accessibility audit, comprehensive `docs/ERD.md` with Mermaid diagram, final `README.md`.

---

## Decisions
- Backend runs with Django 5.2, DRF, django-q2 ORM broker, whitenoise.
- Development database is SQLite; production uses PostgreSQL configured via `DATABASE_URL`.
- Money amounts are stored as `Decimal` (max digits 14, decimal places 2) in base currency (`settings.BASE_CURRENCY`, default USD).
- Legacy oversized files are intentionally kept intact until Slice 8e to minimize merge and regression risks during feature delivery.
- All new features will be built as modular files under dedicated directories (`backend/apps/<module>/` and `frontend/src/features/<module>/`).

## Known Gaps
- `TimeEntry` records internal employee hourly cost snapshot, but lacks client billing rate (to be resolved in Slice 4c).
- `docs/ERD.md` does not exist yet (to be created in Slice 8e).
- Legacy oversized files:
  - `frontend/src/features/hr/hr-page.tsx` (~74 KB)
  - `frontend/src/features/projects/projects-page.tsx` (~52 KB)
  - `backend/apps/projects/views.py` (~50 KB)

## Needs Human
*(None at present. All current dependencies, linters, tests, and builds run green locally on Python 3.14 + Node 20).*
