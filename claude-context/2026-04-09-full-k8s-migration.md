# 2026-04-09 — Full Backend Migration to k3s

## What We Did

Moved the entire stack (postgres, plantuml, api, frontend) into k3s on the Pi5.
Previously only the frontend was running in k8s — the backend was still in
docker-compose, which meant `dev.sketchmyinfra.com/api/*` had no route through
Traefik and OAuth callbacks would have 404'd.

## Why (Decision)

**Problem:** Split-brain deployment. Frontend in k8s, backend in docker-compose.
k3s doesn't know about docker-compose's bridge network, so Traefik couldn't
route `/api/*` to the FastAPI container without an ugly bridge.

**Considered:**
- **A — Everything in k8s.** More YAML, one source of truth. ✅ Chose this.
- **B — Headless Service bridging to host-port docker-compose.** Footgun territory.
- **C — Second Cloudflare Tunnel hostname for api.**  CORS + cookie-domain pain we don't need.

One deployment model wins. Also we now get rolling updates, health probes,
and init-container migrations for free.

---

## New File Layout

```
k8s/
├── configmap.yaml        # Non-secret env: APP_URL, CORS, model, rate limits, etc
├── secret.example.yaml   # Template (gitignored copy is secret.yaml)
├── postgres.yaml         # PVC (2Gi local-path) + Deployment + Service
├── plantuml.yaml         # Deployment + Service (JAVA_TOOL_OPTIONS gotcha baked in)
├── api.yaml              # Deployment (initContainer runs alembic) + Service
├── frontend.yaml         # Deployment + Service (hostPath for static files)
└── ingress.yaml          # Single Ingress, /api → api, / → frontend, 3 hosts
```

---

## Key Design Decisions

### 1. Config split: ConfigMap vs Secret
- **ConfigMap** (`sketchmyinfra-config`): APP_URL, CORS_ORIGINS, PLANTUML_SERVER_URL,
  GEMINI_MODEL, rate limits, JWT algorithm/expiry, POSTGRES_DB, POSTGRES_USER,
  ENVIRONMENT.
- **Secret** (`sketchmyinfra-secret`): POSTGRES_PASSWORD, **DATABASE_URL** (because
  it embeds the password), JWT_SECRET, GEMINI_API_KEY, all four OAuth client
  id/secret pairs.
- **Why DATABASE_URL lives in the Secret:** If you split it into POSTGRES_HOST +
  POSTGRES_PORT + POSTGRES_PASSWORD and try to assemble it at runtime, you're
  building a footgun. The cleanest approach is to put the whole URL in the
  Secret since it's functionally sensitive anyway.

