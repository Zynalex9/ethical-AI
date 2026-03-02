# Developer Guide — Ethical AI Requirements Engineering Platform

> For contributors, researchers, and AI agents who need to extend the platform.

---

## 1. Architecture Overview

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Frontend   │ ──→  │   Backend    │ ──→  │  PostgreSQL  │
│ React 19+TS  │      │   FastAPI    │      │  (async pg)  │
│ Vite + MUI 7 │      │ SQLAlchemy 2 │      └──────────────┘
└──────────────┘      │              │
                      │  Celery      │──→  Redis (broker)
                      │  Workers     │──→  MLflow (tracking)
                      └──────────────┘
```

**Request flow:**
1. React → Axios → `POST /api/v1/validate/all` → FastAPI
2. FastAPI creates DB records, dispatches Celery task, returns `task_id`
3. Celery worker picks up task from Redis, loads model/dataset, runs validators
4. Worker updates PostgreSQL (validation status/results), logs to MLflow
5. Frontend polls `GET /api/v1/validate/task/{task_id}` until complete
6. Frontend fetches `GET /api/v1/validate/suite/{id}/results` for display

---

## 2. Project Structure

```
backend/
  app/
    main.py              ← FastAPI app, lifespan, middleware, router registration
    config.py            ← Pydantic Settings (env-based configuration)
    database.py          ← Async SQLAlchemy engine + session factory
    dependencies.py      ← JWT auth dependency (get_current_user)
    celery_app.py        ← Celery config + task routing

    middleware/           ← Cross-cutting concerns (Phase 6)
      error_handler.py   ← Structured error types + exception handlers
      logging_config.py  ← JSON/Console structured logging
      request_logging.py ← HTTP request logging middleware

    models/              ← SQLAlchemy ORM models
      user.py            ← User + roles (user/admin/auditor)
      project.py         ← Project (soft-delete)
      ml_model.py        ← Uploaded ML model metadata
      dataset.py         ← Uploaded dataset metadata + profile
      requirement.py     ← Ethical requirements + auto-elicitation fields
      validation.py      ← Validation + ValidationResult + traceability fields
      validation_suite.py← Suite orchestrating fairness+transparency+privacy
      audit_log.py       ← Audit trail (18 action types)
      template.py        ← Domain template (rules as JSONB)

    routers/             ← FastAPI routers (API endpoints)
      auth.py            ← register, login, refresh, profile
      projects.py        ← Project CRUD
      models.py          ← Model upload/list/delete
      datasets.py        ← Dataset upload/list/delete/profile/benchmark
      validation.py      ← Run validations, poll status, get results
      requirements.py    ← Requirement CRUD + auto-elicitation
      templates.py       ← Template CRUD + apply/customize + seed
      traceability.py    ← Traceability matrix, compliance history, root-cause
      reports.py         ← Validation/compliance reports + PDF export
      audit.py           ← Audit log list + summary

    schemas/             ← Pydantic request/response schemas
    services/            ← Business logic services
      auth_service.py    ← Password hashing + JWT tokens
      model_loader.py    ← UniversalModelLoader (sklearn/TF/PyTorch/ONNX)
      requirement_elicitor.py ← Auto-generate requirements from data/model
      template_library.py    ← Template query/apply/customize
      traceability_service.py← RTM, compliance history, root-cause analysis
      report_generator.py    ← Report compilation + PDF generation
      dataset_seeder.py      ← Benchmark dataset loading

    tasks/               ← Celery background tasks
      validation_tasks.py← fairness/transparency/privacy validators

    validators/          ← (Reserved for future custom validators)
    datasets/benchmark/  ← Built-in benchmark CSV files
    uploads/             ← User-uploaded models + datasets

frontend/
  src/
    App.tsx              ← Routes, providers, code splitting
    theme.ts             ← MUI dark theme
    main.tsx             ← Entry point

    components/          ← Reusable UI components
      ErrorBoundary.tsx  ← Global error boundary
      QuickStartChecklist.tsx ← Onboarding checklist
      TraceabilityMatrix.tsx  ← RTM table with filters + CSV export
      TemplateCustomizer.tsx  ← Template rule editor
      BenchmarkDatasetLoader.tsx ← Preset dataset loader
      requirements/      ← RequirementCard, RequirementForm
      visualizations/    ← FairnessVisualization, SHAPVisualization,
                           LIMEVisualization, PrivacyVisualization

    contexts/            ← React context providers
      AuthContext.tsx     ← JWT auth state + login/register/logout

    layouts/
      MainLayout.tsx     ← Sidebar navigation + user menu

    pages/               ← Route-level page components (14 pages)
    services/
      api.ts             ← Axios instance + all API modules
      pdf-export.ts      ← Client-side PDF generation

    types/
      index.ts           ← TypeScript interfaces for the full domain
