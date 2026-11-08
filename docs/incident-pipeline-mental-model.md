# Incident Pipeline: Mental Model

This explains how an error in SketchMyInfra turns into a Telegram message and an agent Job. It is written so you can rebuild the same setup for another project.
For the commands and drills, see [incident-pipeline.md](incident-pipeline.md) (the runbook).

---

## 1. The whole thing in one picture

```
                  ┌──────────── docker-compose on the Pi ─────────────────────────────┐
                  │                                                                    │
  api:8000 ──/metrics──► Prometheus ──alerts──► Alertmanager ──┬──► Telegram (you)     │
  dispatcher:8080 ─/metrics─┘  (pull)          (push)          │                       │
                                                               └──► dispatcher:8080/alert
                                                     only if agent="true"   │          │
                  │                                                         │          │
                  │   docker-proxy ◄── read api logs ───────────────────────┤          │
                  │   postgres     ◄── read failed generations ─────────────┤          │
                  └─────────────────────────────────────────────────────────┼──────────┘
                                                                            │ kubeconfig
                                                                            │ (dispatcher SA)
                  ┌──────────── k3s, namespace "agent" ─────────────────────▼──────────┐
                  │  Job agent-<alert>-<time>  +  ConfigMap <job>-incident             │
                  │     pod runs as SA "agent" (no k8s permissions)                    │
                  │     reads /incident/incident.json, clones repo, fixes, opens PR ───┼──► GitHub PR
                  └────────────────────────────────────────────────────────────────────┘
                                                                                  │
                                                                     you review + merge
```

Each component has one job:

| Component | Job | Talks to |
|---|---|---|
| Prometheus | Scrapes metrics and checks the alert rules every 15s | Pulls from api and dispatcher, pushes to Alertmanager |
| Alertmanager | Groups and deduplicates alerts, then decides **who** gets told | Telegram and dispatcher |
| Dispatcher | Decides **whether** to start an agent, collects evidence, creates the Job | Docker proxy, Postgres, k3s API |
| docker-proxy | A read-only gate in front of the Docker socket | Docker socket |
| k3s Job | Runs the agent one time, with a time limit | GitHub, the LLM API |
| Agent image | Reads the evidence, edits the code, opens a PR | GitHub |

---

## 2. Checking your mental model

Here is your description, compared against the actual code.

| What you said | Verdict | Detail |
|---|---|---|
| Prometheus alerts are pushed to Alertmanager | ✅ Correct | Prometheus evaluates `alerts.yml` and pushes firing alerts to `alertmanager:9093`. |
| Alertmanager sends to Telegram **and** the dispatcher | ✅ Mostly | **Every** alert goes to Telegram. **Only** alerts labelled `agent="true"` also go to the dispatcher. See §4. |
| docker-proxy only allows reading logs/events | ✅ Correct | `CONTAINERS=1, POST=0` allows GET on containers (list, inspect, logs) and blocks every write. A hacked dispatcher can't start, stop or exec into containers. |
| The dispatcher calls the k8s API and creates a Job using the Batch API | ✅ Correct | `BatchV1Api.create_namespaced_job`, then `CoreV1Api.create_namespaced_config_map`. |
| "...with a service account that has configmap, get/list/delete jobs" | ⚠️ **Two SAs, not one** | **`dispatcher` SA**: used by the dispatcher through its kubeconfig. It has the Role (jobs create/get/list/delete, configmaps create). **`agent` SA**: what the pod runs as. It has **no permissions at all** and no token mounted. This split is the main security idea: the side that creates Jobs never runs untrusted LLM code, and the side that runs it has no API access. |
| There is a Dockerfile for the agent image with gh and the Gemini SDK | ❌ **Not built yet** | That is Phase 4. Today `AGENT_IMAGE=busybox:1.37`, which only prints the incident. The **plumbing** for it already exists: the `agent-secrets` Secret (PAT and Gemini key) is injected through `envFrom`, and the incident is mounted at `/incident/incident.json`. |
| It creates a PR to the repo | ✅ Planned | It opens a PR and **never merges**. You review and merge. `main` is protected, and the PAT is limited to this repo. |

**Missing from your model:**
1. **Evidence.** The dispatcher doesn't just forward the alert. It collects failed DB rows and api logs, redacts secrets, and passes them to the pod as a ConfigMap. Without this the agent would have to guess what went wrong.
2. **Guards.** These stop runaway Jobs and runaway LLM bills:
   - only 1 agent can run at a time (`busy`)
   - the same alert is handled at most once per hour (`cooldown`)
