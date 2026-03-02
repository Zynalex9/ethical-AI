# Ethical AI Platform — Complete Developer & AI-Agent Documentation

## 1) What This Platform Does

The platform operationalizes ethical AI checks across four principles:

1. **Fairness**
   - Group fairness metrics (demographic parity, equalized odds, disparate impact, etc.).
2. **Transparency**
   - Explainability artifacts (feature importance, model-card style outputs).
3. **Privacy**
   - PII checks + anonymization checks (k-anonymity, l-diversity).
4. **Accountability**
   - Experiment/audit trace logging (MLflow + internal audit logs).

It supports both:
- **manual validation configuration**, and
- **template-driven validation presets**.

---

## 2) High-Level Architecture

## 2.1 Runtime Components

- **Frontend**: React + TypeScript + Vite + MUI + React Query
- **Backend API**: FastAPI (async SQLAlchemy)
- **Database**: PostgreSQL
- **Async worker**: Celery worker
- **Broker/result backend**: Redis
- **Experiment tracking/artifacts**: MLflow (SQLite-backed by default, artifacts on disk)

## 2.2 Request/Execution Topology

1. Frontend calls backend `/api/v1/*` endpoints.
2. Simple operations run inline (CRUD, metadata reads).
3. Long-running validations are queued with Celery (`/validate/all`).
4. Frontend polls task status (`/validate/task/{task_id}`).
5. Final suite results are fetched (`/validate/suite/{suite_id}/results`).

---

## 3) Monorepo Structure

```text
BS/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app bootstrap + startup seeding
│   │   ├── config.py                # Pydantic settings, env loading, path normalization
│   │   ├── database.py              # Async engine/session lifecycle
│   │   ├── celery_app.py            # Celery app + queue config
│   │   ├── models/                  # ORM models
│   │   ├── routers/                 # API route handlers
│   │   ├── services/                # Domain/business logic
│   │   ├── tasks/validation_tasks.py# Celery validation orchestration + validators
│   │   └── validators/              # Fairness, transparency, privacy, accountability engines
│   ├── alembic/versions/            # DB migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Route map
│   │   ├── services/api.ts          # Axios API client + endpoint wrappers
│   │   ├── contexts/AuthContext.tsx # Auth state/session bootstrap
│   │   ├── layouts/MainLayout.tsx   # App shell + sidebar
│   │   └── pages/                   # Feature pages
├── docker-compose.yml               # PostgreSQL service
└── DOCUMENTATION.md                 # This file
```

---

## 4) Backend: Core Logic & Responsibilities

## 4.1 App Startup (`backend/app/main.py`)

Startup lifecycle does:
1. initialize DB tables/session engine,
2. auto-seed domain templates via internal `_seed_templates` helper,
3. register all routers under `settings.api_prefix` (`/api/v1` by default).

Important behavior:
- Template seeding runs at startup and is wrapped in try/except.
- If seeding fails, app still boots but templates may be empty.

## 4.2 Configuration (`backend/app/config.py`)

Settings are loaded from env vars (and `.env` if present), including:
- DB URL,
- Redis/Celery URLs,
- JWT config,
- CORS,
- upload paths,
- MLflow URI + artifact location.

It normalizes relative paths to absolute paths based on backend directory.

## 4.3 Data Model Snapshot

### Users (`models/user.py`)
- Role-based users: `user`, `admin`, `auditor`.
- Own projects and generate audit logs.

### Projects (`models/project.py`)
- Root entity for model/dataset/requirements.
- Soft-delete with `deleted_at`.

### ML Models (`models/ml_model.py`)
- Metadata + file path + framework type.
- Linked to project.

### Datasets (`models/dataset.py`)
- Metadata + schema (`columns`) + sensitive attributes + target column + profile data.
- Linked to project.

### Templates (`models/template.py`)
- Domain templates with `template_id`, `domain`, `rules`, `version`, `is_active`.
- Used to generate project requirements and validation presets.

### Requirements (`models/requirement.py`)
- Ethical requirements per project with principle + JSON rule specification.
- Optional `based_on_template_id` for traceability to template source.
- Includes elicitation fields: `elicited_automatically`, reason, confidence.