```

---

## 3. How to Add a New Validator

Suppose you want to add a **robustness** validator.

### Backend

1. **Create the validator function** in `backend/app/tasks/validation_tasks.py`:
   ```python
   async def _run_robustness_validation_async(
       validation_id, model_id, dataset_id, config, progress_callback
   ):
       # Load model & dataset
       # Run robustness checks (e.g. adversarial perturbation)
       # Store results via ValidationResult
   ```

2. **Register a Celery task**:
   ```python
   @celery_app.task(bind=True, name="run_robustness_validation")
   def run_robustness_validation_task(self, validation_id, ...):
       loop = asyncio.new_event_loop()
       loop.run_until_complete(_run_robustness_validation_async(...))
   ```

3. **Add an API endpoint** in `backend/app/routers/validation.py`:
   ```python
   @router.post("/validate/robustness")
   async def run_robustness_validation(...):
       ...
   ```

4. **Add validation result types** — update the `EthicalPrinciple` enum if needed.

### Frontend

5. **Add a validator card** in `ValidationPage.tsx` → validators array:
   ```ts
   { id: 'robustness', name: 'Robustness', ... }
   ```

6. **Add config UI** in Step 1 of the wizard.

7. **Add result display** in Step 3 results section.

---

## 4. How to Add a New Template

1. Add a new entry to `DOMAIN_TEMPLATES` in `backend/app/routers/templates.py`:
   ```python
   {
       "template_id": "ETH7",
       "name": "ETH7: Insurance (Underwriting)",
       "description": "...",
       "domain": "insurance",
       "rules": {
           "principles": ["fairness", "transparency"],
           "reference": "...",
           "items": [
               {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.80, ...},
           ]
       }
   }
   ```

2. Restart the backend — templates are auto-seeded at startup.

3. If adding a new `TemplateDomain` value, update `backend/app/models/template.py`:
   ```python
   class TemplateDomain(str, PyEnum):
       INSURANCE = "insurance"
       ...
   ```

---

## 5. How to Add a New API Endpoint

1. Choose or create a router file in `backend/app/routers/`.
2. Define your endpoint function with proper typing:
   ```python
   @router.get("/my-endpoint/{id}")
   async def my_endpoint(
       id: UUID,
       db: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       ...
   ```
3. Register the router in `main.py` if new:
   ```python
   app.include_router(my_router.router, prefix=settings.api_prefix)
   ```
4. Add the corresponding API call in `frontend/src/services/api.ts`.
5. Add TypeScript types in `frontend/src/types/index.ts`.

---

## 6. Database Migrations

We use **Alembic** for schema changes:

```bash
cd backend

# Generate a new migration after changing models
alembic revision --autogenerate -m "description of change"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

**Connection**: Alembic reads `DATABASE_URL` from `alembic.ini` or your `.env`.

---

## 7. Testing (Phase 6)

### Backend

```bash
cd backend
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v
```

### Frontend

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom

# Run tests
npx vitest run

# Run in watch mode
npx vitest
```

---

## 8. Environment Variables

All configuration is loaded from `backend/.env`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/ethical_ai` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery broker + result backend |
| `JWT_SECRET_KEY` | (insecure default) | **Must change in production** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `DEBUG` | `false` | Enables verbose error messages |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed frontend origins |
| `UPLOAD_DIR` | `./uploads` | File storage directory |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max upload file size |
| `MLFLOW_TRACKING_URI` | `sqlite:///./mlflow.db` | MLflow backend store |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker URL |

---

## 9. Coding Conventions

- **Backend**: Python 3.10+, type hints on all functions, async/await for DB operations
- **Frontend**: TypeScript strict mode, functional components only, React Query for server state
- **Naming**: snake_case (Python), camelCase (TypeScript), PascalCase (React components)
- **Imports**: Absolute from `app.*` (backend), relative `../` (frontend)
- **Logging**: Use `from app.middleware.logging_config import get_logger; logger = get_logger("module_name")`
- **Errors**: Use `AppError` subclasses (`NotFoundError`, `AccessDeniedError`, `ValidationError`) from `app.middleware.error_handler`

---

## 10. Useful Commands Cheat Sheet

```bash
# ----- Backend -----
cd backend
python -m venv venv-314
venv-314\Scripts\activate          # Windows
source venv-314/bin/activate       # Linux/Mac
pip install -r requirements.txt

uvicorn app.main:app --reload      # Dev server on :8000
celery -A app.celery_app worker --loglevel=info -Q validations  # Worker

# ----- Frontend -----
cd frontend
npm install
npm run dev                         # Dev server on :5173

# ----- Database -----
# Ensure PostgreSQL is running with a database named 'ethical_ai'
cd backend
alembic upgrade head                # Run migrations

# ----- Docker (full stack) -----
docker-compose up --build           # Builds + runs all services
```
