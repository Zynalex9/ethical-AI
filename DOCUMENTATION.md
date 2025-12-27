# Ethical AI Requirements Engineering Platform

## Complete Technical Documentation

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Backend Structure](#backend-structure)
4. [The Four Ethical Principles](#the-four-ethical-principles)
5. [Model Loading - What Can Be Uploaded](#model-loading)
6. [Fairness Validation - What Can Be Tested](#fairness-validation)
7. [Transparency Validation - Explainability](#transparency-validation)
8. [Privacy Validation](#privacy-validation)
9. [Accountability Tracking](#accountability-tracking)
10. [Frontend Structure](#frontend-structure)
11. [Current Capabilities vs Limitations](#capabilities-vs-limitations)
12. [API Endpoints](#api-endpoints)
13. [How to Run](#how-to-run)

---

## 1. Project Overview

The **Ethical AI Requirements Engineering Platform** is a web-based system that helps organizations validate their AI/ML models against four core ethical principles:

| Principle | What It Checks |
|-----------|----------------|
| **Fairness** | Does the model treat all demographic groups equally? |
| **Transparency** | Can we explain why the model makes its predictions? |
| **Privacy** | Does the data contain PII? Is it properly anonymized? |
| **Accountability** | Can we trace and audit all validation activities? |

### The Problem It Solves

AI systems often exhibit bias or make unexplainable decisions. Regulations like GDPR, EU AI Act, and industry standards require organizations to:
- Prove their AI systems don't discriminate
- Explain automated decisions
- Protect personal data
- Maintain audit trails

This platform automates these validations.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  React 18 + TypeScript + MUI + React Router + React Query       │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌─────────────────────┐  │
│  │  Login  │ │Dashboard│ │ Projects  │ │ Validation Results  │  │
│  └─────────┘ └─────────┘ └───────────┘ └─────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/REST API
┌──────────────────────────────▼──────────────────────────────────┐
│                         BACKEND (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      API Routers                             │ 
│  │  /auth  │  /projects  │  /models  │  /datasets  │ /validate  │
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Validation Engines                        │ 
│  │  ┌────────────┐ ┌──────────────┐ ┌─────────┐ ┌────────────┐  │
│  │  │  Fairness  │ │Transparency  │ │ Privacy │ │Accountability││
│  │  │ (Fairlearn)│ │ (SHAP/LIME)  │ │(k-anon) │ │  (MLflow)   │ │ 
│  │  └────────────┘ └──────────────┘ └─────────┘ └────────────┘  │
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Model Loader                              │ 
│  │  sklearn (.pkl) │ TensorFlow (.h5) │ PyTorch (.pt) │ ONNX    │
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                        DATA LAYER                               │
│   PostgreSQL (async)  │  Redis (caching)  │  MLflow (tracking)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Environment configuration
│   ├── database.py             # SQLAlchemy async setup
│   ├── dependencies.py         # JWT auth dependency
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py             # User with roles (user/admin/auditor)
│   │   ├── project.py          # Project container
│   │   ├── ml_model.py         # Uploaded ML model metadata
│   │   ├── dataset.py          # Uploaded dataset metadata
│   │   ├── template.py         # Pre-defined validation templates
│   │   ├── requirement.py      # Custom ethical requirements
│   │   ├── validation.py       # Validation run + results
│   │   └── audit_log.py        # Complete audit trail
│   │
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── user.py             # UserCreate, UserLogin, Token
│   │   └── project.py          # ProjectCreate, ProjectResponse
│   │
│   ├── routers/                # API endpoints
│   │   └── auth.py             # /register, /login, /refresh, /me
│   │
│   ├── services/               # Business logic
│   │   ├── auth_service.py     # JWT + password hashing
│   │   └── model_loader.py     # Universal model loading
│   │
│   ├── validators/             # Validation engines
│   │   ├── fairness_validator.py      # Fairlearn integration
│   │   ├── explainability_engine.py   # SHAP + LIME
│   │   ├── privacy_validator.py       # PII + k-anonymity
│   │   └── accountability_tracker.py  # MLflow + audit
│   │
│   └── examples/               # Demo scripts
│       ├── fairness_example.py
│       ├── transparency_example.py
│       └── privacy_accountability_example.py
│
├── requirements.txt
└── .env
```

---

## 4. The Four Ethical Principles

### How They Work Together

```
┌─────────────────────────────────────────────────────────────┐
│                     VALIDATION WORKFLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. Upload Model (.pkl, .h5, .pt, .onnx)                   │
│                     ↓                                       │
│   2. Upload Test Dataset (.csv with sensitive attributes)   │
│                     ↓                                       │
│   3. Select Ethical Requirements                            │
│      • Use Template (e.g., ETH1-Finance)                    │
│      • Or define custom thresholds                          │
│                     ↓                                       │
│   4. Run Validation Pipeline                                │
│      ┌──────────────────────────────────────────────────┐   │
│      │  PRIVACY → FAIRNESS → TRANSPARENCY → ACCOUNTABILITY  │
│      └──────────────────────────────────────────────────┘   │
│                     ↓                                       │
│   5. Generate Report with Pass/Fail for each principle      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Model Loading - What Can Be Uploaded

### File: `backend/app/services/model_loader.py`

The `UniversalModelLoader` supports **4 ML frameworks**:

| Framework | Extensions | How It's Loaded |
|-----------|------------|-----------------|
| **scikit-learn** | `.pkl`, `.joblib`, `.pickle` | `joblib.load()` or `pickle.load()` |
| **TensorFlow/Keras** | `.h5`, `.keras`, SavedModel dirs | `tf.keras.models.load_model()` |
| **PyTorch** | `.pt`, `.pth` | `torch.load()` |
| **ONNX** | `.onnx` | `onnxruntime.InferenceSession()` |

### Unified Interface

All models are wrapped to provide:
```python
model.predict(X)        # Returns class predictions (0, 1, 2, ...)
model.predict_proba(X)  # Returns probabilities [[0.3, 0.7], ...]
```

### Usage Example
```python
from app.services.model_loader import UniversalModelLoader

# Load any supported model type
model = UniversalModelLoader.load("path/to/model.pkl")

# Works the same regardless of framework
predictions = model.predict(X_test)
probabilities = model.predict_proba(X_test)

# Get metadata
metadata = UniversalModelLoader.get_model_metadata(model)
# {'model_type': 'sklearn', 'model_class': 'LogisticRegression', ...}
```

### ⚠️ Limitations
- PyTorch models must be **full models**, not state_dicts
- TensorFlow/PyTorch require those libraries installed (optional)
- Custom model classes need the original class definition available

---

## 6. Fairness Validation - What Can Be Tested

### File: `backend/app/validators/fairness_validator.py`

Uses the **Fairlearn** library to calculate group fairness metrics.

### Supported Metrics

| Metric | What It Measures | Passes If |
|--------|------------------|-----------|
| **Demographic Parity Ratio** | Equal selection rate across groups | ratio ≥ 0.8 |
| **Demographic Parity Difference** | Max difference in selection rates | diff ≤ 0.1 |
| **Equalized Odds Ratio** | Equal TPR and FPR across groups | ratio ≥ 0.8 |
| **Equalized Odds Difference** | Max TPR/FPR difference | diff ≤ 0.1 |
| **Equal Opportunity Difference** | Equal TPR only (relaxed equalized odds) | diff ≤ 0.1 |
| **Disparate Impact Ratio** | The "80% rule" from US employment law | ratio ≥ 0.8 |

### Group Metrics
For each demographic group, calculates:
- **Confusion Matrix** (TP, FP, TN, FN)
- **Accuracy**, **TPR**, **FPR**, **TNR**, **FNR**, **Precision**

### Usage Example
```python
from app.validators.fairness_validator import FairnessValidator

validator = FairnessValidator(
    y_true=y_test,           # Ground truth labels
    y_pred=model.predict(X_test),  # Model predictions
    sensitive_features=gender_column  # Protected attribute
)

# Run all fairness checks
report = validator.validate_all(thresholds={
    'demographic_parity_ratio': 0.8,
    'equalized_odds_ratio': 0.8
})

print(f"Overall Passed: {report.overall_passed}")
for metric in report.metrics:
    print(f"{metric.metric_name}: {metric.overall_value:.3f} - {'PASS' if metric.passed else 'FAIL'}")
```

### Visualizations Generated
1. **Selection Rate Bar Chart** - Shows positive prediction rate per group
2. **TPR/FPR Comparison** - Grouped bar chart comparing rates
3. **Confusion Matrix Heatmaps** - One per demographic group

### ⚠️ Limitations
- Currently binary classification only
- Single sensitive attribute at a time (no intersectionality)
- Requires labeled test data

---

## 7. Transparency Validation - Explainability

### File: `backend/app/validators/explainability_engine.py`

Uses **SHAP** and **LIME** libraries for model interpretability.

### Explanation Types

| Type | Method | What It Shows |
|------|--------|---------------|
| **Global SHAP** | KernelExplainer | Feature importance across entire dataset |
| **Local SHAP** | Per-instance | Why this specific prediction was made |
| **LIME** | LimeTabularExplainer | Alternative local explanation |
| **Model Card** | Structured docs | Model documentation per Mitchell et al. |

### SHAP Explanations
```python
from app.validators.explainability_engine import ExplainabilityEngine

engine = ExplainabilityEngine(
    model=model,
    X_train=X_train,  # Background data for SHAP
    feature_names=['age', 'income', 'credit_score', ...]
)

# Global feature importance
global_exp = engine.explain_global_shap(X_test)
for fi in global_exp.top_features(5):
    print(f"{fi.rank}. {fi.feature_name}: {fi.importance:.4f}")

# Local explanation for one instance
local_exp = engine.explain_local_shap(X_test, [0])
print(f"Prediction: {local_exp[0].prediction}")
for feature, contribution in local_exp[0].feature_contributions.items():
    print(f"  {feature}: {contribution:+.3f}")
```

### Model Card Contents
- Model details (name, type, features)
- Intended use
- Training/evaluation data stats
- Performance metrics (accuracy, precision, recall, F1)
- Ethical considerations status

### Visualizations Generated
1. **SHAP Summary Plot** (beeswarm)
2. **Feature Importance Bar Chart**
3. **Waterfall Plot** (single instance)

### ⚠️ Limitations
- SHAP KernelExplainer is slow for large datasets (sample first)
- LIME works best with tabular data
- Deep learning models may need specialized explainers

---

## 8. Privacy Validation

### File: `backend/app/validators/privacy_validator.py`

Checks datasets for privacy risks **before** model training or deployment.

### PII Detection

Detects personally identifiable information via:

| Method | Examples Detected |
|--------|-------------------|
| **Pattern Matching (Regex)** | emails, phone numbers, SSNs, credit cards, IPs |
| **Column Name Heuristics** | columns named 'email', 'ssn', 'phone', 'address' |
| **Value Analysis** | High-cardinality strings (likely identifiers) |

### k-Anonymity Checking

> **k-Anonymity**: Every combination of quasi-identifiers appears at least k times.

```python
from app.validators.privacy_validator import PrivacyValidator
import pandas as pd

validator = PrivacyValidator(df)

# Check if dataset is 5-anonymous
result = validator.check_k_anonymity(
    quasi_identifiers=['age', 'zip_code', 'gender'],
    k=5
)

print(f"Satisfies 5-anonymity: {result.satisfies_k}")
print(f"Actual minimum group size: {result.actual_min_k}")
```

### l-Diversity Checking

> **l-Diversity**: Each equivalence class has at least l distinct values of sensitive attribute.

Prevents homogeneity attacks where knowing quasi-identifiers reveals sensitive info.

### Full Validation
```python
report = validator.validate({
    'pii_detection': True,
    'k_anonymity': {'k': 5, 'quasi_identifiers': ['age', 'zip']},
    'l_diversity': {'l': 2, 'sensitive_attribute': 'income', 'quasi_identifiers': ['age', 'zip']}
})

print(f"Overall Passed: {report.overall_passed}")
for rec in report.recommendations:
    print(f"  ⚠️ {rec}")
```

### ⚠️ Limitations
- PII regex patterns are US-focused (phone, SSN formats)
- No differential privacy training (just validation)
- Generalization suggestions are manual, not automated

---

## 9. Accountability Tracking

### File: `backend/app/validators/accountability_tracker.py`

Provides audit trail and experiment tracking using **MLflow**.

### Features

| Feature | Description |
|---------|-------------|
| **MLflow Integration** | Track validation experiments with parameters and metrics |
| **Validation History** | Query past validations by model, requirement, or principle |
| **Model Versioning** | Register and track model versions |
| **Audit Reports** | Generate compliance reports with statistics |
| **Export** | Export complete audit trail as JSON |

### Usage Example
```python
from app.validators.accountability_tracker import AccountabilityTracker

tracker = AccountabilityTracker(
    tracking_uri="sqlite:///mlflow.db",
    experiment_name="ethical-ai-validations"
)

# Start tracking a validation run
run_id = tracker.start_validation_run(
    model_name="loan_model_v3",
    model_id="uuid-123",
    dataset_name="q4_test_data",
    dataset_id="uuid-456",
    requirement_name="ETH1-Fairness",
    requirement_id="req-001",
    principle="fairness",
    user_id="auditor_1"
)

# Log metrics
tracker.log_metrics({
    "demographic_parity_ratio": 0.85,
    "equalized_odds_ratio": 0.78
})

# End run with status
record = tracker.end_validation_run(status="passed")

# Query history
history = tracker.get_validation_history(model_id="uuid-123")

# Generate audit report
report = tracker.generate_audit_report()
print(f"Total validations: {report['summary']['total_validations']}")
print(f"Pass rate: {report['summary']['pass_rate']:.0%}")
```

### What Gets Tracked
- Who ran the validation
- When it was run
- What model and dataset were used
- What requirements were validated
- What metrics were calculated
- Pass/fail status

### ⚠️ Limitations
- MLflow model registry requires full MLflow setup
- In-memory storage in demo mode (use database in production)

---

## 10. Frontend Structure

```
frontend/
├── src/
│   ├── main.tsx              # Entry point + font loading
│   ├── App.tsx               # Routes + providers
│   ├── index.css             # Global CSS (dark theme variables)
│   ├── theme.ts              # MUI theme configuration
│   │
│   ├── contexts/
│   │   └── AuthContext.tsx   # Auth state (user, login, logout)
│   │
│   ├── services/
│   │   └── api.ts            # Axios with token interceptors
│   │
│   ├── types/
│   │   └── index.ts          # TypeScript interfaces
│   │
│   ├── layouts/
│   │   └── MainLayout.tsx    # Sidebar + AppBar
│   │
│   └── pages/
│       ├── LoginPage.tsx     # Login form
│       ├── RegisterPage.tsx  # Register form
│       └── DashboardPage.tsx # Stats + projects overview
```

### Tech Stack
- **Vite** - Fast build tool
- **React 18** - UI library
- **TypeScript** - Type safety
- **MUI (Material-UI)** - Component library
- **React Router** - Client-side routing
- **React Query** - Server state management
- **Axios** - HTTP client with interceptors

---

## 11. Current Capabilities vs Limitations

### ✅ What You CAN Do

| Category | Capability |
|----------|------------|
| **Models** | Load sklearn, TensorFlow, PyTorch, ONNX models |
| **Fairness** | Calculate 6 fairness metrics, generate visualizations |
| **Transparency** | SHAP global/local explanations, LIME, model cards |
| **Privacy** | Detect PII, check k-anonymity, check l-diversity |
| **Accountability** | MLflow tracking, audit logs, history queries |
| **Auth** | JWT-based login/register with role-based users |

### ❌ What You CANNOT Do (Yet)

| Category | Limitation | Future Work |
|----------|------------|-------------|
| **Models** | Multi-class fairness | Extend metrics |
| **Models** | Regression fairness | Add regression support |
| **Fairness** | Intersectional fairness | Multi-attribute analysis |
| **Fairness** | Bias mitigation | Add Fairlearn mitigation |
| **Privacy** | Differential privacy training | Integrate diffprivlib models |
| **Privacy** | Auto-anonymization | Implement generalization |
| **Frontend** | File upload UI | In progress |
| **Frontend** | Results visualization | In progress |
| **API** | Project CRUD | Needs implementation |
| **API** | Validation endpoints | Needs implementation |

### Database Status
- **Models defined**: Yes (9 SQLAlchemy models)
- **Migrations**: Not yet (need Alembic setup)
- **Running instance**: Requires PostgreSQL setup

---

## 12. API Endpoints

### Implemented

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create new user |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |
| GET | `/health` | Health check |

### Planned (Not Yet Implemented)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/projects` | List/create projects |
| POST | `/api/v1/models/upload` | Upload ML model |
| POST | `/api/v1/datasets/upload` | Upload dataset |
| POST | `/api/v1/validate/fairness` | Run fairness validation |
| POST | `/api/v1/validate/transparency` | Run transparency validation |
| POST | `/api/v1/validate/privacy` | Run privacy validation |
| GET | `/api/v1/validations/{id}` | Get validation results |

---

## 13. How to Run

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ (optional for auth)
- Redis (optional for Celery)

### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create .env from example
copy .env.example .env
# Edit .env with your database URL

# Run development server
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Run Example Scripts (No Server Required)
```bash
cd backend

# Fairness validation demo
python -m app.examples.fairness_example

# Transparency/SHAP demo
python -m app.examples.transparency_example

# Privacy & accountability demo
python -m app.examples.privacy_accountability_example
```

---

## Summary

This platform provides a **complete foundation** for validating AI systems against ethical requirements:

1. **Load any model** (sklearn, TensorFlow, PyTorch, ONNX) through a unified interface
2. **Check fairness** with 6 metrics using Fairlearn
3. **Explain predictions** with SHAP and LIME
4. **Validate privacy** with PII detection and k-anonymity
5. **Track everything** with MLflow and audit logs

The core validation engines are **fully functional** and can be used immediately via the example scripts. The web interface provides authentication and a dashboard foundation, with validation UI components as the next development phase.
