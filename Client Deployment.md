# Client Docker Deployment

This guide lets a client run the platform by pulling images from Docker Hub.

## A) Maintainer: publish images to Docker Hub

Run from project root:

```bash
# 1) Login to Docker Hub
docker login

# 2) Build and tag images
docker build -t <dockerhub-namespace>/ethical-ai-backend:latest ./backend
docker build -t <dockerhub-namespace>/ethical-ai-frontend:latest -f ./frontend/Dockerfile.prod ./frontend

# 3) Push images
docker push <dockerhub-namespace>/ethical-ai-backend:latest
docker push <dockerhub-namespace>/ethical-ai-frontend:latest
```

Optional versioned release:

```bash
docker tag <dockerhub-namespace>/ethical-ai-backend:latest <dockerhub-namespace>/ethical-ai-backend:v1.0.0
docker tag <dockerhub-namespace>/ethical-ai-frontend:latest <dockerhub-namespace>/ethical-ai-frontend:v1.0.0
docker push <dockerhub-namespace>/ethical-ai-backend:v1.0.0
docker push <dockerhub-namespace>/ethical-ai-frontend:v1.0.0
```

## B) Client: run the platform

Client needs only these files:

- `docker-compose.client.yml`
- `.env.client.example` (renamed to `.env.client`)

### 1) Prepare env file

Copy and edit:

```bash
cp .env.client.example .env.client
```

Set at least:

- `DOCKERHUB_NAMESPACE`
- `APP_TAG`
- `DB_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET_KEY`

### 2) Start containers

```bash
docker compose -f docker-compose.client.yml --env-file .env.client pull
docker compose -f docker-compose.client.yml --env-file .env.client up -d
```

### 3) Open app

- Frontend: `http://localhost`
- Backend docs: `http://localhost:8000/docs`

### 4) Stop / restart

```bash
docker compose -f docker-compose.client.yml --env-file .env.client down
docker compose -f docker-compose.client.yml --env-file .env.client up -d
```

## Notes

- Uploaded models/datasets persist in Docker volumes (`uploads_data`).
- Validation artifacts and MLflow DB persist in `mlflow_data`.
- Database persists in `postgres_data`.
- If client host already uses port 80, change `frontend` port mapping in `docker-compose.client.yml`.
