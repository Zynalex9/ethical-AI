#!/usr/bin/env bash
# scripts/deploy.sh – Build and deploy the Ethical AI platform (production)
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

echo "=== Ethical AI Platform – Production Deploy ==="

# Ensure env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.production and fill in values."
  exit 1
fi

echo "1/4  Pulling latest images …"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull

echo "2/4  Building services …"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache

echo "3/4  Running database migrations …"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm backend \
  alembic upgrade head

echo "4/4  Starting all services …"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo ""
echo "✅  Deploy complete.  Services:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
