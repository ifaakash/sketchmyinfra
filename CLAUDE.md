# Project Instructions — SketchMyInfra

## Overview

SketchMyInfra is an AI-powered infrastructure diagram generator. Users describe cloud architecture in natural language, and Gemini AI converts it to PlantUML or Mermaid code, which is rendered as PNG/SVG. Live at [sketchmyinfra.com](https://sketchmyinfra.com).

## Documentation Policy

Whenever implementation depends on a framework, SDK, library or API, delegate to the `docs-researcher` agent for lookup. The agent follows this priority:

1. Context7 first.
2. Official documentation if Context7 is insufficient.
3. Web search as last resort.
4. Prefer official documentation over blogs.
5. Mention the documentation source used.
6. Never assume an API exists without verification.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS, Tailwind CSS (CDN), nginx |
| Draw Editor | React 18, Excalidraw, Vite (`frontend/draw-app/`) |
| Backend | Python 3.12, FastAPI, async SQLAlchemy, asyncpg |
| AI | Google Gemini API (`gemini-2.0-flash` / `gemini-2.5-flash`) |
| Diagram Rendering | PlantUML server (Jetty, server-side) + Mermaid.js (client-side) |
| Database | PostgreSQL 16, Alembic migrations |
| Auth | OAuth 2.0 (Google, GitHub), JWT sessions (HS256), HttpOnly cookies |
| Infra | k3s on Raspberry Pi 5, Traefik ingress, Cloudflare Tunnel |

## Common Commands

### Local dev (Docker Compose)

```bash
cp .env.example .env          # configure env vars
docker-compose up              # starts nginx, api, postgres, plantuml
# Frontend: http://localhost/   API: http://localhost/api/
```

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head           # run migrations
pytest                         # run tests
uvicorn app.main:app --reload  # dev server on :8000
```

### Frontend draw-app

```bash
cd frontend/draw-app
npm ci
npm run build                  # outputs to dist/, served at /draw/
```

### Kubernetes deploy (dev)

```bash
docker build -t sketchmyinfra-api:local backend/
docker build -t sketchmyinfra-frontend:local frontend/
docker save sketchmyinfra-api:local | sudo k3s ctr images import -
docker save sketchmyinfra-frontend:local | sudo k3s ctr images import -

cp k8s/secret.example.yaml k8s/secret.yaml   # edit with real creds
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/plantuml.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml
```

### Kubernetes deploy (prod)

```bash
kubectl create namespace prod
cp k8s/prod/secret.example.yaml k8s/prod/secret.yaml
kubectl apply -f k8s/prod/
```

## Architecture

```
Cloudflare Tunnel -> Traefik Ingress -> k3s cluster
                                         |-- nginx (frontend, static + /api proxy)
                                         |-- FastAPI (backend API, port 8000)
                                         |-- PlantUML server (rendering, port 8080)
                                         |-- PostgreSQL (data, port 5432)
```

### Diagram generation flow

1. `POST /api/generate` with natural language prompt
2. Rate limit check (by user ID or client IP)
3. Gemini generates PlantUML or Mermaid code (auto-classifies renderer)
4. If PlantUML: validate by sending to PlantUML server; auto-fix via Gemini if errors
5. Record generation in DB (status: success/gemini_error/autofix_failed)
6. Return `{renderer, code, prompt_used, puml}` to frontend
7. Frontend renders: PlantUML via `POST /api/render`, Mermaid client-side via mermaid.js

### Auth flow

Google/GitHub OAuth -> authorization code -> backend exchanges for token -> fetches user info -> upserts User -> issues JWT (7-day) in HttpOnly cookie (SameSite=Lax) -> `GET /api/auth/me` to load session

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app factory, CORS, router registration
    config.py            # Settings from environment
    database.py          # async SQLAlchemy engine + session
    models.py            # User, Generation, Drawing, Feedback (UUID PKs)
    schemas.py           # Pydantic request/response schemas
    routers/             # API endpoints (auth, generate, render, drawings, history, admin, feedback)
    services/            # Business logic (gemini, plantuml, oauth, jwt_service)
    middleware/auth.py   # JWT cookie session middleware
  alembic/               # DB migrations
  tests/                 # pytest (sanitize, render, error detection, renderer classify)

frontend/
  index.html             # Landing page
  js/                    # app.js, api.js, ui.js, auth.js, history.js, mermaid-renderer.js, gallery.js, feedback.js, mock.js
  css/style.css
  draw-app/              # React + Excalidraw editor (Vite build)

k8s/                     # Dev namespace manifests
  configmap.yaml, secret.example.yaml, postgres.yaml, api.yaml, frontend.yaml, plantuml.yaml, ingress.yaml
  prod/                  # Prod namespace manifests (same structure)

docker-compose.yml       # Local dev: nginx + api + postgres + plantuml
.env.example             # Environment variable template
```

## Key Files

### Backend Routers
| Router | Path | Purpose |
|--------|------|---------|
| auth | `backend/app/routers/auth.py` | OAuth login/callback, logout, `/me` |
| generate | `backend/app/routers/generate.py` | `POST /generate`, rate limiting, error reporting |
| render | `backend/app/routers/render.py` | `POST /render` (PlantUML -> image) |
| drawings | `backend/app/routers/drawings.py` | CRUD for Excalidraw drawings |
| history | `backend/app/routers/history.py` | Generation history |
| admin | `backend/app/routers/admin.py` | Stats endpoint (requires `ADMIN_API_KEY`) |
| feedback | `backend/app/routers/feedback.py` | User feedback submission |

### Backend Services
| Service | Path | Purpose |
|---------|------|---------|
| gemini | `backend/app/services/gemini.py` | AI code generation, sanitization, auto-fix pipeline |
| plantuml | `backend/app/services/plantuml.py` | PlantUML server client, error extraction |
| oauth | `backend/app/services/oauth.py` | Google & GitHub OAuth token exchange |
| jwt_service | `backend/app/services/jwt_service.py` | JWT creation/validation |

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | 32-byte hex key for session tokens |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Model name (e.g., `gemini-2.5-flash`) |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth credentials |
| `GITHUB_CLIENT_ID/SECRET` | GitHub OAuth credentials |
| `APP_URL` | Base URL for OAuth redirects |
| `PLANTUML_SERVER_URL` | Internal PlantUML service URL |
| `RATE_LIMIT_ANONYMOUS` | Max generations/day for anonymous users (default: 3) |
| `RATE_LIMIT_FREE` | Max generations/day for free users (default: 5) |
| `ADMIN_API_KEY` | Secret key for admin stats endpoint |

## Database

4 models (all UUID primary keys):
- **User** — email, name, avatar, oauth_provider/id, tier (free/pro), trial_expires_at
- **Generation** — user_id (nullable), prompt, puml_code, renderer, status, error_message, ip_address (INET)
- **Drawing** — user_id, share_id, title, data (JSONB), thumbnail
- **Feedback** — user_id (unique), rating, message

Migrations: `cd backend && alembic upgrade head` (auto-run by k8s init container)

## Testing

```bash
cd backend && pytest
```

Tests in `backend/tests/`:
- `test_sanitize.py` — PlantUML code sanitization
- `test_plantuml_render.py` — Rendering validation
- `test_error_detection.py` — Error message extraction from PlantUML server
- `test_renderer_classify.py` — Renderer detection (PlantUML vs Mermaid)

## Known Patterns & Gotchas

- **PlantUML icon paths** use underscores not CamelCase (e.g., `AWSLib/Storage/Simple_Storage_Service`). See `claude-context/` and memory files for details.
- **PostgreSQL INET columns** need explicit `cast(ip, INET)` when comparing with strings in SQLAlchemy.
- **Frontend deploys need cache-busting** — append `?v=N` to script tags to prevent stale browser cache.
- **k8s API deployment** uses init containers: `wait-for-postgres` then `alembic upgrade head` before the main container starts.
- **PlantUML is default renderer**; Mermaid restricted to 4 diagram types (flowchart, sequence, class, state).
- **Auto-fix pipeline**: if Gemini generates invalid PlantUML, the backend automatically asks Gemini to fix it before returning an error.
- **Rate limiting**: anonymous users tracked by IP (`CF-Connecting-IP` header), authenticated users by user ID.

## Session Logging (Mandatory)

At the end of every chat session or substantial discussion, generate a summary file in the `claude-context/` directory:

- **Filename format:** `claude-context/YYYY-MM-DD-<short-topic>.md`
- **Contents:**
  - Topics covered
  - Decisions made and reasoning
  - Commands/configs used
  - Key takeaways
  - Gotchas / mistakes
  - Open questions / next steps
- Keep summaries concise and scannable — optimize for "future me reading this 3 weeks later."
- This is **mandatory for every session** — do not skip it.
