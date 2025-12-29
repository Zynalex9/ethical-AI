Celery Setup Guide for Async Validations
Overview
The validation system uses Celery for running long-running validation tasks asynchronously. This prevents the API from timing out during model validation which can take several minutes.

Architecture
Frontend → API (/api/v1/validate/all) → Celery Task Queue → Celery Worker
                ↓                              ↓
         Returns task_id              Runs validations
                ↓                              ↓
    Poll /api/v1/validate/task/{task_id}   Updates progress
Prerequisites
You need Redis running as the message broker for Celery.

Redis via Docker (Recommended)
# Start Redis container
docker run --name ethical-ai-redis -p 6379:6379 -d redis:7-alpine
# Verify it's running
docker ps | findstr redis

1. Activate Virtual Environment
cd C:\Users\Zain\Desktop\BS\backend
.\venv\Scripts\activate
2. Start Celery Worker
# Windows requires the 'solo' pool (eventlet/gevent don't work well on Windows)
celery -A app.celery_app worker --loglevel=info --pool=solo
Expected Output:

-------------- celery@HOSTNAME v5.x.x
---- **** -----
--- * ***  * -- Windows-10-x.x.x
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         app.celery_app:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 1 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery
[tasks]
  . app.tasks.validation_tasks.run_all_validations_task
[2025-12-29 22:15:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-12-29 22:15:00,000: INFO/MainProcess] celery@HOSTNAME ready.
3. Keep It Running
Keep this terminal window open. Celery worker must be running to process validation tasks.

Environment Configuration
Make sure your 
.env
 file has:

# Redis/Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
Testing the Setup
1. Start All Services
You should have 4 terminals running:

Frontend: npm run dev (port 5173)
Backend: uvicorn app.main:app --reload (port 8000)
Redis: Docker container or Windows service
Celery Worker: celery -A app.celery_app worker --loglevel=info --pool=solo
2. Run a Validation
Go to a project in the frontend
Click "Run Validation"
Fill in the form and submit
You should see a progress screen immediately (not hanging)
The Celery worker terminal will show task execution logs
3. Check Task Status
The frontend polls /api/v1/validate/task/{task_id} to get progress updates.

You can also check manually:

curl http://localhost:8000/api/v1/validate/task/{task_id}
Troubleshooting
Redis Connection Error
Error: Error 10061: No connection could be made

Solution: Make sure Redis is running

# Check if Redis container is running
docker ps
# If not, start it
docker start ethical-ai-redis
# Or create new one
docker run --name ethical-ai-redis -p 6379:6379 -d redis:7-alpine
Celery Import Error
Error: ModuleNotFoundError: No module named 'app.celery_app'

Solution: Make sure you're in the backend directory and venv is activated

Task Not Executing
Symptoms: Task stays in PENDING state forever

Solutions:

Check Celery worker is running and connected
Check Redis is accessible
Look for errors in Celery worker logs
Verify task is registered (should see it in worker startup logs)
Windows-Specific Issues
Error: ValueError: not enough values to unpack

Solution: Use --pool=solo flag (required on Windows)

celery -A app.celery_app worker --loglevel=info --pool=solo
Production Deployment
For production, use a proper process manager:

Option 1: Windows Service
Use NSSM (Non-Sucking Service Manager):

nssm install EthicalAICelery "C:\path\to\venv\Scripts\celery.exe" "-A app.celery_app worker --loglevel=info --pool=solo"
Option 2: Docker Compose
Add to docker-compose.yml:

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  celery-worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0
Monitoring
Flower (Celery Monitoring Tool)
# Install
pip install flower
# Run
celery -A app.celery_app flower
# Access at http://localhost:5555
Flower provides a web UI to monitor:

Active tasks
Task history
Worker status
Task execution times
Quick Reference
Start Everything (Development)
# Terminal 1: Redis
docker start ethical-ai-redis
# Terminal 2: Backend
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload
# Terminal 3: Celery Worker  
cd backend
.\venv\Scripts\activate
celery -A app.celery_app worker --loglevel=info --pool=solo
# Terminal 4: Frontend
cd frontend
npm run dev
Stop Everything
# Stop Celery: Ctrl+C in terminal
# Stop Backend: Ctrl+C in terminal  
# Stop Frontend: Ctrl+C in terminal
# Stop Redis: docker stop ethical-ai-redis