# Quick Start Guide - Docker + Database Setup

## Prerequisites

- Docker Desktop installed
- Git (optional)

## Setup Steps

### 1. Start PostgreSQL Database

```bash
# From project root (BS/)
docker-compose up -d postgres

# Wait for database to be ready (check logs)
docker-compose logs -f postgres
# Look for: "database system is ready to accept connections"
```

### 2. Install Alembic (if not already installed)

```bash
cd backend
pip install alembic asyncpg
```

### 3. Run Database Migrations

```bash
cd backend

# Generate initial migration (first time only)
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

### 4. Start All Services

```bash
# From project root
docker-compose up -d

# View logs
docker-compose logs -f
```

### 5. Verify Setup

- Backend API: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Database: localhost:5432

## Common Commands

```bash
# Stop all services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f [service_name]

# Access database
docker exec -it ethical-ai-db psql -U postgres -d ethical_ai

# Create new migration
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Troubleshooting

**Port already in use?**
Edit `docker-compose.yml` and change port mappings.

**Database connection failed?**
Check if PostgreSQL is running: `docker-compose ps`

**Migration errors?**
Reset database: `docker-compose down -v` then restart from step 1.

## Next Steps

1. Create a user account via `/api/auth/register`
2. Upload a model and dataset
3. Run validations

For detailed documentation, see `database_setup_plan.md`