### Validations (`models/validation.py`)
- Individual validation runs and metric results.
- Tracks status/progress/celery task/MLflow run id.
- Phase-3 traceability fields include behavior patterns and affected groups.

### Validation Suites (`models/validation_suite.py`)
- Orchestrates multi-principle validation bundle execution.
- Links fairness/transparency/privacy validation IDs and overall status.

### Audit Logs (`models/audit_log.py`)
- Immutable activity events by action/resource type.

---

## 5) Backend Routers (API Surface)

All routers are mounted at `/api/v1`.

## 5.1 Auth (`/auth`)
- `POST /register`
- `POST /login`
- `POST /refresh`
- `GET /me`

## 5.2 Projects (`/projects`)
- `GET /`
- `POST /`
- `GET /{project_id}`
- `PUT /{project_id}`
- `DELETE /{project_id}`

## 5.3 Models (`/models`)
- `POST /upload`
- `GET /project/{project_id}`
- `GET /{model_id}`
- `DELETE /{model_id}`

## 5.4 Datasets (`/datasets`)
- `POST /upload`
- `GET /project/{project_id}`
- `GET /{dataset_id}`
- `GET /{dataset_id}/profile`
- `DELETE /{dataset_id}`
- `POST /project/{project_id}/load-benchmark`
- `GET /benchmark/available`

## 5.5 Requirements (`/requirements`)
- `POST /elicit-from-dataset`
- `POST /elicit-from-model`
- `POST /accept-elicited`
- `GET /project/{project_id}`
- `POST /project/{project_id}`
- `PUT /{requirement_id}`
- `DELETE /{requirement_id}`

## 5.6 Templates (`/templates`)
- `GET /` (supports domain/principle/search filters)
- `GET /{tpl_id}`
- `POST /` (create template)
- `DELETE /{tpl_id}`
- `POST /apply-to-project`
- `POST /{tpl_id}/customize`
- `POST /seed-defaults` (admin-only)

## 5.7 Validation (`/validate`)
- `POST /fairness`
- `POST /transparency`
- `POST /privacy`
- `GET /{validation_id}`
- `GET /history/{project_id}`
- `POST /all` (queue full suite)
- `GET /task/{task_id}`
- `GET /suite/{suite_id}/results`
- `GET /suite/{suite_id}/privacy-details`
- `GET /suite/{suite_id}/transparency-details`

## 5.8 Traceability (`/traceability`)
- `GET /project/{project_id}/matrix`
- `GET /requirement/{requirement_id}/history`
- `GET /validation/{validation_id}/root-cause`
- `GET /dataset/{dataset_id}/impact`

## 5.9 Reports (`/reports`)
- `GET /validation/{validation_suite_id}`
- `GET /validation/{validation_suite_id}/pdf`
- `GET /project/{project_id}/compliance`
- `GET /project/{project_id}/compliance/pdf`
- `POST /custom`

## 5.10 Audit (`/audit`)
- `GET /`
- `GET /summary`

---

## 6) Template System: How It Actually Works

## 6.1 Seed Catalog

`backend/app/routers/templates.py` defines built-in domain templates:
- `GEN-FAIRNESS`, `GEN-TRANSPARENCY`, `GEN-PRIVACY`
- `ETH1`..`ETH6` (finance, healthcare, criminal justice, employment, GDPR, education)

Each template includes:
- `principles` list,
- legal reference,
- `items[]` with metric/operator/value/principle/description.

## 6.2 Seeding Strategy

- Startup auto-seeding is triggered in app lifespan.
- `_seed_templates` is upsert-style:
  - creates missing template rows,
  - updates existing rows and increments version when content changes.

## 6.3 Template Application

`POST /templates/apply-to-project`:
- loads template,
- optionally applies custom rule overrides/add/remove,
- creates requirement rows under target project,
- links requirements via `based_on_template_id`.

---

## 7) Validation System: End-to-End Logic

## 7.1 Execution Modes

1. **Single validation endpoints** (`/fairness`, `/transparency`, `/privacy`) for direct checks.
2. **Suite endpoint** (`/validate/all`) for orchestrated async execution with progress polling.

## 7.2 Why Celery Is Required

Suite validations can be long-running (model load + inference + metrics + artifacts). Celery prevents HTTP request timeout and enables progress tracking.

