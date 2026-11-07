# Agent Dispatcher

Always-on service between **Alertmanager** and **k3s**. When a code-related alert fires, it collects
evidence (failed generations + api logs), then launches a one-shot **agent Job** in the `agent`
namespace. The agent (built separately) clones the repo, fixes the bug and opens a PR.

End-to-end flow, test commands for every hop, and the remaining plan: [`docs/incident-pipeline.md`](../docs/incident-pipeline.md).

```
Alertmanager --POST /alert (Bearer)--> dispatcher (compose)
   1. keep firing alerts labelled agent="true"
   2. guard: max 1 running agent Job, 1h cooldown per alertname   (state = Jobs in k3s)
   3. evidence: DB (read-only, no prompts/IPs) + api logs (read-only socket proxy), redacted, <=200KB
   4. create Job agent-<alert>-<ts> + ConfigMap <job>-incident (owned by the Job)
```

| Endpoint | Purpose |
|---|---|
| `POST /alert` | Alertmanager webhook. `202` dispatched · `200` skipped (`resolved`/`not-agent`/`cooldown`/`busy`) · `401` bad token · `503` k8s error (Alertmanager retries) |
| `GET /healthz` | Liveness, no auth |
| `GET /metrics` | `smi_dispatcher_alerts_total{result}` |

## Setup on the Pi (in order)

### 1. k8s side
```bash
kubectl apply -f k8s/agent/          # namespace (PSA restricted), RBAC, agent SA, NetworkPolicy
cp k8s/agent/secret.yaml.example k8s/agent/secret.yaml   # only needed once the real agent image exists
```
Check the RBAC boundaries:
```bash
SA=system:serviceaccount:agent:dispatcher
kubectl auth can-i create jobs   -n agent   --as=$SA   # yes
kubectl auth can-i get secrets   -n agent   --as=$SA   # no
kubectl auth can-i create jobs   -n default --as=$SA   # no
```

### 2. Dispatcher secrets (`dispatcher/secrets/`, gitignored)
```bash
mkdir -p dispatcher/secrets
openssl rand -hex 32 > dispatcher/secrets/dispatcher_token          # shared with Alertmanager
dispatcher/scripts/make-kubeconfig.sh https://<pi-lan-or-tailscale-ip>:6443 > dispatcher/secrets/kubeconfig
```
**Gotcha:** the server URL must be in the k3s API cert's SANs. `127.0.0.1` inside a container is the
container itself, and `host.docker.internal` isn't in the cert. The script header shows how to check the SANs.

### 3. Read-only DB role
Column-level grant, so the **database itself** stops the dispatcher from reading prompts, IPs or user ids:
```bash
docker compose exec db psql -U smi -d sketchmyinfra
```
```sql
CREATE ROLE smi_dispatcher LOGIN PASSWORD '<random>';
GRANT CONNECT ON DATABASE sketchmyinfra TO smi_dispatcher;
GRANT USAGE ON SCHEMA public TO smi_dispatcher;
GRANT SELECT (created_at, status, renderer, category, error_message, puml_code)
  ON generations TO smi_dispatcher;
```

### 4. Compose services
Defined in `docker-compose.dispatcher.yml` (its own project, `smi-dispatcher`, on `smi-network`):
`docker-proxy` (read-only Docker API: logs yes; stop/exec/images → 403) and `dispatcher`
(read-only FS, all caps dropped, `/healthz` healthcheck, starts in `dry-run`).
```bash
cp dispatcher/dispatcher.env.example dispatcher/secrets/dispatcher.env   # optional: DB evidence
chmod 644 dispatcher/secrets/*            # files are read as uid 10001
docker compose -f docker-compose.dispatcher.yml up -d --build
DISPATCH_MODE=k8s docker compose -f docker-compose.dispatcher.yml up -d   # once the kubeconfig works
```
Both secret files must exist before `up`. Otherwise Docker creates an empty *directory* in their place.

