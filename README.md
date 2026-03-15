# Ethical AI Validation Platform

An end-to-end platform for evaluating AI systems against four ethical principles:

- Fairness
- Transparency
- Privacy
- Accountability

The system supports model and dataset uploads, requirement-driven validation suites, async task execution, auditability, and report generation.

## Key Capabilities

- Create projects and manage AI assets (models and datasets).
- Run single validations or full validation suites.
- Execute long-running validation workloads through Celery workers.
- Track run status in near real-time via task polling.
- Persist metric outputs and artifacts for post-run analysis.
- Generate suite-level reports and compliance summaries.

## Architecture

- Frontend: React + TypeScript + Vite + MUI
- Backend API: FastAPI (async)
- ORM: SQLAlchemy async
- Migrations: Alembic
- Database: PostgreSQL
- Queue: Celery + Redis
- Tracking/Artifacts: MLflow

## Repository Structure

```text
BS/
  backend/
    app/
      main.py                 # FastAPI entrypoint
      routers/                # API endpoints
      models/                 # ORM entities
      services/               # Business logic
      tasks/                  # Celery background tasks
      validators/             # Fairness/transparency/privacy engines
    alembic/                  # DB migrations
    requirements.txt
  frontend/
    src/
      pages/
      components/
      services/
  docker-compose.yml          # Local postgres compose
  docker-compose.prod.yml     # Prod-style multi-service compose
  nginx.conf
```

## Runtime Components

- API server: `backend/app/main.py`
- Celery app: `backend/app/celery_app.py`
- Validation tasks: `backend/app/tasks/validation_tasks.py`
- Database migrations: `backend/alembic/versions/`
- Frontend app: `frontend/src/`

## Validation Lifecycle

1. User starts validation from frontend.
2. Backend creates `Validation` / `ValidationSuite` records.
3. Backend queues Celery task(s).
4. Worker runs validators and writes progress/results.
5. Frontend polls task state and loads suite details.

## Important Behavior Notes

- Fairness expects binary targets (`0/1`) for the classification metrics currently implemented.
- Transparency can be skipped when no target column is provided.
- Validation error fields are stored as `TEXT` and error handling now rolls back failed sessions safely.

## Local Run Modes

- Minimal local mode:
  - PostgreSQL in Docker
  - Redis in Docker
  - Backend + Celery + Frontend on host
- Container-heavy mode:
  - Use `docker-compose.prod.yml` for a fuller stack (postgres, redis, backend, worker, frontend, nginx)

## Redis/Celery Requirement

Celery requires Redis broker/backend.

Default setup:

```bash
docker compose up -d redis
```

If you use a custom host port (for example `5498`):

```bash
$env:REDIS_HOST_PORT=5498
docker compose up -d --force-recreate redis
```

Then set backend env values accordingly:

```env
REDIS_URL=redis://localhost:5498/0
CELERY_BROKER_URL=redis://localhost:5498/0
CELERY_RESULT_BACKEND=redis://localhost:5498/0
```

## API and UI Endpoints

- Backend docs: `http://localhost:8000/docs`
- Frontend dev UI: `http://localhost:5173`

## Troubleshooting

- Celery task stuck in pending:
  - verify Redis container is running and reachable
  - verify `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`
- Migration issues:
  - run `alembic current` and `alembic upgrade head`
- DB connection failures:
  - check `docker-compose ps` and postgres health

## Quick Navigation

- Detailed setup and run commands: `Get Started.md`
- Client pull-and-run Docker guide: `Client Deployment.md`
