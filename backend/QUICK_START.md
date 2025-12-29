# Quick Start Guide - Ethical AI Backend (MVP)

This guide will get you up and running with the complete backend including background task processing.

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies

```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Setup Environment

```powershell
# Copy example environment file
copy .env.example .env

# Edit .env and update:
# - DATABASE_URL (if using different credentials)
# - JWT_SECRET_KEY (generate with: openssl rand -hex 32)
```

### 3. Start Redis

```powershell
# Using Docker (recommended)
docker run -d -p 6379:6379 --name redis-ethical-ai redis:latest

# Verify Redis is running
docker ps
```

### 4. Setup Database

```powershell
# Create PostgreSQL database
# Using psql:
psql -U postgres
CREATE DATABASE ethical_ai;
\q

# Run migrations
alembic upgrade head
```

### 5. Start Services

You need **3 terminals**:

#### Terminal 1: FastAPI Server
```powershell
.\venv\Scripts\activate
uvicorn app.main:app --reload
```
Server runs at: http://localhost:8000

#### Terminal 2: Celery Worker
```powershell
.\venv\Scripts\activate
celery -A app.celery_app worker --loglevel=info --pool=solo
```

#### Terminal 3: (Optional) MLflow UI
```powershell
.\venv\Scripts\activate
mlflow ui
```
MLflow UI at: http://localhost:5000

---

## 📝 Testing the Complete Flow

### 1. Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Test User"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'
```

Save the `access_token` from the response.

### 3. Create a Project

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Credit Approval Model",
    "description": "Testing ethical AI validations"
  }'
```

Save the `id` from the response.

### 4. Upload a Model

```bash
curl -X POST http://localhost:8000/api/v1/models/upload \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@path/to/model.pkl" \
  -F "name=Credit Model v1" \
  -F "project_id=YOUR_PROJECT_ID" \
  -F "version=1.0.0"
```

Save the `id` from the response.

### 5. Upload a Dataset

```bash
curl -X POST http://localhost:8000/api/v1/datasets/upload \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@path/to/test_data.csv" \
  -F "name=Test Dataset" \
  -F "project_id=YOUR_PROJECT_ID"
```

Save the `id` from the response.

### 6. Run All Validations (NEW!)

```bash
curl -X POST http://localhost:8000/api/v1/validate/all \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "YOUR_MODEL_ID",
    "dataset_id": "YOUR_DATASET_ID",
    "fairness_config": {
      "sensitive_feature": "gender",
      "target_column": "approved",
      "thresholds": {
        "demographic_parity_ratio": 0.8,
        "equalized_odds_ratio": 0.8
      }
    },
    "transparency_config": {
      "target_column": "approved",
      "sample_size": 100
    },
    "privacy_config": {
      "k_anonymity_k": 5,
      "l_diversity_l": 2,
      "quasi_identifiers": ["age", "zipcode"],
      "sensitive_attribute": "income"
    }
  }'
```

Response:
```json
{
  "suite_id": "uuid-here",
  "task_id": "celery-task-id",
  "status": "queued",
  "message": "Validation suite queued. Use task_id to check status."
}
```

### 7. Check Task Status

```bash
curl -X GET http://localhost:8000/api/v1/validate/task/TASK_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response (in progress):
```json
{
  "task_id": "...",
  "state": "PROGRESS",
  "progress": 50,
  "current_step": "Transparency validation",
  "result": null,
  "error": null
}
```

Response (completed):
```json
{
  "task_id": "...",
  "state": "SUCCESS",
  "progress": 100,
  "current_step": "Completed",
  "result": {
    "suite_id": "...",
    "overall_passed": false,
    "validations": { ... }
  },
  "error": null
}
```

### 8. Get Complete Results

```bash
curl -X GET http://localhost:8000/api/v1/validate/suite/SUITE_ID/results \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 🎯 What's New (MVP Features)

### ✅ Background Task Processing
- All validations now run in background via Celery
- No more HTTP timeouts on large models
- Progress tracking during execution

### ✅ Validation Pipeline
- Single endpoint `/validate/all` runs all 4 validations
- Automatic orchestration (fairness → transparency → privacy)
- Aggregate results in one response

### ✅ Accountability Integration
- MLflow tracking for every validation
- Complete audit trail
- Experiment runs with metrics and artifacts

### ✅ Status Tracking
- Real-time progress updates
- Poll task status during execution
- Frontend-friendly API

---

## 📊 API Endpoints Summary

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/validate/all` | Run all 4 validations in background |
| GET | `/api/v1/validate/task/{task_id}` | Check task status and progress |
| GET | `/api/v1/validate/suite/{suite_id}/results` | Get aggregate validation results |