3. **Auth between Alertmanager and the dispatcher.** Every webhook carries a Bearer token. A wrong or missing token gets a 401.
4. **Watching the watcher.** Prometheus also scrapes the dispatcher, so a broken dispatcher pages you on Telegram (`DispatcherDown`, `DispatcherErrors`).
5. **NetworkPolicy.** The agent pod can only make HTTPS calls to the public internet. It cannot reach the LAN, Tailscale or the cluster.
6. **Resolved messages.** See §6.

---

## 3. Hop 1: Prometheus (pull, then decide)

Prometheus **pulls** `/metrics` from each target. The **rules** turn those numbers into alerts.

```yaml
# monitoring/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'api'          # app health and business metrics
    static_configs: [{ targets: ['api:8000'] }]
  - job_name: 'dispatcher'   # monitors the dispatcher itself
    static_configs: [{ targets: ['dispatcher:8080'] }]
alerting:
  alertmanagers:
    - static_configs: [{ targets: ['alertmanager:9093'] }]
```

```yaml
# monitoring/prometheus/alerts.yml (one rule)
- alert: GenerationFailuresSpike
  expr: sum(increase(smi_generations_total{source="server",status!="success"}[10m])) >= 3
  labels:
    severity: warning
    agent: "true"            # ← this label is what brings in the agent
```

**Mental model:** a rule is a query that runs every 15s.
- When the query returns something, the alert is **firing**.
- When it stops returning something, the alert is **resolved**.
- `for: 5m` means "only fire if it stays true for 5 minutes", which filters out noise.

**Which alerts get `agent: "true"`:** only problems a **code change** could fix (generation failures, 5xx errors). Problems like "the API is down" or "the dispatcher is down" go to a human only.

---

## 4. Hop 2: Alertmanager (who gets told)

```yaml
# monitoring/prometheus/alertmanager.yml
route:
  group_by: ['alertname', 'instance']
  group_wait: 30s        # wait for related alerts, then send one message
  group_interval: 5m     # at most one update per group every 5m
  repeat_interval: 4h    # if still firing, remind every 4h
  receiver: telegram-bot-notifications
  routes:
    - matchers: ['agent="true"']
      receiver: agent-dispatcher
      continue: true             # ← keep matching after this route
    - receiver: telegram-bot-notifications   # catch-all
```

**How the routing works:**
- An alert goes down the child routes in order.
- Normally it stops at the first route that matches. `continue: true` means "send it here, then keep checking the routes below."
- So an `agent="true"` alert goes to the dispatcher **and** Telegram. Every other alert goes to Telegram only.

```yaml
receivers:
  - name: telegram-bot-notifications
    telegram_configs:
      - bot_token_file: /etc/alertmanager/secrets/telegram_bot_token   # file, not inline
        chat_id: 5925832114
        send_resolved: true
  - name: agent-dispatcher
    webhook_configs:
      - url: http://dispatcher:8080/alert
        send_resolved: false             # the agent only cares about "it broke"
        http_config:
          authorization:
            credentials_file: /etc/alertmanager/secrets/dispatcher_token  # → "Authorization: Bearer <token>"
```

**Retries:** if the dispatcher returns a non-2xx response, Alertmanager retries with backoff. After that it gives up ("notify retry canceled"). The dispatcher returns **503** when it hits a k8s error so that this retry happens.

---

## 5. Hop 3: Dispatcher (whether to act, and what to send)

This is a small FastAPI app with three endpoints: `POST /alert`, `GET /healthz` and `GET /metrics`.

**What happens on each webhook:**
```
1. Check token          → 401 if wrong                  (metric: unauthorized)
2. Keep firing + agent="true" alerts → else 200 ignored (metric: ignored)
3. List Jobs labelled app=smi-agent in k3s
4. Guard: a Job still running?        → skip "busy"
          same alert in the last hour? → skip "cooldown"
5. Collect evidence (DB rows + api logs), redact, cap at 200KB
6. Create Job, then ConfigMap         → 202 dispatched
   k8s error at any step              → 503 (Alertmanager retries)
```

