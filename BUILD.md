# Build & Deploy — SketchMyInfra (Pi5)

## Prerequisites

- Raspberry Pi 5 running Docker Compose
- SSH access to the Pi5

## Build Steps

```bash
# SSH into Pi5
ssh pi5

# Pull latest code
cd ~/sketchmyinfra
git pull origin refactor/whole-codebase

# Rebuild API image (includes D2 binary — first build downloads ~50MB)
docker compose build api

# Run DB migration (adds category + ir_data columns)
docker compose run --rm api alembic upgrade head

# Restart services
docker compose down
docker compose up -d

# Verify D2 is installed in the API container
docker compose exec api d2 --version

# Verify API health
curl http://localhost/api/health

# Tail logs to watch for errors
docker compose logs -f api
```

## Testing the V2 Endpoint

The new `/api/v2/generate` endpoint runs in parallel with the existing `/api/generate`. Both work independently.

```bash
# Test AWS cloud diagram (PlantUML renderer)
curl -s -X POST http://localhost/api/v2/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AWS VPC with ALB, ECS Fargate, and RDS PostgreSQL"}' | python3 -m json.tool | head -5

# Test ER diagram (D2 renderer)
curl -s -X POST http://localhost/api/v2/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Users table with id, email. Posts table with id, title, user_id FK. Users has many Posts."}' | python3 -m json.tool | head -5

# Test sequence diagram (D2 renderer)
curl -s -X POST http://localhost/api/v2/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Client sends POST /login to API. API queries Database for user. Database returns user row. API returns JWT to Client."}' | python3 -m json.tool | head -5

# Test building plan (Excalidraw renderer)
curl -s -X POST http://localhost/api/v2/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Side elevation of a building 12m wide, 3m walls, 5m peak height"}' | python3 -m json.tool | head -5
```

## Expected Response Format

```json
{
  "renderer": "plantuml | d2 | excalidraw",
  "category": "cloud_architecture | er_diagram | sequence | building_plan | ...",
  "code": "diagram source code (null for excalidraw)",
  "image": "data:image/svg+xml;base64,... (null for excalidraw)",
  "excalidraw_data": {"elements": [...], ...} (null for graph track),
  "prompt_used": "original prompt"
}
```

## Rollback

If something breaks, the old `/api/generate` endpoint is untouched and still works. The v2 endpoint is additive — no existing functionality was modified.

```bash
# Rollback migration if needed
docker compose run --rm api alembic downgrade -1
```
