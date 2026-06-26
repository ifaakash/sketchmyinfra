# 2026-04-08 — Backend Build: Phases 1–4

## What We Built

### Phase 1: Skeleton
- FastAPI app with health check (`/api/health`)
- Docker Compose: nginx + api + db (postgres:16) + plantuml (jetty)
- nginx reverse proxy: `/` → frontend, `/api/` → FastAPI
- Pydantic Settings for env var config
- `.env.example` with all required vars

### Phase 2: Database
- SQLAlchemy async models: `User` and `Generation`
- Alembic for migrations (async setup with `asyncpg`)
- Migration `24bbc3928cc0`: creates both tables with indexes
- Partial indexes on `generations` for rate limiting (by user_id or ip_address)
- UUID primary keys to prevent enumeration

### Phase 3: PlantUML Render Endpoint
- `POST /api/render` — accepts PUML code, returns base64 data URI (svg/png)
- PlantUML service client using `httpx` async
- Error extraction from PlantUML's error SVGs (returns meaningful messages)

### Phase 4: Gemini Generate Endpoint
- `POST /api/generate` — accepts prompt, returns PUML code
- Gemini API client with system prompt for infrastructure diagrams
- Markdown code fence stripping (Gemini sometimes wraps output)
- Test endpoint: `POST /api/test/full-pipeline` (dev only)
- Test preview: `GET /api/test/preview` (renders last diagram in browser)
- Files saved to `test_output/` (mounted as Docker volume)

---

## Key Decisions & Gotchas

### PlantUML Security Profile
- **Problem:** PlantUML server blocks `!include` from external URLs by default
- **Fix:** `JAVA_TOOL_OPTIONS: "-DPLANTUML_SECURITY_PROFILE=UNSECURE"` in docker-compose
- **NOT working:** `PLANTUML_SECURITY_PROFILE` env var directly, or `-Dplantuml.security.profile` via `JAVA_OPTIONS`
- **Only `JAVA_TOOL_OPTIONS` works** — it gets injected into the JVM automatically

### Gemini Prompt Engineering
- Must explicitly tell Gemini: "do NOT use Internetalt1" — the icon file exists but the function name is broken in v20.0
- Use `actor` or `cloud` for internet/user elements instead
- Must tell Gemini to use v20.0 AWS icons (not v18.0)
- Include a reference example in the system prompt — drastically improves output quality
- Gemini sometimes wraps output in markdown code fences despite instructions — backend strips them

### Alembic CLI Path Issue
- `alembic` CLI couldn't find `app` module inside Docker
- **Fix:** Added `sys.path.insert(0, ...)` in `alembic/env.py`
- Alternative: run alembic via `python -c "from alembic.config import Config; ..."` which works without the path fix

### Dockerfile WORKDIR
- Changed from `/app` to `/backend` to avoid conflict with `app/` Python package
- `/app/app/` was confusing for imports

---

## File Structure (Backend)
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Pydantic Settings
│   ├── database.py          # Async SQLAlchemy
│   ├── models.py            # User, Generation
│   ├── schemas.py           # Request/response models
│   ├── routers/
│   │   ├── generate.py      # POST /api/generate
│   │   ├── render.py        # POST /api/render
│   │   └── test.py          # Test pipeline (dev only)
│   └── services/
│       ├── gemini.py        # Gemini API + system prompt
│       └── plantuml.py      # PlantUML server client
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 24bbc3928cc0_create_users_and_generations_tables.py
├── requirements.txt
├── Dockerfile
└── alembic.ini

docker-compose.yml
nginx/conf.d/default.conf
.env.example
```

---

## Commands Reference

```bash
# Start everything
docker compose up --build -d

# Check health
curl http://localhost/api/health

# Generate PUML from prompt
curl -s -X POST http://localhost/api/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AWS VPC with ALB and ECS"}'

# Render PUML to image
curl -s -X POST http://localhost/api/render \
  -H "Content-Type: application/json" \
  -d '{"puml": "@startuml\nAlice -> Bob: Hello\n@enduml", "format": "svg"}'

# Full pipeline test (generate + render + save files)
curl -s -X POST http://localhost/api/test/full-pipeline \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AWS VPC with ALB, ECS Fargate, and RDS PostgreSQL"}'

# Preview last test diagram in browser
open http://localhost/api/test/preview

# View saved files
ls test_output/
open test_output/test_diagram.png

# Run Alembic migration
docker compose exec api alembic upgrade head

# Check DB tables
docker compose exec db psql -U smi -d sketchmyinfra -c "\dt"

# View API docs (dev only)
open http://localhost/api/docs
```

---

## Next Steps
1. **Phase 5:** Google + GitHub OAuth (login, callback, JWT cookies)
2. **Phase 6:** Rate limiting (3/day anonymous, 5/day free)
3. **Phase 7:** Frontend update (auth UI, restore generator from _archive)
4. **Later:** Stripe payment integration for premium tier
