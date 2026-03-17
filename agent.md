# agent.md — Ethical AI Validation Platform Context Document

> This document is intended to give an AI agent (or any developer) immediate, full context of the entire project without needing to read all source files.

---

## 1. General Project Overview

The **Ethical AI Validation Platform** is an end-to-end system for auditing AI/ML models against four core ethical principles:

| Principle | Description |
|---|---|
| **Fairness** | Ensures model predictions do not discriminate across demographic groups |
| **Transparency** | Provides human-readable explanations of how a model makes decisions |
| **Privacy** | Detects PII and enforces anonymisation standards on datasets |
| **Accountability** | Maintains immutable audit trails and MLflow experiment logs for compliance |

**Key capabilities:**
- Upload and manage ML models and datasets per project
- Configure requirement-driven validation suites via domain templates
- Execute long-running validations asynchronously via Celery workers
- Track validation progress in real time (frontend polls)
- Persist metric outputs and visualisation artifacts via MLflow
- Generate suite-level compliance reports (PDF via jsPDF)
- Audit log, traceability matrix, remediation suggestions, and notification system

---

## 2. Tech Stack

### Backend
| Category | Library / Framework | Version (from `requirements.txt`) |
|---|---|---|
| API Framework | FastAPI | `>=0.115.0` |
| ASGI Server | Uvicorn (standard) | `>=0.32.0` |
| ORM | SQLAlchemy (asyncio) | `>=2.0.35` |
| Async DB Driver | asyncpg | `>=0.30.0` |
| Sync Driver (Alembic) | psycopg2-binary | `>=2.9.9` |
| DB Migrations | Alembic | `>=1.14.0` |
| Auth | python-jose, passlib[bcrypt] | `>=3.3.0`, `==1.7.4` |
| Settings / Validation | Pydantic v2, pydantic-settings | `>=2.9.0` |
| Task Queue | Celery[redis] | `>=5.6.0` |
| Message Broker / Backend | Redis | `>=5.2.0` |
| **Fairness** | **fairlearn** | **`>=0.11.0`** |
| Data science | pandas, numpy, scikit-learn, scipy | `>=2.2.3`, `>=2.0.0`, `>=1.6.0`, `>=1.16.1` |
| Visualisation | matplotlib, seaborn | `>=3.9.0`, `>=0.13.2` |
| **Explainability** | **SHAP** | **`>=0.46.0`** |
| **Explainability (local)** | **LIME** | **`>=0.2.0.1`** |
| **Privacy / Differential Privacy** | **diffprivlib** | **`>=0.6.5`** |
| Experiment Tracking | MLflow | `>=2.16.0` |
| Model Inference | onnxruntime | `>=1.20.1` |
| Async file I/O | aiofiles | `>=24.1.0` |

### Frontend
| Category | Library | Version |
|---|---|---|
| UI Framework | React | `^19.2.0` |
| Language | TypeScript | `~5.9.3` |
| Build Tool | Vite | `^7.2.4` |
| Component Library | MUI (Material UI) | `^7.3.6` |
| State / Data Fetching | TanStack React Query | `^5.90.12` |
| HTTP Client | axios | `^1.13.2` |
| Forms | react-hook-form | `^7.69.0` |
| Routing | react-router-dom | `^7.11.0` |
| Charts | recharts | `^3.6.0` |
| Flow Diagrams | reactflow | `^11.11.4` |
| PDF Export | jsPDF + html2canvas | `^4.2.0` |
| Testing | Vitest + Testing Library | `^3.2.0` |

### Infrastructure
| Component | Technology |
|---|---|
| Database | PostgreSQL |
| Reverse Proxy | Nginx |
| Containerisation | Docker / Docker Compose |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│   React 19 + TypeScript + Vite + MUI                        │
│   http://localhost:5173  (dev)                               │
└───────────────────┬──────────────────────────────────────────┘
                    │ HTTP / REST (axios)
                    ▼