## 7.3 Suite Lifecycle

1. Frontend sends `/validate/all` payload.
2. Backend creates `ValidationSuite` and enqueues Celery task.
3. Worker performs validations sequentially, updating status/progress.
4. Frontend polls `/validate/task/{task_id}`.
5. On success/failure, frontend fetches `/validate/suite/{suite_id}/results`.

## 7.4 Validation Inputs

`runAll` payload includes:
- `model_id`, `dataset_id`
- `selected_validations` (subset support)
- `fairness_config` (sensitive feature, target, selected metrics, thresholds)
- `transparency_config` (target, sample size)
- `privacy_config` (checks, k/l values, quasi-identifiers, sensitive attribute)
- `requirement_ids` (optional link for requirement-driven validation)

## 7.5 Requirement-Aware Threshold Flow

In validation page:
- user can select relevant requirements,
- thresholds can be imported from requirement `specification.rules`,
- run payload still carries explicit effective thresholds/checks.

## 7.6 Template Preset in Validation UI (Current Behavior)

Validation flow now supports template preset selection:
- selecting a template auto-derives:
  - which validations run,
  - fairness metric selection + thresholds,
  - privacy checks + k/l defaults.
- user still selects model/dataset and required dataset columns.

This is implemented in frontend validation page logic (`applyTemplatePreset` + preset lock behavior).

---

## 8) Requirement Elicitation Logic (Cognitive RE)

Service: `backend/app/services/requirement_elicitor.py`

### Dataset-driven elicitation
- Detect PII-like columns from names.
- Detect sensitive-attribute imbalance.
- Detect high-dimensionality for explainability recommendation.
- Always include accountability recommendation.

### Model+dataset elicitation
- Uses model predictions to infer fairness risk signals.
- Adds fairness/transparency/accountability suggestions where patterns indicate risk.

Important: suggestions are not persisted until accepted via API.

---

## 9) Traceability & Reporting

## 9.1 Traceability Matrix

`TraceabilityService` builds requirement-to-validation linkage:
- requirement info,
- model + dataset context,
- validation/result pass/fail state,
- root-cause oriented metadata.

## 9.2 Report Generation

`ReportGenerator` composes:
- suite-level report (fairness/transparency/privacy + recommendations),
- compliance report with traceability summary,
- downloadable PDF variants.

---

## 10) Frontend Application Map

## 10.1 App Shell & Session
- Routing in `frontend/src/App.tsx`
- Auth session state in `frontend/src/contexts/AuthContext.tsx`
- Main navigation layout in `frontend/src/layouts/MainLayout.tsx`

## 10.2 Key Pages
- `DashboardPage`
- `ProjectsPage` (scratch/template project creation)
- `ProjectDetailPage` (models, datasets, requirements, validations, traceability)
- `ValidationPage` (wizard + async progress + results)
- `TemplateBrowserPage` / `TemplatesPage`
- `RequirementElicitationPage`
- `TraceabilityPage`
- `ReportViewerPage`
- `AuditLogPage`

## 10.3 Frontend Data Layer

`frontend/src/services/api.ts`:
- central axios client,
- token injection request interceptor,
- token refresh flow on 401,
- typed endpoint wrapper groups (`authApi`, `projectsApi`, `validationApi`, etc.).

---

## 11) End-to-End Use Cases

## Use Case A: Template-based Project Bootstrap
1. User opens Projects → Create Project.
2. Selects “Start with template”.
3. Chooses domain template.
4. Project is created and template requirements are applied.
5. Requirements show source template linkage in project detail.

## Use Case B: Manual Validation Run
1. User opens project → Run Validation.
2. Selects validation types manually.
3. Configures model/dataset/features/checks/thresholds.
4. Optionally links requirements and imports requirement thresholds.
5. Runs suite and watches progress.
6. Reviews result cards + detail pages.

## Use Case C: Template-Preset Validation Run
1. User opens project → Run Validation.
2. Selects template preset.
3. Validation types + metrics/checks/thresholds auto-configure.
4. User picks model/dataset/required columns.
5. Runs validation and reviews outcomes.

