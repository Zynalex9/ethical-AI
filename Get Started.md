# Get Started

## 1. Clone and enter project

```bash
git clone <your-repo-url>
cd BS
```

## 2. Start PostgreSQL + Redis in Docker

```bash
docker compose up -d postgres redis
```

Verify DB health:

```bash
docker compose ps
docker compose logs -f postgres
```

## 3. Redis port options (required for Celery)

Default Redis host port (`6379`):

```bash
docker compose up -d redis
```

If `6379` is busy, set a custom host port (example `5498`) and recreate Redis:

```bash
$env:REDIS_HOST_PORT=5498
docker compose up -d --force-recreate redis
```

If using custom host port, update backend env before running API/worker:

```env
REDIS_URL=redis://localhost:5498/0
CELERY_BROKER_URL=redis://localhost:5498/0
CELERY_RESULT_BACKEND=redis://localhost:5498/0
```

## 4. Backend setup

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Optional: create `.env` from example and edit values

```bash
copy .env.example .env
```

Run migrations:

```bash
alembic upgrade head
```

Run API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 5. Celery worker setup

Open a new terminal:

```bash
cd backend
.venv\\Scripts\\activate
celery -A app.celery_app worker --loglevel=info --pool=solo

```

## 6. Frontend setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

## 7. Access app

- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

## 8. Optional full container stack

Start full local stack:

```bash
docker compose up -d
```

## 9. Optional: Generate a real-world model zoo for testing

This trains multiple model types across benchmark datasets already in this repo
(Adult, Bank Marketing, COMPAS, Diabetes, German Credit) and saves uploadable
`.joblib` files.

```bash
cd backend
.venv\\Scripts\\activate
python scripts/train_real_world_model_zoo.py
```

Output location:

```text
backend/uploads/models/model_zoo/
```

Then upload generated models through the `/models/upload` flow and run validations.

## Common commands

```bash
# create migration
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head

# check running redis container
docker ps

# view celery worker logs (if run in terminal session, check that terminal)
# or if containerized:
docker logs -f redis-ethical-ai

# stop docker services
cd ..
docker compose down
```
