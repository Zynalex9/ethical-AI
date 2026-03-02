# Changelog

All notable changes to the **Ethical AI Requirements Engineering Platform** are documented in this file.

---

## [Phase 7] – Polish, Testing & Documentation

### 7.1 – Improved Error Handling
- Added structured error response format (`error`, `message`, `details`, `timestamp`, `request_id`)
- Created domain exception classes (`AppError`, `NotFoundError`, `AccessDeniedError`, `ValidationError`)
- Added `RequestIdMiddleware` – attaches a UUID to every request
- Created React `ErrorBoundary` component with recovery UI
- Configured smart React Query retry logic (no retry on 4xx except 408/429, max 2 retries, exponential backoff)
- Removed debug `console.log` and debug info cards from production pages

### 7.2 – Improved Performance
- Fixed N+1 query in `list_projects` — replaced per-project COUNT loop with correlated subqueries in a single SELECT
- Fixed double `db.commit()` in `create_project` — replaced with `db.flush()` + single commit
- Added lazy loading / code splitting to all 12 page components via `React.lazy()` + `Suspense`

### 7.3 – Improved User Onboarding
- Created `QuickStartChecklist` component (5-step guide: create project → upload model → upload dataset → elicit requirements → run validation)
- Progress bar auto-tracks completion, auto-hides when all steps are done
- Integrated into Dashboard page

### 7.4 – Improved Documentation
- Created `USER_GUIDE.md` — non-technical guide: concepts, 7-step getting started, understanding results, FAQ
- Created `DEVELOPER_GUIDE.md` — architecture, project structure, how to add validators/templates/endpoints, migrations, coding conventions
- Created in-app `HelpTooltip` component with glossary of 19 ethical AI terms

### 7.5 – Added Testing
- **Backend:** pytest + pytest-asyncio + httpx test suite
  - `test_auth.py` (8 tests) — register, login, profile
  - `test_projects.py` (8 tests) — list, create, get, delete
  - `test_templates.py` (5 tests) — list, seed, create, get
  - `test_services.py` (6 tests) — auth service, middleware helpers
  - `test_health.py` (4 tests) — health, root, request-id, structured errors
- **Frontend:** Vitest + Testing Library + jsdom
  - `ErrorBoundary.test.tsx` (4 tests)
  - `HelpTooltip.test.tsx` (2 tests)
- **CI/CD:** GitHub Actions workflow (`.github/workflows/ci.yml`) with PostgreSQL + Redis services

### 7.6 – Security Improvements
- Added in-memory token-bucket rate limiter (`RateLimitMiddleware`, 100 req/min per IP)
- Created file upload security utilities (`validate_upload_file`, `sanitize_csv_cell`, `safe_filename`)
- Integrated upload security into model and dataset upload endpoints
- Added password complexity validation (uppercase, lowercase, digit, special character)
- Replaced hardcoded `print()` statements with structured logger in `config.py`

### 7.7 – Logging & Monitoring
- Created structured logging system (`JSONFormatter` for production, `ConsoleFormatter` for dev)
- Added `RequestLoggingMiddleware` with per-request timing and status-aware log levels
- Integrated `get_logger()` into all 10 routers (auth, projects, models, datasets, validation, templates, audit, requirements, traceability, reports)
- Added event logging for: user registration/login, model uploads, dataset uploads, validation start/complete/fail

### 7.8 – Deployment Configuration
- Created `docker-compose.prod.yml` — full production stack (postgres, redis, backend, celery, frontend, nginx)
- Created `frontend/Dockerfile.prod` — multi-stage build (node build → nginx serve)
- Created `nginx.conf` — reverse proxy, rate limiting, security headers, SPA fallback
- Created `.env.production` — production environment template
- Created deployment scripts: `scripts/deploy.sh`, `scripts/backup.sh`, `scripts/restore.sh`

### 7.9 – Admin Dashboard
- Created backend `admin` router with admin-only endpoints:
  - `GET /admin/stats` — system-wide statistics
  - `GET /admin/users` — list all users
  - `PATCH /admin/users/:id/role` — change user role
  - `PATCH /admin/users/:id/status` — activate/deactivate user
  - `GET /admin/health` — database, Redis, Celery health checks
  - `GET /admin/activity` — recent platform activity
- Created `AdminDashboardPage.tsx` with stat cards, user management table, health indicators, activity log
- Added admin nav item (visible only to admin users)

### 7.10 – Changelog
- Created this `CHANGELOG.md` documenting all phases

---

## [Phase 6] – Requirement Templates & Domain Adaptation

### Added
- 6 domain-specific ethical requirement templates (Healthcare, Finance, Criminal Justice, Education, Employment, General)
- Template browser UI with domain filtering and search
- Template customisation — apply templates to projects, create custom templates
- Template seeding on application startup

---

## [Phase 5] – Visualization & Reporting

### Added
- SHAP/LIME explainability visualizations (feature importance, waterfall, force plots)
- Privacy validation (PII detection, k-anonymity, l-diversity)
- Accountability validation (audit trail, MLflow logging)
- Comprehensive validation suite (run all principles in one batch)
- PDF report export via html2canvas + jsPDF
- Report viewer page with tabbed sections (fairness, transparency, privacy, accountability)
- Validation suite history and comparison

---

## [Phase 4] – Requirement Traceability Matrix

### Added
- Requirement Traceability Matrix (RTM) — maps requirements to datasets, models, and validation results
- Compliance history tracking per requirement
- Root-cause analysis for failed validations
- Dataset impact analysis
- Traceability visualization page with matrix table and compliance charts

---

## [Phase 3] – Requirement Elicitation (Cognitive RE)

### Added
- Automated requirement elicitation from dataset analysis (detects sensitive attributes, class imbalance, PII)
- Model-aware elicitation (analyses model type, feature importance, prediction patterns)
- Elicitation UI page — interactive requirement suggestions with accept/reject/edit workflow
- Manual requirement creation and management
- Requirement status tracking (draft, accepted, rejected, implemented, validated)

---

## [Phase 2] – Fairness & Transparency Validation

### Added
- Fairness validation engine (Fairlearn integration): demographic parity, equalized odds, disparate impact
- Transparency/explainability engine (SHAP): global and local explanations, model cards
- Validation result storage and history
- Detailed validation result pages (fairness metrics, transparency details)

---

## [Phase 1] – Foundation & Setup

### Added
- FastAPI backend with async SQLAlchemy + PostgreSQL
- React frontend with Material UI, React Router, React Query
- JWT authentication (register, login, refresh, profile)
- Project CRUD with soft delete
- ML model upload (sklearn, TensorFlow, PyTorch, ONNX)
- Dataset upload with CSV profiling
- Audit logging system
- Benchmark dataset seeder (COMPAS, Adult Income, German Credit)
- Docker Compose for local development
- Alembic database migrations
