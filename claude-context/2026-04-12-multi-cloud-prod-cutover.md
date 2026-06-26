# Multi-cloud support, prod cutover, and frontend fixes

**Date:** 2026-04-12
**Branch:** `feat/update-gemini`

## Topics covered

- Fixed frontend bugs: JSON parse error on HTML 502, error state UX, footer text
- Added X-Forwarded-For parsing for real visitor IP
- Baked frontend into nginx Docker image (killed hostPath stale-inode bug)
- Split k8s into dev (default namespace) and prod (`prod` namespace)
- Created all prod manifests with separate ConfigMap, Secret, Ingress
- Added multi-cloud PlantUML support (GCP + Azure) to the Gemini system prompt
- Fixed GCP and Azure icon path bugs that caused 502 on render
- Created README.md with SEO keywords and live site URL

## Decisions + why

| Decision | Why |
|---|---|
| Let LLM infer cloud provider from service names | Most natural UX — user just describes what they want. Explicit dropdown adds friction for no benefit since Gemini recognizes "Cloud Run" = GCP trivially. |
| Keep all three reference examples in the system prompt | Each cloud has different naming conventions (!define, include paths, macro names). One example per cloud teaches the pattern. ~5000 chars total, well within Gemini's system instruction budget. |
| Dev in default namespace, prod in `prod` namespace | Avoids touching the working dev deployment. Namespaces give full isolation (separate PVCs, Secrets, Services). Short DNS names (`postgres`) resolve within the namespace automatically. |
| Bake frontend into nginx image instead of hostPath | Eliminates the stale-inode 403 bug. Deployments become atomic: build → import → rollout restart. No more "git pull then restart". |
| Separate OAuth apps for prod | Dev and prod OAuth apps have different redirect URIs. Sessions can't cross environments because JWT_SECRET differs. |

## Critical gotchas discovered

### GCP PlantUML icons use underscores, not CamelCase

**This caused 502 errors on GCP diagram renders.**

| Wrong (CamelCase) | Correct (underscores) |
|---|---|
| `GCPPuml/Compute/CloudRun.puml` | `GCPPuml/Compute/Cloud_Run.puml` |
| `CloudRun(alias, "label", "tech")` | `Cloud_Run(alias, "label", "tech")` |
| `GCPPuml/Databases/CloudSQL.puml` | `GCPPuml/Databases/Cloud_SQL.puml` |
| `GCPPuml/Networking/CloudLoadBalancing.puml` | `GCPPuml/Networking/Cloud_Load_Balancing.puml` |

Both the filename AND the macro name use underscores. The system prompt now explicitly warns Gemini about this.

### Azure icon path gotchas

| Wrong | Correct |
|---|---|
| `AzurePuml/Web/AzureAppService.puml` | `AzurePuml/Compute/AzureAppService.puml` |
| `AzureSQLDatabase` (uppercase SQL) | `AzureSqlDatabase` (lowercase ql) |

AppService lives in `Compute/`, not `Web/`. The `Web/` folder has `AzureWebApp.puml` but that's a different icon.

### PlantUML icon library URLs

All three are public GitHub raw URLs fetched at render time by the PlantUML server:

```
AWS:   https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
GCP:   https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist
Azure: https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
```

The PlantUML container must have internet access to fetch these. No container changes needed — same mechanism AWS already uses.

## Commands / configs

### Frontend image build (new)

```bash
# Build
docker build -t sketchmyinfra-frontend:local frontend/

# Import into k3s
docker save sketchmyinfra-frontend:local | sudo k3s ctr images import -

# k8s/frontend.yaml now uses image: sketchmyinfra-frontend:local
# No more hostPath volume mount
```

### Prod namespace setup

```bash
kubectl create namespace prod
cp k8s/prod/secret.example.yaml k8s/prod/secret.yaml
# Edit with prod credentials
kubectl apply -f k8s/prod/
kubectl get pods -n prod -w
```

### Prod OAuth apps needed

- **Google:** console.cloud.google.com → OAuth Client → redirect URI: `https://sketchmyinfra.com/api/auth/google/callback`
- **GitHub:** github.com/settings/developers → callback URL: `https://sketchmyinfra.com/api/auth/github/callback`

## Key takeaways

- **Always verify PlantUML icon paths against the actual GitHub repo.** The naming conventions differ wildly between AWS (CamelCase), GCP (underscores), and Azure (CamelCase but surprising directory placement). Never assume the path from the service name.
- **Kubernetes namespaces give you free environment isolation.** Same cluster, same images, completely separate data and secrets. Services resolve by short name within their namespace — no config changes needed between dev and prod beyond the ConfigMap/Secret values.
- **Baking static files into container images is always better than hostPath.** hostPath is a debugging tool, not a deployment strategy. The 403 stale-inode bug proved this conclusively.
- **`api.js` should always check `Content-Type` before calling `.json()`.** Proxies (Traefik, Cloudflare) return HTML error pages on 502/504. Blindly parsing HTML as JSON gives the user a cryptic "Unexpected token '<'" instead of a useful "Request failed (502)".
- **X-Forwarded-For: take the first entry, trust it because Traefik is the only ingress.** If you ever expose pods directly, re-evaluate.

## File inventory