### Existing Endpoints (Still Work)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/validate/fairness` | Run fairness validation (synchronous) |
| POST | `/api/v1/validate/transparency` | Run transparency validation (synchronous) |
| POST | `/api/v1/validate/privacy` | Run privacy validation (synchronous) |

---

## 🔍 Monitoring

### Check Celery Worker Status

```powershell
# View active tasks
celery -A app.celery_app inspect active

# View registered tasks
celery -A app.celery_app inspect registered

# View worker stats
celery -A app.celery_app inspect stats
```

### View MLflow Experiments

1. Start MLflow UI: `mlflow ui`
2. Open: http://localhost:5000
3. Browse experiments: "ethical-ai-validations"
4. View metrics, parameters, and artifacts for each validation

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🐛 Troubleshooting

### Redis Connection Error

```
Error: Cannot connect to Redis
```

**Solution:**
```powershell
# Check if Redis is running
docker ps

# Start Redis if not running
docker start redis-ethical-ai

# Or start new container
docker run -d -p 6379:6379 --name redis-ethical-ai redis:latest
```

### Database Migration Error

```
Error: Target database is not up to date
```

**Solution:**
```powershell
# Run migrations
alembic upgrade head

# If issues persist, check database connection
alembic current
```

### Celery Worker Not Starting

```
Error: No module named 'app.celery_app'
```

**Solution:**
```powershell
# Make sure you're in the backend directory
cd backend

# Activate virtual environment
.\venv\Scripts\activate

# Try again
celery -A app.celery_app worker --loglevel=info --pool=solo
```

### Task Stuck in PENDING

**Possible causes:**
1. Celery worker not running
2. Redis connection issue
3. Task routing misconfiguration

**Solution:**
```powershell
# Restart Celery worker
# Ctrl+C to stop, then restart:
celery -A app.celery_app worker --loglevel=info --pool=solo

# Check Redis connection
redis-cli ping  # Should return "PONG"
```

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── celery_app.py          # NEW: Celery configuration
│   ├── tasks/                 # NEW: Background tasks
│   │   ├── __init__.py
│   │   └── validation_tasks.py
│   ├── models/
│   │   ├── validation_suite.py # NEW: Validation suite model
│   │   └── ...
│   ├── routers/
│   │   ├── validation.py      # UPDATED: New endpoints
│   │   └── ...
│   ├── validators/            # All 4 validators implemented
│   │   ├── fairness_validator.py
│   │   ├── explainability_engine.py
│   │   ├── privacy_validator.py
│   │   └── accountability_tracker.py
│   └── ...
├── alembic/
│   └── versions/
│       └── add_validation_suite.py # NEW: Migration
├── CELERY_SETUP.md            # NEW: Celery setup guide
├── QUICK_START.md             # NEW: This file
└── requirements.txt
```

---

## 🎓 Next Steps

1. **Test with Real Models**: Upload your ML models and datasets
2. **Customize Thresholds**: Adjust fairness thresholds for your use case
3. **Integrate Frontend**: Use the new `/validate/all` endpoint
4. **Monitor MLflow**: Check experiment tracking in MLflow UI
5. **Scale Workers**: Add more Celery workers for parallel processing

---

## 💡 Tips

- **Use `/validate/all` for production** - It's the recommended way to run validations
- **Poll task status every 2-3 seconds** - Don't overwhelm the server
- **Check MLflow for detailed metrics** - All validations are tracked
- **Keep Celery worker running** - It's required for background tasks
- **Monitor Redis memory** - Clear old task results if needed

---

## 📞 Support

- API Documentation: http://localhost:8000/docs
- MLflow UI: http://localhost:5000
- Celery Setup: See `CELERY_SETUP.md`
- Backend Analysis: See `backend_analysis.md` in artifacts

---

**Status: ✅ MVP Ready**

All critical features are now implemented:
- ✅ Background task processing
- ✅ Validation pipeline
- ✅ Accountability integration
- ✅ Status tracking
- ✅ MLflow experiment tracking

Happy validating! 🚀
