# Celery Worker Setup

This document explains how to run the Celery worker for background task processing.

## Prerequisites

- Redis server running on `localhost:6379` (or configured in `.env`)
- PostgreSQL database running
- Python virtual environment activated

## Starting Redis (if not running)

### Windows
```powershell
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install Redis for Windows from:
# https://github.com/microsoftarchive/redis/releases
```

### Linux/Mac
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install via package manager
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis                  # macOS
```

## Running the Celery Worker

### Development Mode

Open a **new terminal** (keep the FastAPI server running in another terminal):

```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Start Celery worker
celery -A app.celery_app worker --loglevel=info --pool=solo
```

**Note:** On Windows, use `--pool=solo` to avoid multiprocessing issues.

### Production Mode

```bash
# Linux/Mac
celery -A app.celery_app worker --loglevel=info --concurrency=4

# With autoreload for development
celery -A app.celery_app worker --loglevel=info --pool=solo --autoreload
```

## Monitoring Tasks

### Flower (Web-based monitoring)

Install Flower:
```bash
pip install flower
```

Run Flower:
```bash
celery -A app.celery_app flower
```

Access at: http://localhost:5555

### Command Line Monitoring

```bash
# View active tasks
celery -A app.celery_app inspect active

# View registered tasks
celery -A app.celery_app inspect registered

# View worker stats
celery -A app.celery_app inspect stats
```

## Testing the Setup

1. Start Redis
2. Start FastAPI server: `uvicorn app.main:app --reload`
3. Start Celery worker: `celery -A app.celery_app worker --loglevel=info --pool=solo`
4. Upload a model and dataset via API
5. Trigger validation suite: `POST /api/v1/validate/all`
6. Check task status: `GET /api/v1/validate/task/{task_id}`

## Troubleshooting

### "No module named 'app.celery_app'"
- Make sure you're in the `backend` directory
- Check that `app/celery_app.py` exists

### "Cannot connect to Redis"
- Verify Redis is running: `redis-cli ping` (should return "PONG")
- Check Redis URL in `.env` file

### "Task timeout"
- Increase `task_time_limit` in `app/celery_app.py`
- Check model/dataset file sizes

### Windows-specific issues
- Always use `--pool=solo` on Windows
- If you get "Access Denied" errors, run terminal as Administrator

## Task Queues

The system uses a single queue named `validations` for all validation tasks:
- `run_fairness_validation_task`
- `run_transparency_validation_task`
- `run_privacy_validation_task`
- `run_all_validations_task`

## Environment Variables

Add to your `.env` file:

```env
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# MLflow Configuration
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_EXPERIMENT_NAME=ethical-ai-validations
```