┌──────────────────────────────────────────────────────────────┐
│                     NGINX (prod)                             │
│   Reverse proxy → /api/* to backend, /* to frontend         │
└───────────────────┬──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND  (port 8000)                    │
│  app/main.py — registers 13 routers under /api/v1           │
│  Middleware: CORS, RateLimit(100 req/min), RequestLogging,   │
│              RequestId, ErrorHandler                         │
│                                                              │
│  Routers:                                                    │
│   auth, projects, models, datasets, validation,              │
│   templates, audit, requirements, traceability,              │
│   reports, admin, notifications, remediation                 │
└───────┬───────────────────────────┬──────────────────────────┘
        │ SQLAlchemy async          │ Celery task dispatch
        ▼                           ▼
┌───────────────┐          ┌─────────────────────────┐
│  PostgreSQL   │          │   CELERY WORKERS        │
│  (via asyncpg)│          │  broker: Redis           │
│               │          │  backend: Redis          │
│  ORM Models:  │          │                         │
│  User, Project│          │  Tasks:                 │
│  Dataset,     │          │  run_fairness_validation│
│  MLModel,     │          │  run_transparency_valid │
│  Validation,  │          │  run_privacy_validation │
│  ValSuite,    │          │  run_accountability_val │
│  Requirement, │          │  run_suite_validation   │
│  AuditLog,    │          └───────────┬─────────────┘
│  Notification,│                      │ MLflow logging
│  Remediation  │                      ▼
└───────────────┘          ┌─────────────────────────┐
                           │   MLflow Tracking       │
                           │   (SQLite or remote)    │
                           │   Artifacts, metrics,   │
                           │   model cards stored    │
                           └─────────────────────────┘
```

**Data flow summary:**
1. Frontend authenticates (JWT) and makes REST calls to FastAPI.
2. FastAPI persists records in PostgreSQL and queues Celery tasks.
3. Celery workers execute the validators, write results back to PostgreSQL, and log artifacts to MLflow.
4. Frontend polls task state and loads completed validation details.

**Deployment modes:**
- **Local minimal:** PostgreSQL + Redis in Docker; backend, Celery worker, frontend run on host.
- **Full container:** `docker-compose.prod.yml` runs postgres, redis, backend, worker, frontend, nginx.

---

## 4. Types of Validations

### Validation 1 — Fairness (`fairness_validator.py`)
Uses the **Fairlearn** library (`MetricFrame`) to compare model predictions across demographic groups.

**Requires:** binary target labels (0/1), a sensitive feature column, and model predictions.

| Metric | Description | Default Threshold |
|---|---|---|
| `demographic_parity_ratio` | `min(selection_rate) / max(selection_rate)` across groups | `≥ 0.8` (80% rule) |
| `demographic_parity_difference` | `max(selection_rate) − min(selection_rate)` | `≤ 0.1` |
| `equalized_odds_ratio` | Combined TPR+FPR ratio across groups | `≥ 0.8` |
| `equalized_odds_difference` | Combined TPR+FPR max difference | `≤ 0.1` |
| `equal_opportunity_difference` | Max difference in TPR (True Positive Rate) | `≤ 0.05` |
| `disparate_impact_ratio` | `min_rate / max_rate` of positive predictions | `≥ 0.8` |

**Outputs:**
- Per-metric pass/fail with group-level breakdowns
- Per-group confusion matrices (TP, FP, TN, FN, accuracy, TPR, FPR, TNR, FNR, precision)
- Base64-encoded visualisations: selection-rate bar chart, TPR/FPR comparison chart, confusion matrix heatmaps

**Special mode:** If no target column is provided, predictions are used as both `y_true` and `y_pred` (consistency check mode).

---

### Validation 2 — Transparency / Explainability (`explainability_engine.py`)
Uses **SHAP** (KernelExplainer) and **LIME** (LimeTabularExplainer) to explain model decisions.

**Requires:** a trained model with `predict`/`predict_proba`, training background data, and optionally a target column.

> **Note:** Transparency validation is **skipped** (marked as `CANCELLED`) if no target column is provided, without failing the overall suite.

**Global explanation (SHAP):**
- Computes mean absolute SHAP values across all test samples
- Ranks features by importance
- Stores `shap_summary` (beeswarm), `shap_bar` (mean |SHAP| bar plot), `shap_waterfall` (single instance) as base64 PNG images

**Local explanation (SHAP & LIME):**
- Generates per-instance feature contribution dicts for up to 5 sample predictions
- LIME fits a local linear surrogate model around each prediction
- **Explanation fidelity** score: `1 − mean(|f(x) − g(x)|)` measures how well the LIME surrogate mirrors the original model (closer to 1.0 is better)

**Model card:**
- Auto-generated per Mitchell et al.'s model card framework
- Includes: model type, feature names, performance metrics (accuracy, precision, recall, F1), training/eval data sizes

**Visualisations saved to MLflow** (`feature_importance.json`, `model_card.json`).

---

### Validation 3 — Privacy (`privacy_validator.py`)
Validates privacy standards for datasets. References GDPR, CCPA, and HIPAA.

**Requires:** a pandas DataFrame (the dataset).

| Check | Description |
|---|---|
| **PII Detection** | Scans column names and values using pre-compiled regex patterns for email, phone (US), SSN, credit card, IP address, date of birth, ZIP code, name patterns. Also flags high-cardinality string columns (>90% unique values) as potential identifiers. |
| **k-Anonymity** | Every combination of quasi-identifier values must appear at least `k` times (default k=5). Reports violating groups and distribution. |
| **l-Diversity** | Every equivalence class (defined by quasi-identifiers) must contain at least `l` distinct values of the sensitive attribute (default l=2). |
| **Generalisation suggestions** | For columns failing k-anonymity, suggests binning, rounding, noise addition (numeric) or masking, generalisation, categorisation (string). |

**Additional checks available:**
- `differential_privacy.py` — applies differential privacy noise mechanisms via **diffprivlib**
- `hipaa_checker.py` — HIPAA-specific compliance checks

---

### Validation 4 — Accountability (`accountability_tracker.py`)
Provides audit trail and experiment tracking rather than a "pass/fail" check.

**Integrates with MLflow:**
- Creates/reuses an MLflow experiment (`ethical-ai-validations` by default)
- Starts a named run per validation with tags (model, dataset, requirement, principle, user)
- Logs all numerical metrics via `mlflow.log_metric`
- Saves JSON artifacts (fairness report, feature importance, model cards) via `mlflow.log_dict`
- Ends run with `passed` / `failed` / `error` status tag

**Validation record persistence:**
- Writes `ValidationRecord` objects (in-memory during run, then to PostgreSQL `Validation` + `ValidationResult` tables)
- Model lineage: tracks `ModelVersion` objects with full validation history

**Audit log:** Every validation run appends an `AuditLog` DB record via the `AuditLog` model (`AuditAction.VALIDATION_RUN`).

---

## 5. Web App Flow

### a. Login / Register
- Routes: `LoginPage.tsx` → `POST /api/v1/auth/login` (returns JWT access token)
- `RegisterPage.tsx` → `POST /api/v1/auth/register`
- JWT stored in memory/context; attached as `Authorization: Bearer <token>` on all requests
- `AdminDashboardPage.tsx` accessible to admin-role users only (`GET /api/v1/admin/...`)

---

### b. Create a New Project
- `ProjectsPage.tsx` → `POST /api/v1/projects` with name, description
- **With template:** `TemplateBrowserPage.tsx` lets users browse domain templates (Healthcare, Finance, HR, etc.) seeded automatically on startup from `template_library.py`. Applying a template auto-populates requirements for the project.
- **Without template:** User manually creates requirements via `RequirementElicitationPage.tsx`

---

### c. Upload a Dataset or Load Existing
- **Upload:** `POST /api/v1/datasets/upload` (multipart CSV upload)
  - Stores file in `settings.upload_dir`
  - Creates `Dataset` DB record with metadata (row count, column count, file size)
- **Load server dataset:** `GET /api/v1/datasets` lists available datasets; user selects one
- Dataset seeder (`dataset_seeder.py`) can pre-populate example datasets on the server

---

### d. Add Dataset / Model to Project
- Models uploaded via `POST /api/v1/models/upload` (supports `.pkl`, `.joblib`, `.onnx`, `.h5`, `.pt` via `UniversalModelLoader`)
- `ProjectDetailPage.tsx` provides UI to:
  - Link uploaded datasets to the project
  - Link uploaded models to the project
  - View linked assets, column metadata, and dataset previews

---

### e. Run Validations

#### Starting a single validation
`ValidationPage.tsx` → `POST /api/v1/validations` → creates `Validation` DB record, queues a Celery task, returns `task_id`.

Frontend polls `GET /api/v1/validations/{id}` for status (`PENDING` → `RUNNING` → `COMPLETED` / `FAILED`).

#### Validation Suite
`POST /api/v1/validations/suite` → creates a `ValidationSuite` record and queues all four validations in sequence (or in parallel depending on config). The suite-level status rolls up from individual validation statuses.

#### The four validations in a suite:
| # | Name | Celery Task | Key Input |
|---|---|---|---|
| 1 | Fairness | `run_fairness_validation_task` | sensitive feature column, target column, thresholds |
| 2 | Transparency | `run_transparency_validation_task` | target column (optional), sample size |
| 3 | Privacy | `run_privacy_validation_task` | quasi-identifiers, k, l, sensitive attribute |
| 4 | Accountability | `run_accountability_validation_task` | logs to MLflow, generates audit trail |

---

### f. How Validations Work (Technical Flow)

```
User clicks "Run Validation" in ValidationPage.tsx
         ↓
POST /api/v1/validations  (FastAPI router: validation.py)
         ↓
Create Validation record (status=PENDING) in PostgreSQL
         ↓
Dispatch Celery task (e.g., run_fairness_validation_task.delay(...))
         ↓
Celery Worker picks up task
  1. Set status=RUNNING, progress=10%
  2. Load MLModel from disk (UniversalModelLoader)
  3. Load Dataset CSV from disk (pandas)
  4. Align dataset features to model schema (_align_features_to_model)
  5. Run validator (FairnessValidator / ExplainabilityEngine / PrivacyValidator)
  6. Log metrics & artifacts to MLflow (AccountabilityTracker)
  7. Persist ValidationResult records to PostgreSQL
  8. Set status=COMPLETED, progress=100%
  9. Write AuditLog record
         ↓
Frontend polls GET /api/v1/validations/{id}
         ↓
Displays results in ValidationPage.tsx / TransparencyDetailPage / PrivacyDetailPage
```

**Error handling:** On any exception, the worker rolls back the DB session, sets `status=FAILED` with an error message (truncated to 2000 chars), ends the MLflow run as `error`, and re-raises.

---

## 6. Key File Map

```
backend/
  app/
    main.py                          # FastAPI app, middleware, router registration
    config.py                        # Pydantic settings (env vars)
    database.py                      # SQLAlchemy async engine + session maker
    celery_app.py                    # Celery app configuration
    dependencies.py                  # FastAPI dependency injection (auth, DB)
    routers/
      auth.py                        # JWT login/register
      projects.py                    # Project CRUD
      datasets.py                    # Dataset upload/list/detail
      models.py                      # ML model upload/list
      validation.py                  # Start validations/suites, poll results (LARGEST: 56KB)
      templates.py                   # Domain template browser + seeding (LARGEST: 47KB)
      requirements.py                # Project requirements CRUD
      reports.py                     # Suite-level report generation
      audit.py                       # Audit log viewer
      admin.py                       # Admin dashboard
      notifications.py               # User notifications
      remediation.py                 # Auto-remediation suggestions
      traceability.py                # Requirement-to-validation traceability matrix
    models/                          # SQLAlchemy ORM entities (12 files)
    services/
      model_loader.py                # UniversalModelLoader (pkl/joblib/onnx/h5/pt)
      report_generator.py            # PDF/JSON report generation (33KB)
      requirement_elicitor.py        # AI-assisted requirement elicitation (29KB)
      traceability_service.py        # Traceability matrix logic (29KB)
      template_library.py            # Built-in domain templates
      dataset_seeder.py              # Pre-seeded example datasets
    tasks/
      validation_tasks.py            # All 4 Celery validation tasks (68KB, 1592 lines)
    validators/
      fairness_validator.py          # Fairlearn-based fairness checks
      explainability_engine.py       # SHAP + LIME transparency engine
      privacy_validator.py           # PII, k-anonymity, l-diversity
      differential_privacy.py        # diffprivlib noise mechanisms
      accountability_tracker.py      # MLflow integration + audit trail
      hipaa_checker.py               # HIPAA compliance checks
    templates/                       # Jinja2 / HTML report templates

frontend/src/
  pages/
    LoginPage.tsx / RegisterPage.tsx
    DashboardPage.tsx                # Overview metrics
    ProjectsPage.tsx                 # Project list + create
    ProjectDetailPage.tsx            # Per-project assets, run validations (LARGEST: 62KB)
    ValidationPage.tsx               # Validation runner + results viewer (LARGEST: 112KB)
    TransparencyDetailPage.tsx       # SHAP/LIME results, feature importance charts
    PrivacyDetailPage.tsx            # PII scan, k-anonymity, l-diversity results
    TemplateBrowserPage.tsx          # Domain template library
    RequirementElicitationPage.tsx   # AI-guided requirement creation
    TraceabilityPage.tsx             # Requirement-to-validation matrix
    ReportViewerPage.tsx             # Suite compliance report viewer
    AuditLogPage.tsx                 # Audit trail viewer
    KnowledgeBasePage.tsx            # In-app documentation
    AdminDashboardPage.tsx           # Admin management
  services/                         # axios API call wrappers
  contexts/                         # React context (auth, theme)
  components/                       # Reusable UI components
  theme.ts                          # MUI theme configuration
```

---

## 7. Environment Variables

Key environment variables (see `backend/.env.example`):

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | JWT signing secret |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis connection |
| `MLFLOW_TRACKING_URI` | MLflow backend (default: `sqlite:///mlflow.db`) |
| `MLFLOW_EXPERIMENT_NAME` | MLflow experiment name |
| `UPLOAD_DIR` | Directory for uploaded models/datasets |
| `CORS_ORIGINS` | Allowed frontend origins |
| `DEBUG` | Enable debug mode |

---

## 8. API Endpoints (Summary)

Base prefix: `/api/v1`

| Endpoint | Method | Description |
|---|---|---|
| `/auth/login` | POST | Get JWT token |
| `/auth/register` | POST | Create user account |
| `/projects` | GET/POST | List / create projects |
| `/projects/{id}` | GET/PUT/DELETE | Project detail |
| `/datasets/upload` | POST | Upload CSV dataset |
| `/datasets` | GET | List all datasets |
| `/models/upload` | POST | Upload ML model file |
| `/models` | GET | List all models |
| `/validations` | POST | Start a single validation |
| `/validations/suite` | POST | Start a full validation suite |
| `/validations/{id}` | GET | Poll validation status/results |
| `/templates` | GET | List domain templates |
| `/requirements` | GET/POST | List / create requirements |
| `/reports/{suite_id}` | GET | Get suite compliance report |
| `/audit` | GET | Audit log entries |
| `/traceability/{project_id}` | GET | Traceability matrix |
| `/remediation/{validation_id}` | GET | Auto-remediation suggestions |
| `/notifications` | GET | User notifications |
| `/admin/users` | GET | Admin: list users |
| `/health` | GET | Health check |

---

## 9. Important Behaviour Notes

- **Fairness requires binary targets:** Labels must be `0` or `1`. The system auto-encodes string targets containing keywords like `yes`, `true`, `high`, `approved` → 1, otherwise → 0.
- **Transparency is skipped** (not failed) when no target column is provided.
- **Feature alignment:** `_align_features_to_model` handles schema mismatches between dataset and model — missing features are filled with `0`, extra features are dropped.
- **Celery event loop:** A single persistent asyncio event loop is reused per Celery worker process to avoid asyncpg connection issues.
- **Error truncation:** Validation error messages are truncated to 2000 chars before DB storage.
- **Template seeding:** On every startup, domain templates are auto-seeded via `_seed_templates()` (idempotent).
- **MLflow artifacts:** Reports (`fairness_report.json`, `feature_importance.json`, `model_card.json`) are saved as MLflow artifacts and retrievable from the tracking UI.
