# Get Started

## 1. Clone and enter project

```bash
git clone <your-repo-url>
cd BS
```

## 2. Start PostgreSQL in Docker

```bash
docker-compose up -d postgres
```

Verify DB health:

```bash
docker-compose ps
docker-compose logs -f postgres
```

## 3. Start Redis in Docker (required for Celery)

Default Redis port:

```bash
docker run -d --name redis-ethical-ai -p 6379:6379 redis:latest
```

If `6379` is busy and you want a custom host port (example `5498`):

```bash
docker run -d -p 6379:6379 redis
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

Optional scheduler (for periodic tasks):

```bash
celery -A app.celery_app beat --loglevel=info
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
docker-compose up -d
```

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
docker-compose down
```