### 2. Migrations via initContainer, not Job
```yaml
initContainers:
  - name: migrate
    image: sketchmyinfra-api:local
    command: ["alembic", "upgrade", "head"]
```
**Why:** Every rollout auto-migrates. If migration fails, the pod never becomes
Ready — which is the correct behavior (don't serve traffic on a broken schema).
A Job would be more "correct" for multi-replica, but with `replicas: 1` on the
Pi5 this is simpler and leaves no separate resource to clean up.

**Tradeoff:** When we eventually scale to multiple replicas, we'll want to move
this to a Job or a `helm upgrade --hook` style thing so migrations don't run
N times in parallel. Today's problem is not tomorrow's problem.

### 3. Image delivery: build-and-import, no registry
k3s uses containerd, not docker. So `docker build` creates an image that k3s
can't see. Two options:
- **Push to a registry** (Docker Hub, GHCR) — cleanest but adds credentials + network.
- **Build and import into containerd directly** — what we're doing.

```bash
# On the Pi5
cd ~/sketchmyinfra
docker build -t sketchmyinfra-api:local ./backend
docker save sketchmyinfra-api:local | sudo k3s ctr images import -
```

Combined with `imagePullPolicy: IfNotPresent` and a fixed tag, k3s uses the
imported image. When you want to "deploy a new version," rebuild + import +
`kubectl rollout restart deployment/sketchmyinfra-api`.

### 4. Postgres: `strategy: Recreate`, not RollingUpdate
RWO (ReadWriteOnce) PVCs can only be mounted by one pod at a time. A rolling
update briefly has both the old and new pod running, which deadlocks on the
volume. `Recreate` tears down the old pod first, then creates the new one.
**Tradeoff:** ~30s of downtime on postgres restarts. For single-node Pi5, fine.

### 5. No TLS on the Ingress
Traffic from Cloudflare's edge to the Pi5 flows through an authenticated
mTLS tunnel (cloudflared). Cloudflared proxies to `http://localhost:80` plain
HTTP, so Traefik's `websecure` (443) entrypoint never sees external traffic.
Adding a TLS block with no `secretName` makes Traefik generate a self-signed
cert that serves no purpose and would confuse future-you. Dropped it.

### 6. Service names match env var expectations
- Service `postgres` → `DATABASE_URL=...@postgres:5432/...`
- Service `plantuml` → `PLANTUML_SERVER_URL=http://plantuml:8080`
- Service `sketchmyinfra-api` (port 8000) for the ingress
- Service `sketchmyinfra-frontend` (port 80) for the ingress

k8s in-cluster DNS resolves bare service names within the same namespace, so
no FQDNs needed.

### 7. Ingress path order
Traefik picks the most specific prefix match. Having both `/api` and `/` under
the same host lets Traefik route correctly without annotation gymnastics.

---

## Deploy Workflow (On the Pi5)

### First-time setup

```bash
cd ~/sketchmyinfra

# 1. Build the API image
docker build -t sketchmyinfra-api:local ./backend

# 2. Import into k3s's containerd
docker save sketchmyinfra-api:local | sudo k3s ctr images import -

# 3. Create your secret file (do NOT commit)
cp k8s/secret.example.yaml k8s/secret.yaml
# Edit k8s/secret.yaml with real values:
#  - Generate JWT_SECRET: python3 -c "import secrets; print(secrets.token_hex(32))"
#  - Paste Gemini API key
#  - Paste Google + GitHub OAuth client id/secret
#  - Set POSTGRES_PASSWORD (remember to keep DATABASE_URL in sync!)
vim k8s/secret.yaml

# 4. Apply in dependency order
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/plantuml.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# Or all at once (order doesn't matter for apply — k8s reconciles):
kubectl apply -f k8s/
```

### Watch it come up

```bash
kubectl get pods -w
# Expect: postgres Running, plantuml Running, sketchmyinfra-api 0/1 Init,
#         then sketchmyinfra-api 1/1 Running, sketchmyinfra-frontend Running

kubectl logs -f deployment/sketchmyinfra-api -c migrate   # init container
kubectl logs -f deployment/sketchmyinfra-api              # main container
```

### Test

```bash
# Cluster-internal (bypasses ingress)
kubectl port-forward svc/sketchmyinfra-api 8000:8000
curl http://localhost:8000/api/health

# Through the ingress
kubectl port-forward -n kube-system svc/traefik 8080:80
curl -H "Host: dev.sketchmyinfra.com" http://localhost:8080/api/health

# End-to-end via Cloudflare Tunnel
curl https://dev.sketchmyinfra.com/api/health
```

### Deploy a new API version

```bash
cd ~/sketchmyinfra
git pull
docker build -t sketchmyinfra-api:local ./backend
docker save sketchmyinfra-api:local | sudo k3s ctr images import -
kubectl rollout restart deployment/sketchmyinfra-api
kubectl rollout status deployment/sketchmyinfra-api
```

### Rolling back

```bash
kubectl rollout undo deployment/sketchmyinfra-api
```

---

## Debugging Cheatsheet

```bash
# Pod won't start
kubectl describe pod -l app=sketchmyinfra-api
kubectl logs -l app=sketchmyinfra-api -c migrate
kubectl logs -l app=sketchmyinfra-api

# Ingress not routing
kubectl describe ingress sketchmyinfra
kubectl logs -n kube-system -l app.kubernetes.io/name=traefik

# Postgres down / PVC stuck
kubectl get pvc
kubectl describe pvc postgres-data
kubectl logs -l app=postgres

# Hit services directly to isolate where a failure is
kubectl exec -it deploy/sketchmyinfra-api -- curl http://plantuml:8080/
kubectl exec -it deploy/sketchmyinfra-api -- curl http://postgres:5432/ || echo "expected: not HTTP"

# Shell into postgres
kubectl exec -it deploy/postgres -- psql -U smi -d sketchmyinfra
```

---

## Gotchas to Watch For

1. **Forgetting `k3s ctr images import`** after rebuilding. Symptom: `ImagePullBackOff`
   on the api pod. k3s can't see docker-build images until you import them.

2. **Password drift between `POSTGRES_PASSWORD` and `DATABASE_URL`.** They live in
   the same Secret but you have to update them together. If postgres comes up
   with password X but the api connects with password Y → auth failure on every
   request. Do a sanity check: `kubectl exec deploy/postgres -- psql -U smi -c '\l'`
   and then a round-trip through `/api/health`.

3. **Ingress `/api` prefix and OAuth callback URLs.** The Google/GitHub OAuth apps
   must have `https://dev.sketchmyinfra.com/api/auth/google/callback` registered
   exactly — trailing slashes, scheme, host must all match. Check Cloudflare DNS
   has a `dev` CNAME pointing at the tunnel and cloudflared config includes
   `dev.sketchmyinfra.com`.

4. **Cookie `Secure` flag.** Our auth router sets `secure=True` when `APP_URL`
   starts with `https://`. Since the ConfigMap sets `APP_URL=https://dev.sketchmyinfra.com`,
   cookies WILL be marked Secure. Browser will drop them on plain HTTP. Always
   test through the tunnel, never via raw IP or port-forward.

5. **PVC data survives `kubectl delete deployment postgres`** but NOT
   `kubectl delete pvc postgres-data`. Deleting the PVC wipes the database.
   Add a reminder to yourself.

6. **The frontend `hostPath` is node-local.** If you ever add a second node,
   the frontend pod could land on a node that doesn't have `/home/ubuntu/sketchmyinfra/frontend`.
   For single-node Pi5 this is fine. For multi-node, bake the frontend into
   an nginx image instead.

---

## Open Questions / Next Steps

- [ ] **Test the full OAuth flow end-to-end** once you've imported the api image,
      applied the manifests, and configured Google + GitHub OAuth apps.
- [ ] **Frontend nginx /api proxy removal:** the old docker-compose nginx config
      proxied /api/ to the api container. In the k8s world, Traefik does that
      routing, so the frontend pod's nginx doesn't need a proxy rule — it's
      just serving static files. The current `nginx:alpine` image uses the
      default config which is exactly that. ✅ Already correct.
- [ ] **docker-compose.yml** is now dev-only for local testing on your laptop.
      Consider whether to keep it or delete it. My vote: keep it — faster
      iteration cycle on a MacBook than rebuilding + importing to k3s.
- [ ] **Phase 6 — Rate limiting.** Now that auth is wired in, count rows in
      `generations` by user_id (signed-in) or ip_address (anonymous) per day.
- [ ] **Phase 7 — Frontend auth UI.** Sign in buttons, `useUser()` hook, logout
      button, gated generator view.
- [ ] **Move postgres PVC to external SSD** (Layer 1 of the Pi5 persistence
      strategy). Reconfigure k3s local-path-provisioner's data directory or use
      a manually-created PV pointing at an SSD mount.
- [ ] **Daily pg_dump cron** synced to R2/B2 (Layer 3).
