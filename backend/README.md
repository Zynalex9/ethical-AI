# Ethical AI Requirements Engineering Platform - Backend

A FastAPI-based backend for validating AI models against ethical requirements (fairness, transparency, privacy, accountability).

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis 7+

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
copy .env.example .env
# Edit .env with your database credentials
```

4. Create the PostgreSQL database:
```sql
CREATE DATABASE ethical_ai;
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── dependencies.py      # FastAPI dependencies
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API route handlers
│   ├── services/            # Business logic
│   └── validators/          # ML validation engine (Sprint 2+)
├── requirements.txt
├── .env.example
└── README.md
```

## Authentication

The API uses JWT (JSON Web Tokens) for authentication:

1. Register: `POST /api/v1/auth/register`
2. Login: `POST /api/v1/auth/login` → Returns access & refresh tokens
3. Use access token in Authorization header: `Bearer <token>`
4. Refresh token: `POST /api/v1/auth/refresh`

## Development

Run with auto-reload:
```bash
uvicorn app.main:app --reload --port 8000
```