## Use Case D: Requirement Elicitation
1. User opens requirement elicitation page.
2. Runs elicitation from dataset and/or model.
3. Reviews suggestions with reason/confidence.
4. Accepts selected suggestions into project requirements.

## Use Case E: Governance/Compliance
1. User runs validations over time.
2. Auditors inspect Audit Log and Traceability matrix.
3. Compliance reports are exported (JSON/PDF style endpoints).

---

## 12) Operational Notes & Constraints

- Validation suite async requires **Redis + Celery worker**.
- On Windows, Celery should use `--pool=solo`.
- Template list emptiness usually indicates:
  - seeding did not run successfully at startup, or
  - backend is connected to a DB without seeded template rows.
- Some old docs reference `venv`; your workspace currently uses `venv-314`.

---

## 13) Complete Startup & Operations Guide (Windows)

This section is intentionally last, as requested.

## 13.1 Prerequisites
- Python 3.11+ (or your project-compatible version)
- Node.js 18+
- Docker Desktop (for PostgreSQL and optionally Redis)
- PowerShell

## 13.2 Database Startup (PostgreSQL)

From repository root:

```powershell
docker-compose up -d postgres
docker-compose ps
```

Expected DB connection defaults:
- Host: `localhost`
- Port: `5432`
- DB: `ethical_ai`
- User: `postgres`
- Password: `postgres`

## 13.3 Redis Startup (for Celery)

```powershell
docker run -d --name ethical-ai-redis -p 6379:6379 redis:7-alpine
```

If already created:
```powershell
docker start ethical-ai-redis
```

## 13.4 Backend Environment Configuration

1. Create backend env file:
```powershell
cd backend
copy .env.example .env
```

2. Ensure `.env` values align with your local services:
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ethical_ai`
- `REDIS_URL=redis://localhost:6379/0`
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/0`

## 13.5 Python Environment + Dependencies

If using existing local env in this repo:
```powershell
cd backend
.\venv-314\Scripts\activate
pip install -r requirements.txt
```

If creating a new one:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 13.6 Database Migrations

```powershell
cd backend
alembic upgrade head
```

## 13.7 Start Backend API

```powershell
cd backend
.\venv-314\Scripts\activate
uvicorn app.main:app --reload
```

Health check:
- `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

## 13.8 Start Celery Worker

In a second terminal:

```powershell
cd backend
.\venv-314\Scripts\activate
celery -A app.celery_app worker --loglevel=info --pool=solo
```

## 13.9 Start Frontend

In a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:
- `http://localhost:5173`

Ensure `frontend/.env` has:
```dotenv
VITE_API_URL=http://localhost:8000/api/v1
```

## 13.10 Minimal Smoke Test

1. Register/login.
2. Create project.
3. Upload model + dataset.
4. Open Run Validation page.
5. Choose template preset or manual validators.
6. Run suite.
7. Confirm progress updates and results appear.
8. Check audit + traceability pages.

## 13.11 Common Failure Modes

### Templates empty
- Check backend startup logs for template seeding line.
- Ensure backend connected to expected DB.
- Restart backend after migrations.

### Task stuck in `PENDING`
- Redis not running, or Celery worker not running/connected.
- Verify worker terminal shows registered task and ready state.

### Auth errors in frontend API calls
- Access token missing/expired.
- Re-login and verify `/auth/me` succeeds.

### Backend cannot connect DB
- Confirm `docker-compose ps` shows postgres healthy.
- Validate `DATABASE_URL` in backend `.env`.

---

## 14) Quick Reference Commands

```powershell
# Postgres
docker-compose up -d postgres

# Redis
docker run -d --name ethical-ai-redis -p 6379:6379 redis:7-alpine

# Backend
cd backend
.\venv-314\Scripts\activate
alembic upgrade head
uvicorn app.main:app --reload

# Celery
cd backend
.\venv-314\Scripts\activate
celery -A app.celery_app worker --loglevel=info --pool=solo

# Frontend
cd frontend
npm install
npm run dev
```

---

## 15) Documentation Maintenance Policy

When code changes, update this file if you modify any of the following:
- route contracts,
- validation flow logic,
- template behavior,
- async execution model,
- startup/runtime requirements.

Treat this file as the implementation index for both humans and AI agents.
