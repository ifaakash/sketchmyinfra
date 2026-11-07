# Incident pipeline: Prometheus → Alertmanager → Dispatcher → k8s agent → PR

How a production failure becomes a Telegram page and, eventually, an AI-generated fix PR. Covers how to
**check** and **trigger** each hop, the tests run so far, and the remaining plan.

Related: `dispatcher/README.md` (dispatcher setup and config), `k8s/agent/` (cluster manifests),
`monitoring/` (Prometheus + Alertmanager).

---

## 1. The flow

```
 user request fails
        │
        ▼
 api  ── exposes /metrics (smi_generations_total, http_requests_total)   [internal only, not via nginx]
        │  pull, every 15s
        ▼
 Prometheus ── evaluates alerts.yml rules ── Inactive → Pending (for:) → Firing
        │  push
        ▼
 Alertmanager ── groups (group_wait 30s), routes by labels
        ├──────────────► Telegram               (you get paged)
        └── agent="true" ► webhook POST /alert ──► dispatcher (compose)
                                                     │ token check → filter → busy/cooldown guard
                                                     │ evidence: DB rows (read-only role) + api logs (socket proxy)
                                                     ▼
                                              k3s namespace `agent`
                                              Job + incident ConfigMap
                                                     │
                                                     ▼
                                              agent pod: clone → LLM → pytest → push fix/* → gh pr create
                                                     │
                                                     ▼
                                              PR for human review   (or a "not a code bug" diagnosis)
```

| Hop | Mechanism | Adds latency | Typical break |
|---|---|---|---|
| api → Prometheus | **Pull** scrape, 15s | ≤15s | Wrong target name; api down (`up == 0`) |
| Rule evaluation | `evaluation_interval` (default 1m) + `for:` | 1m + `for` | Rule syntax; window too short for low traffic |
| Prometheus → Alertmanager | **Push** via `alerting.alertmanagers` | seconds | Missing `alerting:` block (`activeAlertmanagers: []`) |
| Alertmanager → receivers | Routing tree, `group_wait` | 30s | Child routes swallowing the root receiver; bad bot token |
| Alertmanager → dispatcher | **Push** webhook + Bearer token | seconds | No route / no `agent="true"` label; token mismatch (401) |
| Dispatcher → k3s | k8s API with the `dispatcher` ServiceAccount | seconds | Kubeconfig server IP not in the k3s cert SANs; RBAC |
| Job → PR | Agent image | minutes | Image not in containerd; bad PAT; tests fail |

**Expected time from failure to page:** about 15s + 1m + `for` + 30s, so roughly 2 minutes for `GenerationFailuresSpike` (`for: 0`).

---

## 2. Check and trigger each hop

Replace `<pi>` with the Pi's Tailscale/LAN IP. Run `docker compose` commands from the repo root on the Pi.

### 2.1 API metrics
```bash
# Is the counter there? (from inside the container — /metrics is not exposed via nginx)
docker compose exec -T api python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())" | grep smi_

# Must NOT return metrics from outside
curl -s http://<pi>/metrics | grep -c smi_      # expect 0
```

### 2.2 Prometheus
```bash
P=http://<pi>:9090
curl -s $P/api/v1/targets        | python3 -m json.tool | grep -E '"job"|"health"|lastError'   # api: up
curl -s $P/api/v1/rules          | python3 -m json.tool | grep -E '"name"|"state"|"health"'
curl -s $P/api/v1/alerts         | python3 -m json.tool                                         # pending/firing now
curl -s $P/api/v1/alertmanagers  | python3 -m json.tool                                         # MUST list alertmanager:9093
curl -sG $P/api/v1/query --data-urlencode \
  'query=sum by (status) (increase(smi_generations_total{source="server"}[10m]))' | python3 -m json.tool

# Validate before reloading
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker exec prometheus promtool check rules  /etc/prometheus/alerts.yml
curl -X POST $P/-/reload                      # needs --web.enable-lifecycle (set in monitoring/prometheus/Dockerfile)
```