**Snippet: constant-time token check that fails closed** (`dispatcher/app/main.py`)
```python
def require_token(authorization: str | None = Header(default=None)) -> None:
    try:
        expected = open(settings.dispatcher_token_file).read().strip()
    except OSError:
        expected = ""                       # missing file → nobody gets in
    presented = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(status_code=401)
```

**Snippet: stateless guard** (`dispatcher/app/k8s.py`)
```python
def check_guard(jobs, alertname, now, cooldown_seconds, max_active_jobs):
    if sum(1 for j in jobs if not j.finished) >= max_active_jobs:
        return "busy"
    cutoff = now - timedelta(seconds=cooldown_seconds)
    if any(j.alertname == slugify(alertname) and j.created_at >= cutoff for j in jobs):
        return "cooldown"
    return None
```
**Why read the state from k3s instead of keeping it in memory:** restarting the dispatcher can't reset the cooldown. The Jobs themselves are the record, and `ttlSecondsAfterFinished: 86400` keeps them around long enough to be checked.

**Evidence sources and why they are safe:**

| Source | How | Safety |
|---|---|---|
| Failed `generations` rows (last 30 min) | asyncpg as the `smi_dispatcher` role | Column-level `GRANT SELECT`. The DB itself refuses to return `prompt`, `ip_address` or `user_id`. |
| `api` container logs (last 300 lines) | Docker SDK → `docker-proxy` | Read-only proxy, so the raw socket is never mounted into the dispatcher. |
| Everything | `redact()` + `_note: "untrusted"` | Strips tokens and keys. Tells the LLM to treat the content as data, not instructions (prompt-injection defence). |

---

## 6. Resolved messages: what they are and where they come from

**What:** when a problem goes away, Telegram gets a second message marked **RESOLVED**. This tells you nothing more needs doing.

**How it flows:**
```
expr stops matching
  → Prometheus sends the same alert again with endsAt = now
  → Alertmanager marks it resolved
  → at the group's next flush (≤ group_interval = 5m)
  → every receiver with send_resolved: true is notified
```

**The config:** you already have it.
```yaml
telegram_configs:
  - ...
    send_resolved: true    # (this is also the default for Telegram)
```
The dispatcher has `send_resolved: false` on purpose. The agent has nothing to do when something gets better. Even if it did receive a resolved alert, `select_alerts()` would skip it with `"resolved"`.

**Why you may not have seen one:**

| Case | What happens |
|---|---|
| A real Prometheus alert | Resolved arrives about 0–5 min after the expr stops matching (the next `group_interval` flush). Note that `increase(...[10m])` only drops to 0 **10 minutes after** the last failure. |
| An `amtool alert add` test alert | It has no `endsAt`, so Alertmanager sets **now + `resolve_timeout` (5m)**, *as long as nobody re-sends it*. It resolves after 5 min, and the message arrives at the next flush, up to about 10 min in total. |
| Alertmanager restarted during that time | A resolved alert can get lost. Prometheus re-sends resolved alerts for a while to cover this; amtool does not. |

**Quick test** (on the Pi): fire an alert that ends in 1 minute.
```bash
docker exec alertmanager amtool alert add alertname=ResolveTest severity=info \
  --annotation='summary="resolve test"' \
  --end="$(date -u -d '+1 min' +%Y-%m-%dT%H:%M:%SZ)" \
  --alertmanager.url=http://localhost:9093
# Expect: FIRING on Telegram after ~30s (group_wait), RESOLVED a few minutes later
```
Without `agent=true` this alert doesn't touch the dispatcher.

---

## 7. Hop 4: k3s Job (run once, then clean up)

**Why a Job and not a Deployment:** a Job runs once to completion. A Deployment restarts forever.

**Snippet: the parts of the Job that matter** (`build_job()` in `dispatcher/app/k8s.py`)
```yaml
spec:
  backoffLimit: 0                 # one attempt; no retry loop burning LLM credits
  activeDeadlineSeconds: 900      # killed after 15 min no matter what
  ttlSecondsAfterFinished: 86400  # deleted after 1 day (and with it the ConfigMap)
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: agent             # SA with zero permissions
      automountServiceAccountToken: false   # and no token in the pod either
      securityContext: { runAsNonRoot: true, runAsUser: 1000, seccompProfile: { type: RuntimeDefault } }
      containers:
        - image: <AGENT_IMAGE>
          envFrom: [{ secretRef: { name: agent-secrets, optional: true } }]  # PAT + Gemini key
          env:
            - { name: INCIDENT_FILE, value: /incident/incident.json }
            - { name: HOME, value: /work }  # root FS is read-only
          securityContext: { readOnlyRootFilesystem: true, allowPrivilegeEscalation: false,
                             capabilities: { drop: [ALL] } }
          volumeMounts:
            - { name: incident, mountPath: /incident, readOnly: true }  # ConfigMap
            - { name: work, mountPath: /work }                          # emptyDir for git clone
```