### New files
- `README.md` — project README with live URL, tech stack, setup guide, SEO keywords
- `frontend/Dockerfile` — bakes frontend into nginx:1.27-alpine
- `frontend/js/auth.js` — auth widget (login buttons / avatar+logout)
- `k8s/prod/configmap.yaml` — prod config (APP_URL=https://sketchmyinfra.com)
- `k8s/prod/secret.example.yaml` — prod secret template
- `k8s/prod/postgres.yaml` — prod postgres (4Gi PVC, separate from dev)
- `k8s/prod/plantuml.yaml` — prod plantuml
- `k8s/prod/api.yaml` — prod API with init containers
- `k8s/prod/frontend.yaml` — prod frontend (baked image)
- `k8s/prod/ingress.yaml` — routes sketchmyinfra.com + www
- `frontend/_archive/index-waitlist.html` — backup of old landing page

### Modified files
- `backend/app/services/gemini.py` — multi-cloud system prompt with GCP + Azure rules, reference examples, dynamic defaults, corrected icon paths
- `backend/app/routers/generate.py` — X-Forwarded-For IP parsing, user-aware with DB persistence
- `frontend/index.html` — generator UI active, auth slot, blurred error state, multi-cloud example chips, updated footer
- `frontend/js/api.js` — Content-Type check before JSON parse, credentials:'include'
- `frontend/js/ui.js` — showError accepts optional lastImageUri for blurred background
- `frontend/js/app.js` — engaging error copy, passes currentImageUri to showError
- `k8s/frontend.yaml` — uses baked image, no hostPath
- `k8s/ingress.yaml` — dev only (dev.sketchmyinfra.com), renamed to sketchmyinfra-dev
- `.gitignore` — added k8s/prod/secret.yaml

## Rate limiting (Phase 6) — implemented same session

### Backend (`generate.py`)
- `_check_rate_limit()` counts generations in last 24h BEFORE calling Gemini
- Anonymous: 3/day per IP (uses `idx_generations_ip_date`)
- Logged-in free: 5/day per user_id (uses `idx_generations_user_date`)
- Pro tier: unlimited (`if user.tier == "pro": return`)
- Returns HTTP 429 with structured JSON: `{message, limit, used, authenticated}`
- **Bug fix:** PostgreSQL INET column can't be compared with a plain string — needed `cast(ip, INET)` to avoid `operator does not exist: inet = character varying`

### Frontend rate limit UX
- `api.js`: detects 429, throws typed error with `.rateLimited`, `.authenticated`, `.limit`
- `api.js`: handles `data.detail` being an object (dict) — `typeof` check prevents `[object Object]` display
- `app.js`: catch block routes to different UIs based on auth state
- `ui.js` — `showRateLimitLogin(limit, lastImageUri)`: anonymous users see "You're on a roll!" + Google/GitHub login buttons
- `ui.js` — `showUpgradePrompt(limit, lastImageUri)`: logged-in users see Pro teaser with:
  - Momentum headline: "Whoa, 5 diagrams today? You're a machine!"
  - Feature card: unlimited generations, priority rendering, history, **$2/month** (emerald-400 color)
  - "Count me in" button → POSTs to Formspree (`xykboawb`) with user's OAuth email + `source: pro-upgrade-prompt`
  - Shows "You're on the early list!" confirmation inline after click
- Cache-busting: added `?v=2` to all `<script>` tags to prevent stale browser cache after deploys

### Bugs found and fixed during deployment
| Bug | Cause | Fix |
|-----|-------|-----|
| `[object Object]` in error message | `data.detail` was a dict, `new Error({...})` stringifies as `[object Object]` | `typeof data.detail === 'string'` check in `api.js` |
| `inet = character varying` SQL crash | PostgreSQL INET column compared with plain Python string | `cast(ip, INET)` in the rate limit query |
| Browser serving stale JS after deploy | nginx default cache headers + no cache-busting | Added `?v=N` query strings to script tags |
| "$2/month" invisible on dark UI | `text-white` on white card background | Changed to `text-emerald-400` |
| Em dashes (`—`) look like double hyphens | Unicode em dash renders poorly in some fonts | Replaced with comma and bullet (`·`) |

### Pro tier — UX only, no payment integration
- `User.tier` column already existed (`default="free"`)
- Backend skips rate limit for `tier == "pro"` (one-liner future-proof)
- `/api/auth/me` already returns `tier` in response
- No Stripe integration — "Notify me" button submits interest to Formspree
- To manually upgrade a user: `UPDATE users SET tier = 'pro' WHERE email = '...';`

### ReplicaSet cleanup
- Old ReplicaSets pile up (0 replicas) after each `rollout restart` — Kubernetes keeps them for rollback history
- Fix: add `revisionHistoryLimit: 3` to deployment specs
- Manual cleanup: `kubectl get rs -o json | jq -r '.items[] | select(.spec.replicas==0) | .metadata.name' | xargs kubectl delete rs`

## Next steps

- [ ] Deploy and test all three cloud example chips on dev
- [x] Rate limiting (Phase 6) — implemented with server-side enforcement
- [ ] History from DB — `GET /api/generations` for logged-in users
- [ ] Persist frontend history to localStorage (survives page refresh)
- [ ] Prod cutover — create OAuth apps, fill secret, apply, verify
- [ ] Add `revisionHistoryLimit: 3` to all deployment specs
- [ ] Stripe integration for Pro tier (when demand is validated via Formspree signups)
- [ ] Automate cache-busting (build timestamp instead of manual `?v=N`)
