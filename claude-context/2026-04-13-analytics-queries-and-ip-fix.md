# Analytics queries, CF-Connecting-IP fix, and deployment gotchas

**Date:** 2026-04-13
**Branch:** `feat/update-gemini`

## Topics covered

- Discovered IP-based rate limiting was broken — all visitors had internal cluster IPs (`10.42.0.x`)
- Fixed by reading `CF-Connecting-IP` header (Cloudflare Tunnel's real visitor IP)
- Documented useful analytics queries against the `generations` table
- Caught a deployment typo: `sketchmyinfra-backend:local` vs `sketchmyinfra-api:local`

## CF-Connecting-IP fix

### Problem
Rate limiting by IP was useless — all generations showed `10.42.0.x` (k3s pod CIDR). The request chain is:

```
Visitor (real IP) → Cloudflare Edge → cloudflared pod (10.42.x.x) → Traefik → API pod
```

Traefik sees `cloudflared` as the client, so `X-Forwarded-For` = cloudflared's internal IP.

### Fix
Cloudflare sets `CF-Connecting-IP` to the real visitor IP before tunneling. Updated `_get_client_ip()` in `generate.py` to check it first:

```
Priority: CF-Connecting-IP → X-Forwarded-For → X-Real-IP → request.client.host
```

### Verification
```sql
SELECT DISTINCT ip_address FROM generations ORDER BY ip_address;
-- Before fix: 10.42.0.37, 10.42.0.61, 10.42.0.78 (all internal)
-- After fix: should show real public IPs
```

## Analytics queries

All data comes from the `generations` table (written on every successful `/api/generate` call). Connect via:

```bash
kubectl exec -it deploy/postgres -- psql -U smi sketchmyinfra
# For prod namespace:
kubectl exec -it deploy/postgres -n prod -- psql -U smi sketchmyinfra
```

### Volume

```sql
-- Total generations ever
SELECT count(*) FROM generations;

-- Generations today
SELECT count(*) FROM generations WHERE created_at >= now() - interval '24 hours';

-- Generations per day (last 7 days)
SELECT created_at::date AS day, count(*)
FROM generations
GROUP BY day ORDER BY day DESC LIMIT 7;
```

### Unique visitors

```sql
-- Unique IPs per day (how many distinct visitors actually generated)
SELECT created_at::date AS day, count(DISTINCT ip_address) AS unique_visitors, count(*) AS total
FROM generations
GROUP BY day ORDER BY day DESC LIMIT 7;
```

### User breakdown

```sql
-- Logged-in vs anonymous split
SELECT
  CASE WHEN user_id IS NOT NULL THEN 'logged_in' ELSE 'anonymous' END AS user_type,
  count(*)
FROM generations
GROUP BY user_type;

-- Registered users
SELECT count(*) FROM users;

-- Users who actually generated something
SELECT count(DISTINCT user_id) FROM generations WHERE user_id IS NOT NULL;
```

### Content insights

```sql
-- Top prompts (what are people asking for?)
SELECT LEFT(prompt, 80) AS prompt_preview, count(*)
FROM generations
GROUP BY prompt_preview ORDER BY count DESC LIMIT 10;
```

### Rate limit monitoring

```sql
-- Users close to their daily limit
SELECT user_id, count(*) AS today_count
FROM generations
WHERE user_id IS NOT NULL AND created_at >= now() - interval '24 hours'
GROUP BY user_id
HAVING count(*) >= 4
ORDER BY today_count DESC;

-- Anonymous IPs close to limit
SELECT ip_address, count(*) AS today_count
FROM generations
WHERE user_id IS NULL AND created_at >= now() - interval '24 hours'
GROUP BY ip_address
HAVING count(*) >= 2
ORDER BY today_count DESC;
```

## Deployment gotcha

Image name mismatch when building:
```bash
# WRONG — k8s deployment uses sketchmyinfra-api:local
docker build -t sketchmyinfra-backend:local backend/

# RIGHT
docker build -t sketchmyinfra-api:local backend/
```

The k3s containerd image store uses the exact tag name. If the tag doesn't match the deployment's `image:` field, the rollout restart silently uses the old cached image. Always double-check the tag matches `k8s/api.yaml`.

## Key takeaways

- **Cloudflare Tunnel requires `CF-Connecting-IP`** — standard `X-Forwarded-For` only contains the cloudflared pod's internal IP. This is Cloudflare-specific behavior; other reverse proxies (nginx, HAProxy) do set XFF correctly.
- **The `generations` table is your analytics database** — no need for Mixpanel or Amplitude at this stage. SQL queries against one table give you volume, visitors, conversion, and content insights.
- **Always verify the Docker image tag matches the k8s manifest** — a typo in the tag means your deploy is a no-op but looks successful.

## Next steps

- [ ] Verify `CF-Connecting-IP` is producing real public IPs after deploy
- [ ] Set up a simple daily analytics cron or dashboard (even a bash script piped to Slack)
- [ ] Consider adding a `GET /api/stats` admin endpoint for quick checks without psql