### 2.3 Trigger a real failure (whole pipeline)
```bash
# 1. Break Gemini in dev: set GEMINI_API_KEY=invalid in .env
#    `restart` does NOT re-read env_file; `up -d` recreates the container
docker compose up -d api

# 2. Generate 3 times (each one = gemini_error = +1 on the failure counter)
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://<pi>/api/generate \
    -H 'Content-Type: application/json' -d '{"prompt":"three tier web app on aws"}'
done                                          # expect 502 (Gemini error) x3

# 3. Watch: Prometheus alerts → Alertmanager → Telegram (+ dispatcher once wired)
# 4. Restore the key, `docker compose up -d api`; RESOLVED arrives after the 10m window
```
> **Gotcha:** the anonymous rate limit is **3/day per IP**, and failed generations count towards it. A 4th
> try returns 429, not 502. Raise `RATE_LIMIT_ANONYMOUS` in dev, or log in.

### 2.4 Alertmanager
```bash
A=http://<pi>:9093
docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml

# Dry-run routing: which receivers WOULD get this alert? No side effects.
docker exec alertmanager amtool config routes test \
  --config.file=/etc/alertmanager/alertmanager.yml alertname=GenerationFailuresSpike agent=true
# expect: agent-dispatcher,telegram-bot-notifications   (after Phase 3 wiring)

# Synthetic alert — skips Prometheus entirely. Proves Alertmanager → Telegram (→ dispatcher).
# Quote annotation values ('summary="..."'), otherwise amtool warns about the new matcher parser.
docker exec alertmanager amtool alert add alertname=TestAlert severity=warning \
  --annotation='summary="hello from amtool"' --alertmanager.url=http://localhost:9093
# Add agent=true to also exercise the dispatcher route. Use a NEW alertname per test:
# an existing alert group won't re-notify until repeat_interval (4h).

# Did delivery work? Per-integration counters on Alertmanager's own /metrics
curl -s $A/metrics | grep -E '^alertmanager_notifications_total|^alertmanager_notification_requests_failed_total'
# requests_failed{integration="webhook"} rising = dispatcher returning non-2xx (see its logs)
docker logs alertmanager 2>&1 | grep -E "Notify attempt failed|retry canceled" | tail -5

curl -s $A/api/v2/alerts | python3 -m json.tool          # what Alertmanager currently holds
curl -s $A/api/v2/status | python3 -m json.tool | head   # version + loaded config (secrets masked)

# Silence during maintenance
docker exec alertmanager amtool silence add alertname=GenerationFailuresSpike \
  --duration=1h --comment="planned work" --alertmanager.url=http://localhost:9093
```
> Alertmanager retries a failed webhook with backoff, then **gives up** ("notify retry canceled after N
> attempts"). After fixing the dispatcher, fire a new alert; the old one won't be resent for 4h.
>
> A synthetic alert passing does **not** prove Prometheus → Alertmanager. That's exactly how the missing
> `alerting:` block went unnoticed. Always run 2.3 once as well.

### 2.5 Dispatcher
No published port, so call it from inside the container:
```bash
D="docker compose -f docker-compose.dispatcher.yml"
$D ps                                                   # dispatcher: healthy
$D logs -f dispatcher                                   # Dispatched / Skipping / WARNING lines
$D logs --tail 80 dispatcher | grep -A12 ERROR          # k8s failures are logged at ERROR with a traceback
$D exec dispatcher env | grep -E "DISPATCH_MODE|AGENT_"  # what the RUNNING container uses

# Fake Alertmanager webhook
$D exec -T dispatcher python3 - "$(cat dispatcher/secrets/dispatcher_token)" <<'EOF'
import json, sys, urllib.request
body = json.dumps({"status": "firing", "alerts": [{"status": "firing",
        "labels": {"alertname": "GenerationFailuresSpike", "agent": "true"}}]}).encode()
req = urllib.request.Request("http://localhost:8080/alert", data=body,
        headers={"Authorization": f"Bearer {sys.argv[1]}", "Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
EOF
# 202 dispatched | 200 cooldown / busy / not-agent / resolved | 401 bad token | 503 k8s error

$D exec -T dispatcher python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/metrics').read().decode())" | grep smi_dispatcher
```

### 2.6 k8s agent Job
```bash
kubectl -n agent get jobs,cm,pods
kubectl -n agent get jobs -w                        # watch Jobs appear/complete (Ctrl-C to stop)
kubectl -n agent logs job/<name>                    # placeholder prints the incident JSON
kubectl -n agent logs -f job/<name>                 # follow a running agent
kubectl -n agent get jobs --sort-by=.metadata.creationTimestamp -o name | tail -1   # newest Job
kubectl -n agent describe job/<name>                # events: image pull, PSA rejections, deadline
kubectl -n agent get cm <name>-incident -o jsonpath='{.data.incident\.json}'

# RBAC boundaries of the dispatcher identity
SA=system:serviceaccount:agent:dispatcher
kubectl auth can-i create jobs   -n agent   --as=$SA    # yes
kubectl auth can-i get secrets   -n agent   --as=$SA    # no
kubectl auth can-i create jobs   -n default --as=$SA    # no
```

---

## 3. Test log (what has been verified)

| Date | What | How | Result |
|---|---|---|---|
| 2026-11-06 | Backend metrics (#59) | `pytest` in `python:3.12-slim` | 111 passed / 17 skipped; `test_metrics.py` 5/5 |
| 2026-11-06 | `/metrics` stays internal | `curl http://localhost/metrics` via nginx | Frontend HTML, 0 metric lines ✅ |
| 2026-11-06 | Alertmanager → Telegram | Synthetic alert (Alertmanager UI / `amtool alert add`) | Telegram message received ✅ |
| 2026-11-07 | Live stack over Tailscale | `/api/v1/targets`, `/rules`, `/alertmanagers`, `/api/v2/status` | api UP, 4 rules OK, retention `4d or 1GiB`, **`activeAlertmanagers: []`** ❌, so a real alert would never page. Fixed in `66c0feb` |
| 2026-11-07 | Dispatcher unit tests | `pytest` (33 tests) | 33 passed |
| 2026-11-07 | Dispatcher dry-run | Fake webhook ×2, then no token | `202 dispatched`, `200 cooldown`, `401` ✅; metrics counted |
| 2026-11-07 | Socket proxy is read-only | `GET` logs vs `POST /containers/x/stop`, `GET /images/json` | Logs ✅; stop **403**; images **403** |
| 2026-11-07 | Manifests on real k8s | Throwaway `rancher/k3s:v1.31.4-k3s1` in Docker, `kubectl apply -f k8s/agent/` | Applied after the namespace-ordering fix |
| 2026-11-07 | Dispatcher RBAC | `kubectl auth can-i ... --as=$SA` | create/list jobs, create cm: yes; delete pods, get secrets, other ns, create pods: **no** ✅ |
| 2026-11-07 | k8s mode end to end | Dispatcher → throwaway k3s with busybox placeholder | Job Complete under PSA `restricted`; incident printed with token redacted; ConfigMap owned by Job; 2nd alert `busy` ✅ |
| 2026-11-07 | Pod Security | `kubectl run` a privileged pod in `agent` | Forbidden by PSA `restricted` ✅ |
| 2026-11-07 | NetworkPolicy | curl from a pod labelled `app=smi-agent` | api.github.com 200; k8s API / 10.43.0.1 / port 80 blocked ✅ |
| 2026-11-07 | Compose service (#64) | `compose up --build`, fake webhook, `touch /` | healthy; 202/200; uid 10001; read-only FS ✅ |
| 2026-11-07 | Phase 3 config live on the Pi (#67) | `/api/v1/targets`, `/api/v1/rules`, `amtool config routes test`, `/api/v2/status` | api + dispatcher targets up; 7 rules, `agent=true` on 3; `agent=true` → dispatcher + Telegram; `bot_token_file` ✅ |
| 2026-11-07 | Drill A1: Alertmanager → dispatcher → k3s | `amtool alert add alertname=DrillTest agent=true` | Telegram ✅; webhook delivered ✅; dispatcher **503 ×4**: `No route to host` to `192.168.1.50:6443` ❌; **`DispatcherErrors` fired to Telegram** (self-monitoring works) ✅ |
| 2026-11-07 | Drill A2 after kubeconfig fix | `amtool alert add alertname=DrillTest2 agent=true` | `Dispatched`; Job `agent-drilltest2-...` Complete in 11s ✅ |

**Bugs found by testing (all fixed):**
- `kubectl apply -f dir/` applies files alphabetically, so `agent-sa.yaml` ran before the namespace existed. Renamed to `00-namespace.yaml`.
- `secret.example.yaml` would have been applied by `kubectl apply -f k8s/agent/`. Renamed to `secret.yaml.example`.
- `kubernetes==37.0.2` needs `PyYAML>=6.0.3`, so the 6.0.2 pin made pip resolution impossible.
- Pi kubeconfig pointed at `192.168.1.50`, the example IP from the script's usage line, not the Pi
  (`192.168.1.6`), giving `No route to host`. The script now uses a `<pi-ip>` placeholder.
- Compose draft: `environments`, scalar `networks`, `src: dst` volume maps, and empty keys. Also, with no `name:`, it shared the app's project, so `--remove-orphans` could delete app containers.

---

## 4. Why Prometheus needs a `dispatcher` scrape job

Two different directions of traffic are easy to mix up:

| | Direction | Purpose |
|---|---|---|
| Alertmanager webhook → dispatcher `/alert` | **Push** | How alerts *reach* the dispatcher. Configured in `alertmanager.yml`, not `prometheus.yml` |
| Prometheus → dispatcher `/metrics` | **Pull** | How you *monitor the dispatcher itself* |

Prometheus only knows about targets listed in `scrape_configs`. Without a `dispatcher` job:
- If the dispatcher crashes, nobody notices. Alerts still reach Telegram, but no agent ever runs. **The automation fails silently.**
- `smi_dispatcher_alerts_total{result}` is invisible. You can't see `error` (k8s/TLS/RBAC broken), `unauthorized` (Alertmanager token mismatch) or how often `cooldown`/`busy` drop incidents.

This is the "who watches the watcher" rule: every automated responder needs its own health signal.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: dispatcher
    static_configs:
      - targets: ['dispatcher:8080']       # service name on smi-network
```
```yaml
# alerts.yml — NO agent="true" on these: a broken dispatcher can't dispatch its own fix
- alert: DispatcherDown
  expr: up{job="dispatcher"} == 0
  for: 2m
- alert: DispatcherErrors
  expr: increase(smi_dispatcher_alerts_total{result="error"}[15m]) > 0
- alert: DispatcherUnauthorized
  expr: increase(smi_dispatcher_alerts_total{result="unauthorized"}[15m]) > 0
```

---

## 5. Current state (on the Pi, 2026-11-07)

| Item | State |
|---|---|
| Backend metrics, `/metrics` internal-only | ✅ |
| Prometheus: targets `api:8000` + `dispatcher:8080`, 7 rules, 4d / 1GB retention | ✅ (#67) |
| Prometheus → Alertmanager | ✅ |
| Alertmanager → Telegram (`bot_token_file`) | ✅ (#67) |
| Alertmanager → dispatcher (`agent="true"` route, shared token) | ✅ (#67, drill A2) |
| Dispatcher → k3s (`DISPATCH_MODE=k8s`, kubeconfig → `192.168.1.6:6443`) | ✅ (drill A2: Job Complete) |
| Dispatcher self-alerts | ✅ (`DispatcherErrors` fired during drill A1) |
| Read-only DB role / `dispatcher.env` | ❓ verify `failed_generations` in the incident (not in `evidence_errors`) |
| Real-failure drill from Prometheus (§2.3) | ⏳ next |
| `prom/alertmanager:latest`, unpinned Prometheus | ⚠️ pin (running: Alertmanager 0.34.2, Prometheus 3.16.0) |
| 9090/9093 published on 0.0.0.0 | ⚠️ bind to `127.0.0.1` or the Tailscale IP (Alertmanager has no auth, so anyone on the LAN can silence) |
| Agent image | ❌ Phase 4 |

---|---|
| Backend metrics, `/metrics` internal-only | ✅ |
| Prometheus scraping api, 4 rules, 4d / 1GB retention | ✅ |
| Prometheus → Alertmanager (`alerting:` block) | ✅ (`66c0feb`), re-verify with `/api/v1/alertmanagers` |
| Alertmanager → Telegram | ✅ |
| Dispatcher code, k8s manifests, compose service | ✅ (#60, #64) |
| Scrape target uses the container name `sketchmyinfra-api-1` | ⚠️ use service name `api:8000` |
| No `dispatcher` scrape job or dispatcher self-alerts | ❌ (§4) |
| No Alertmanager webhook route to the dispatcher | ❌ |
| No `agent: "true"` labels; no `annotations` on rules | ❌ |
| Telegram `bot_token: ''` in git | ⚠️ move to `bot_token_file` + gitignored secret |
| `prom/alertmanager:latest`, unpinned Prometheus | ⚠️ pin (running: Alertmanager 0.34.2, Prometheus 3.16.0) |
| 9090/9093 published on 0.0.0.0 | ⚠️ bind to `127.0.0.1` or the Tailscale IP (Alertmanager has no auth, so anyone on the LAN can silence) |
| Agent image | ❌ Phase 4 |

---

## 6. Remaining plan

### Phase 3: Wire it together (config only)
✅ done · ◐ partial (`bot_token_file` done; pin tags + bind ports left) · ❓ unverified · ⏳ next
| # | Step | ✅ Check |
|---|---|---|
| 3.1 ✅ | On the Pi: `kubectl apply -f k8s/agent/` | `kubectl -n agent get sa,role,rolebinding,netpol` |
| 3.2 ✅ | Dispatcher secrets: `openssl rand -hex 32 > dispatcher/secrets/dispatcher_token`; `dispatcher/scripts/make-kubeconfig.sh https://<pi-ip>:6443 > dispatcher/secrets/kubeconfig`; `chmod 644 dispatcher/secrets/*` | The IP is in the k3s cert SANs (script header) |
| 3.3 ❓ | Read-only DB role (SQL in `dispatcher/README.md` §3) + `dispatcher/secrets/dispatcher.env` from `dispatcher/dispatcher.env.example` | `psql` as `smi_dispatcher`: `SELECT prompt FROM generations` → permission denied |
| 3.4 ✅ | `docker compose -f docker-compose.dispatcher.yml up -d --build` (dry-run) | §2.5 fake webhook → 202; `api_logs` / `failed_generations` populated |
| 3.5 ✅ | `DISPATCH_MODE=k8s docker compose -f docker-compose.dispatcher.yml up -d` | §2.5 again → Job in `agent`; `kubectl logs` prints the incident |
| 3.6 ✅ | Alertmanager: `agent-dispatcher` webhook receiver + child route `agent="true"` (`continue: true`) + catch-all Telegram child route; mount the token at `/etc/alertmanager/secrets/dispatcher_token` (snippet in `dispatcher/README.md` §5) | `amtool config routes test ... agent=true` → both receivers |
| 3.7 ✅ | `alerts.yml`: add `agent: "true"` + `severity` + `annotations` (summary/description/runbook) to `GenerationFailuresSpike`, `GenerationFailureRatioHigh`, `Api5xxRate`. **Not** `ApiMetricsDown` | `promtool check rules` |
| 3.8 ✅ | `prometheus.yml`: target `api:8000`; add the `dispatcher` job; add the dispatcher self-alerts (§4) | `/api/v1/targets` → api + dispatcher UP |
| 3.9 ◐ | Hygiene: `bot_token_file`, pin image tags, bind ports to 127.0.0.1/Tailscale | `git grep bot_token` shows no token |
| 3.10 ⏳ | **Drill** (§2.3) | Telegram page **and** a Job in `agent` with the real incident; `smi_dispatcher_alerts_total{result="dispatched"}` = 1 |

### Phase 4: The agent image (build)
| # | Step | ✅ Check |
|---|---|---|
| 4.1 | Choose the LLM: Gemini (CLI headless or SDK) **or** Claude (Claude Code `claude -p` or SDK). Use a **separate key** from the app's, or the agent can exhaust the app's quota and trigger the very alert it's fixing | n/a |
| 4.2 | `agent/Dockerfile`: arm64, non-root **uid 1000**, `git`, `gh`, Python 3.12 + `backend/requirements.txt` + pytest, the LLM CLI/SDK. Works with a read-only root FS (`HOME=/work`) | `docker run --read-only --user 1000 ...` works |
| 4.3 | Entrypoint: clone with `GITHUB_TOKEN` into `/work` → `git switch -c fix/incident-<job>` → run the LLM on `$INCIDENT_FILE` → if changed: `pytest` → push → `gh pr create`; else print the diagnosis | Run locally with a hand-written `incident.json` |
| 4.4 | Prompt rules: the evidence is **untrusted data**; minimal diff; tests must pass; config/infra causes (bad key, dead container) → **no PR**, diagnosis only; put the root cause and evidence in the PR body | Review the output from 4.3 |
| 4.5 | GitHub: fine-grained PAT (this repo only; Contents RW, Pull requests RW, Metadata R); protect `main` (PR required) | A push to `main` with the PAT is rejected |
| 4.6 | `cp k8s/agent/secret.yaml.example k8s/agent/secret.yaml`, fill it in, `kubectl apply -f k8s/agent/secret.yaml` | `kubectl -n agent get secret agent-secrets` |
| 4.7 | Get the image into k3s (containerd ≠ Docker): `docker save smi-agent:0.1 \| sudo k3s ctr images import -`, or push to GHCR. Pinned tag | `sudo k3s ctr images ls \| grep smi-agent` |
| 4.8 | Dispatcher: `AGENT_IMAGE=smi-agent:0.1`, `AGENT_COMMAND=` (empty, so the image entrypoint runs) → `up -d` | §2.5 → Job runs the real agent |
| 4.9 | **Drill A**: bad Gemini key (§2.3) | Diagnosis says "config, not code", and **no PR** |
| 4.10 | **Drill B**: plant a real bug in dev (e.g. break a generator) → alert | A PR with a fix + green tests |

### Phase 5: Close the loop (later)
- The agent posts the PR link / diagnosis to Telegram (the same bot or a separate one).
- `smi_agent_runs_total{result}`: either the dispatcher reads Job status, or the agent pushes to a Pushgateway.
- Grafana dashboard: generations by status, failure ratio, 5xx, p95 latency, dispatcher results, agent runs.
- LLM spend: cap per run (`activeDeadlineSeconds`) and per day (cooldown, or a daily max in the dispatcher).
- Loki + Promtail for log history beyond `docker logs`.

---

## 7. Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| Alert **Firing** in Prometheus, nothing in Alertmanager | No `alerting:` block, or Alertmanager unreachable | `curl $P/api/v1/alertmanagers` |
| Telegram works with `amtool`, but real failures never page | Same as above; a synthetic alert skips Prometheus | §2.3 drill |
| Telegram gets the alert, no Job | No webhook route / no `agent="true"` label / token mismatch | `amtool config routes test`; dispatcher logs; `smi_dispatcher_alerts_total{result="unauthorized"}` |
| Dispatcher `401` | Token file differs between Alertmanager and the dispatcher, or isn't readable by uid 10001 | `sha256sum` both files; `chmod 644` |
| Dispatcher `503`, `No route to host` / `Connection refused` | Wrong IP in the kubeconfig `server:` (e.g. the example IP), or a firewall blocking Docker → host:6443 | `grep server: dispatcher/secrets/kubeconfig`; `$D exec dispatcher python3 -c "import socket; socket.create_connection(('<pi-ip>', 6443), 3)"` |
| Fixed the dispatcher, but the old alert never arrives | Alertmanager gave up ("retry canceled") and won't resend that group until `repeat_interval` (4h) | Fire a test alert with a new `alertname` |
| Changed the kubeconfig, still failing | The dispatcher caches its k8s client after the first request | `$D restart dispatcher` |
| `export DISPATCH_MODE=k8s` had no effect | Shell variables are only read when compose **creates** the container | `DISPATCH_MODE=k8s $D up -d`; check with `$D exec dispatcher env` |
| Dispatcher `503`, TLS error in logs | The kubeconfig server address isn't in the k3s cert SANs | `openssl s_client -connect <ip>:6443 </dev/null \| openssl x509 -noout -ext subjectAltName` |
| `200 cooldown` / `busy` when you expected a Job | A Job for this alert in the last hour, or one still running | `kubectl -n agent get jobs` |
| Job stuck `ContainerCreating` | Incident ConfigMap missing, or the image isn't in containerd | `kubectl -n agent describe pod ...` |
| Job rejected / no pod | PSA `restricted`: image runs as root, or missing securityContext | `kubectl -n agent describe job ...` (events) |
| `api_logs` empty | The api logged nothing in the window (normal when idle), or the proxy is unreachable | `evidence_errors` in the incident; `docker logs --since 30m <api>` |
| `failed_generations` error | `EVIDENCE_DATABASE_URL` unset, or the role lacks a column grant | `evidence_errors` in the incident |
| A secret file mount turned into a directory | The file didn't exist at `up` time | Create the file, `rm -r` the directory, `up -d` |

---

## 8. Cheat sheet (debugging + simulating)

```bash
P=http://localhost:9090; A=http://localhost:9093          # on the Pi
D="docker compose -f docker-compose.dispatcher.yml"
M="docker compose -f monitoring/docker-compose.monitoring.yml"
```

### Simulate, from cheapest to most realistic
| Level | Command | Exercises |
|---|---|---|
| Dispatcher only | Fake webhook (§2.5) | token, guards, evidence, Job creation |
| Alertmanager onward | `docker exec alertmanager amtool alert add alertname=Drill$(date +%s) agent=true severity=warning --annotation='summary="drill"' --alertmanager.url=http://localhost:9093` | routing, Telegram, webhook token, dispatcher, k3s |
| Telegram only | Same, **without** `agent=true` | Telegram receiver |
| Whole pipeline | Bad `GEMINI_API_KEY` + 3× generate (§2.3) | metrics, rules, `for:`, everything |

`Drill$(date +%s)` gives a unique alertname, so you never hit the 4h repeat or the 1h dispatcher cooldown.

### Is it healthy?
```bash
curl -s $P/api/v1/targets | python3 -c "import sys,json; [print(t['labels']['job'], t['health'], t.get('lastError','')) for t in json.load(sys.stdin)['data']['activeTargets']]"
curl -s $P/api/v1/rules   | python3 -c "import sys,json; [print(r['name'], r['state'], r.get('labels',{}).get('agent','-')) for g in json.load(sys.stdin)['data']['groups'] for r in g['rules']]"
curl -s $P/api/v1/alertmanagers | grep -o 'http://[^"]*'                    # must not be empty
curl -s $A/api/v2/alerts | python3 -c "import sys,json; [print(a['labels'].get('alertname'), a['status']['state'], [r['name'] for r in a['receivers']]) for a in json.load(sys.stdin)]"
curl -sG $P/api/v1/query --data-urlencode 'query=smi_dispatcher_alerts_total' | python3 -m json.tool | grep -E '"result"|"[0-9.]+"$'
$D ps; $M ps
```
> `grep -c` counts **lines**, and the Prometheus API returns one-line JSON, so `grep -c` prints `1` for any number
> of matches. Use `grep -o ... | wc -l` or the Python one-liners above.

### Where did it stop?
```bash
docker logs alertmanager 2>&1 | grep -E "Notify attempt failed|retry canceled" | tail -5   # AM → receivers
curl -s $A/metrics | grep -E '^alertmanager_notification_requests_failed_total'
$D logs --tail 80 dispatcher | grep -E "Dispatched|Skipping|POST /alert|ERROR"
$D logs --tail 80 dispatcher | grep -A12 ERROR
kubectl -n agent get jobs,pods
kubectl -n agent describe job/<name> | tail -20                                           # events
kubectl -n agent logs job/<name>
```

### Validate config before reloading
```bash
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
docker exec alertmanager amtool config routes test --config.file=/etc/alertmanager/alertmanager.yml alertname=X agent=true
curl -X POST $P/-/reload                                       # Prometheus config/rules
$M up -d --force-recreate alertmanager                         # Alertmanager config or mounts changed
```

### k3s connectivity (dispatcher → API)
```bash
grep server: dispatcher/secrets/kubeconfig
echo | openssl s_client -connect <pi-ip>:6443 2>/dev/null | openssl x509 -noout -ext subjectAltName   # IP must be listed
$D exec dispatcher python3 -c "import socket; socket.create_connection(('<pi-ip>', 6443), 3); print('ok')"
dispatcher/scripts/make-kubeconfig.sh https://<pi-ip>:6443 > dispatcher/secrets/kubeconfig && chmod 644 dispatcher/secrets/kubeconfig
$D restart dispatcher                                           # client is cached
kubectl auth can-i create jobs -n agent --as=system:serviceaccount:agent:dispatcher
```

### Reset / clean up
```bash
kubectl -n agent delete job <name>                              # also deletes its ConfigMap (ownerReference); clears that alert's cooldown
kubectl -n agent delete jobs -l app=smi-agent                   # all agent Jobs
docker exec alertmanager amtool alert query --alertmanager.url=http://localhost:9093
docker exec alertmanager amtool silence add alertname=<name> --duration=1h --comment="testing" --alertmanager.url=http://localhost:9093
docker exec alertmanager amtool silence expire $(docker exec alertmanager amtool silence query -q --alertmanager.url=http://localhost:9093) --alertmanager.url=http://localhost:9093
```