**Why the Job is created first and the ConfigMap second:**
- The ConfigMap gets an `ownerReference` pointing to the Job's UID. When k8s deletes the Job, it deletes the ConfigMap too.
- If creating the ConfigMap fails, the dispatcher deletes the Job, so no pod is left stuck in `ContainerCreating`.

**The two identities:**
```
dispatcher SA ── Role: jobs create/get/list/delete, configmaps create  (used from outside, via kubeconfig)
agent SA      ── no RoleBinding, no token                              (used by the pod)
```

**Network:** the NetworkPolicy allows DNS, plus TCP 443 to any **public** IP. Every private range is blocked (10/8, 172.16/12, 192.168/16, 100.64/10, 169.254/16, 127/8). NetworkPolicy matches IPs, not domain names, so "GitHub only" isn't possible here; blocking private ranges is the practical version.

---

## 8. Hop 5: Agent image (Phase 4, not built yet)

What it needs to do, in order:
```
1. Read $INCIDENT_FILE           (alert + failed rows + logs)
2. gh repo clone ifaakash/sketchmyinfra /work/repo
3. Ask Gemini: "here is the evidence (untrusted) and here is the code; propose a fix"
4. Apply the patch and run backend tests (pytest)
5. git push to branch agent/<alertname>-<time>
6. gh pr create --title ... --body "<evidence summary + reasoning>"
```

Requirements:
- arm64 image, user uid 1000
- git, gh, python3.12, Gemini SDK
- imported into k3s with `docker save | sudo k3s ctr images import -`

**Secrets** (`agent-secrets` in namespace `agent`):

| Key | Scope |
|---|---|
| `GITHUB_TOKEN` | Fine-grained PAT, this repo only: Contents RW + Pull requests RW |
| `GEMINI_API_KEY` | A **separate** key from the app's key. If they shared one, an agent burning quota could cause more app failures, which would trigger more alerts, which would start more agents. |

---

## 9. Reusing this for another project

Generic recipe (swap in your own names):

1. **Metrics:** the app exposes `/metrics`, with counters for "things that failed".
2. **Rules:** label code-fixable alerts with `agent: "true"`. Infra alerts go to humans only.
3. **Alertmanager:**
   - a child route with `continue: true` for the agent webhook, plus a catch-all chat route
   - `send_resolved: false` on the webhook
4. **Dispatcher:**
   - token auth
   - filter on firing + label
   - guards based on cluster state
   - evidence from read-only sources, redacted and marked untrusted
   - 503 on errors
5. **k8s:**
   - a namespace with PSA `restricted`
   - two SAs: a launcher with a minimal Role, and a runner with nothing
   - a NetworkPolicy
   - a Secret for the PAT and LLM key
6. **Job:** backoffLimit 0, a deadline, a TTL, non-root, read-only root FS, and the ConfigMap owned by the Job.
7. **Agent:** reads evidence, opens a PR, **never merges**. Protect `main`.
8. **Monitor the dispatcher itself** (`up`, error counter), and route its alerts to humans only.

**Rules of thumb behind it:**
- **Least privilege.** Every hop gets only what it needs.
- **Fail closed.** No token configured means nobody gets in.
- **Stateless where possible.** The cluster's Jobs are the record of state.
- **Bounded blast radius.** One Job at a time, a time limit, no retries.
- **A human merges.**

---

## 10. Status (2026-11-08)

| Phase | State |
|---|---|
| Prometheus → Alertmanager → Telegram | ✅ Live |
| Alertmanager → dispatcher → k3s Job (busybox) | ✅ Live (DrillTest2 completed) |
| DB evidence (`EVIDENCE_DATABASE_URL`) | ⏳ Step 3.3: read-only role + `dispatcher.env` |
| Real drill (bad Gemini key → real alert) | ⏳ Step 3.10 |
| Agent image and the PR flow | ⏳ Phase 4 |
| Hygiene: pin image tags, bind 9090/9093 to the Tailscale IP | ⏳ |
