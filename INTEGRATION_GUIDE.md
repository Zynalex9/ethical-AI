# Frontend-Backend Integration Guide

## ✅ What's Been Integrated

### Backend Updates:
1. ✅ Celery task queue for background processing
2. ✅ `/api/v1/validate/all` - Run all 4 validations
3. ✅ `/api/v1/validate/task/{task_id}` - Check task status
4. ✅ `/api/v1/validate/suite/{suite_id}/results` - Get results
5. ✅ MLflow accountability tracking
6. ✅ Database migration for `validation_suites` table

### Frontend Updates:
1. ✅ Updated `api.ts` with new validation endpoints
2. ✅ Completely rewritten `ValidationPage.tsx`:
   - All 4 validations in one click
   - Real-time progress tracking
   - Proper error handling
   - Results display with MLflow run IDs
3. ✅ Added TypeScript types for validation suite
4. ✅ Model/Dataset uploading already working

---

## 🚀 Quick Start (3 Terminals)

### Terminal 1: Backend + Database
```powershell
cd backend

# Activate virtual environment
.\venv\Scripts\activate

# Run database migration (IMPORTANT!)
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload
```

### Terminal 2: Celery Worker
```powershell
cd backend
.\venv\Scripts\activate

# Start Celery worker (required for background tasks!)
celery -A app.celery_app worker --loglevel=info --pool=solo
```

### Terminal 3: Frontend
```powershell
cd frontend

# Install dependencies (if not done)
npm install

# Start development server
npm run dev
```

---

## 📋 Testing Checklist

### 1. Start Services
- [ ] PostgreSQL running
- [ ] Redis running (`docker run -d -p 6379:6379 redis`)
- [ ] Backend API running (Terminal 1)
- [ ] Celery worker running (Terminal 2)
- [ ] Frontend running (Terminal 3)

### 2. Test Model Upload
1. Open http://localhost:5173
2. Login/Register
3. Create a new project
4. Click "Upload Model"
5. Upload a `.pkl` or `.h5` file
6. Verify model appears in table

### 3. Test Dataset Upload
1. Go to "Datasets" tab
2. Click "Upload Dataset"
3. Upload a `.csv` file
4. Specify sensitive feature and target column
5. Verify dataset appears in table

### 4. Test All Validations
1. Click "Run Validation" button
2. Select model and dataset
3. Configure:
   - Sensitive Feature (e.g., "gender")
   - Target Column (e.g., "approved")
   - Optional: Quasi-identifiers for privacy
4. Click "Run All Validations"
5. Watch progress bar update in real-time
6. Verify all 4 validation cards appear:
   - ✅ Fairness (green)
   - ✅ Transparency (blue)
   - ✅ Privacy (orange)
   - ✅ Accountability (purple)

### 5. Verify MLflow Tracking
1. Open http://localhost:5000 (if MLflow UI running)
2. Check "ethical-ai-validations" experiment
3. Verify 3 runs created (fairness, transparency, privacy)
4. Check metrics and artifacts

---

## 🐛 Troubleshooting

### "Cannot connect to Redis"
```powershell
# Start Redis
docker run -d -p 6379:6379 --name redis-ethical-ai redis:latest

# Verify
docker ps
```

### "Task stuck in PENDING"
- Check if Celery worker is running in Terminal 2
- Look for errors in Celery worker logs
- Restart Celery worker if needed

### "Database migration error"
```powershell
cd backend
alembic upgrade head
```

### "Frontend can't connect to backend"
- Check backend is running on http://localhost:8000
- Check `.env` file in frontend has correct `VITE_API_URL`
- Check CORS settings in backend

### "Grid import error in ValidationPage"
The new ValidationPage uses Material-UI Grid v2. If you see errors, update:
```tsx
// Change this:
import { Grid } from '@mui/material';

// To this:
import Grid from '@mui/material/Unstable_Grid2';
```

---

## 📊 API Endpoints Summary

### New Endpoints:
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/validate/all` | Run all 4 validations |
| GET | `/api/v1/validate/task/{task_id}` | Check task status |
| GET | `/api/v1/validate/suite/{suite_id}/results` | Get suite results |

### Existing Endpoints (Still Work):
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/models/upload` | Upload model |
| POST | `/api/v1/datasets/upload` | Upload dataset |
| GET | `/api/v1/models/project/{id}` | List models |
| GET | `/api/v1/datasets/project/{id}` | List datasets |

---

## ✨ Features Implemented

### All 4 Ethical Validations:
1. **Fairness** - Demographic parity, equalized odds, disparate impact
2. **Transparency** - SHAP feature importance, model cards
3. **Privacy** - PII detection, k-anonymity, l-diversity
4. **Accountability** - MLflow experiment tracking

### Progress Tracking:
- Real-time progress bar (0-100%)
- Current step display ("Fairness validation", "Transparency validation", etc.)
- Automatic polling every 2 seconds

### Results Display:
- Overall pass/fail status
- Individual validation cards with status
- MLflow run IDs for traceability
- Error messages if validation fails

---

## 🎯 What Works Now

✅ **Model Upload**: Drag & drop or browse, supports .pkl, .h5, .pt, .onnx
✅ **Dataset Upload**: CSV files with column detection
✅ **All 4 Validations**: Single button to run everything
✅ **Background Processing**: No HTTP timeouts
✅ **Progress Tracking**: Real-time updates
✅ **Accountability**: MLflow tracking integrated
✅ **Error Handling**: Proper error messages
✅ **No Broken Links**: All navigation works
✅ **No Useless Buttons**: Every button has functionality

---

## 📝 Files Modified

### Backend:
- `app/celery_app.py` (NEW)
- `app/tasks/validation_tasks.py` (NEW)
- `app/models/validation_suite.py` (NEW)
- `app/routers/validation.py` (UPDATED)
- `alembic/versions/add_validation_suite.py` (NEW)

### Frontend:
- `src/services/api.ts` (UPDATED)
- `src/pages/ValidationPage.tsx` (COMPLETELY REWRITTEN)
- `src/types/index.ts` (UPDATED)

---

## 🎉 Ready to Test!

Everything is integrated and ready. Just follow the Quick Start steps above!