### 5. Alertmanager wiring
Add a child route that matches `agent="true"` and sends it to the webhook, with `continue: true` so
Telegram still gets it. **Gotcha:** once a route has children, the root receiver is only used when *no*
child matches. A matching child with `continue: true` falls through to its *siblings*, not to the
root, so add an explicit catch-all Telegram child after it.
```yaml
route:
  receiver: telegram-bot-notifications
  routes:
    - matchers: ['agent="true"']
      receiver: agent-dispatcher
      continue: true
    - receiver: telegram-bot-notifications

receivers:
  - name: agent-dispatcher
    webhook_configs:
      - url: http://dispatcher:8080/alert
        send_resolved: false
        http_config:
          authorization:
            credentials_file: /etc/alertmanager/secrets/dispatcher_token
```
Mount the same `dispatcher_token` into the alertmanager container.

### 6. Alert rules + scrape
- Add `agent: "true"` under `labels:` for `GenerationFailuresSpike`, `GenerationFailureRatioHigh` and `Api5xxRate`.
  **Not** on `ApiMetricsDown`, because a dead container isn't a code bug.
- Prometheus: add scrape job `dispatcher` → `dispatcher:8080`.

## Configuration (env vars)
| Var | Default | Notes |
|---|---|---|
| `DISPATCH_MODE` | `dry-run` | `k8s` to create real Jobs; `dry-run` logs the manifests |
| `DISPATCHER_TOKEN_FILE` | `/run/secrets/dispatcher_token` | Missing or empty means every request gets 401 (fail closed) |
| `KUBECONFIG` | `/run/secrets/kubeconfig` | |
| `AGENT_IMAGE` | `busybox:1.37` | Placeholder until the agent image exists |
| `AGENT_COMMAND` | `[]` (image entrypoint) | JSON list, e.g. `["cat","/incident/incident.json"]` for the placeholder |
| `AGENT_NAMESPACE` / `AGENT_SERVICE_ACCOUNT` / `AGENT_SECRET_NAME` | `agent` / `agent` / `agent-secrets` | |
| `AGENT_RUN_AS_USER` | `1000` | Required: the namespace enforces non-root |
| `JOB_DEADLINE_SECONDS` / `JOB_TTL_SECONDS` | `900` / `86400` | Kill after 15m, keep finished Jobs 1 day (cooldown reads them) |
| `COOLDOWN_SECONDS` / `MAX_ACTIVE_JOBS` | `3600` / `1` | |
| `DOCKER_HOST` | n/a | `tcp://docker-proxy:2375` |
| `API_SERVICE_NAME` | `api` | Container is found by the `com.docker.compose.service` label |
| `EVIDENCE_DATABASE_URL` | empty (skip) | `postgresql://smi_dispatcher:<pw>@db:5432/sketchmyinfra` |
| `EVIDENCE_WINDOW_MINUTES` / `FAILED_ROWS_LIMIT` / `LOG_TAIL` / `EVIDENCE_MAX_BYTES` | `30` / `20` / `300` / `200000` | |

## What the agent receives
- `/incident/incident.json`: alert labels/annotations, failed generations, api logs, `evidence_errors`,
  `truncated`, and a `_note` marking it as **untrusted data**. Error messages can echo user text, so the
  agent must treat it as data, never as instructions.
- env: `INCIDENT_FILE`, `WORK_DIR=/work`, `HOME=/work`, plus everything in the `agent-secrets` Secret.
- Writable paths: only `/work` (2Gi) and `/tmp`. The root FS is read-only.
- Network: DNS + TCP 443 to public IPs only (no LAN, cluster, Tailscale or metadata).

## Test
```bash
# unit tests (prod-matching interpreter)
cd dispatcher && docker run --rm -v "$PWD":/src:ro -w /work python:3.12-slim \
  sh -c "cp -r /src/. /work && pip install -q -r requirements-dev.txt && python -m pytest -q"

# fake alert against a running dispatcher
curl -s -H "Authorization: Bearer $(cat dispatcher/secrets/dispatcher_token)" \
  -H 'Content-Type: application/json' localhost:8080/alert \
  -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"GenerationFailuresSpike","agent":"true"}}]}'

kubectl -n agent get jobs,cm,pods
kubectl -n agent logs job/<name>        # placeholder prints the incident
```
