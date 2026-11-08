# smi-agent

This is the image the dispatcher runs as a k3s Job, once per incident. It does the following:
1. reads `/incident/incident.json`
2. asks Gemini which files to read, then asks for a fix
3. runs the backend tests before and after the fix
4. opens a PR

It never merges. How it fits into the whole pipeline is covered in `docs/incident-pipeline-mental-model.md` and `docs/incident-pipeline.md`.

```
app/main.py     orchestration + PR body (exit 0 = done/nothing to do, 1 = failed)
app/llm.py      Gemini calls (google-genai, JSON schema output)
app/edits.py    search/replace edits, path allowlist (backend/app/, backend/tests/)
app/testrun.py  venv + pytest, "no new failures" gate, secrets scrubbed from env
app/repo.py     git clone/push (token via scoped credential helper) + gh pr
```

## Build and import into k3s (on the Pi)

```bash
docker build -t smi-agent:0.1.1 agent/
docker save smi-agent:0.1.1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep smi-agent
```
Bump the tag on every change. With the same tag, k3s keeps using the copy it already has (`IfNotPresent`).

## Secrets (`agent-secrets`, namespace `agent`)

```bash
cp k8s/agent/secret.yaml.example k8s/agent/secret.yaml   # gitignored
# GITHUB_TOKEN   fine-grained PAT: this repo, Contents RW + Pull requests RW
# GEMINI_API_KEY separate from the app's key
# AGENT_DRY_RUN  "true" for the first drills (no push, no PR, diff in logs)
kubectl apply -f k8s/agent/secret.yaml
```

## Env

| Var | Default | Source |
|---|---|---|
| `INCIDENT_FILE`, `WORK_DIR`, `HOME` | `/incident/incident.json`, `/work`, `/work` | Job spec |
| `GITHUB_TOKEN`, `GEMINI_API_KEY` | none (required) | `agent-secrets` |
| `AGENT_DRY_RUN` | `false` | `agent-secrets` |
| `AGENT_REPO` | `ifaakash/sketchmyinfra` | image env / Secret |
| `AGENT_MODEL` | `gemini-3.6-flash` | image env / Secret |

## Local test

```bash
cd agent
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests
```

To smoke test the image with the same restrictions the pod has (fake keys: it clones the repo, then stops with Gemini's `API key not valid`):
```bash
docker run --rm --read-only --user 1000:1000 --cap-drop ALL --tmpfs /work --tmpfs /tmp \
  -e HOME=/work -e AGENT_DRY_RUN=true -e GITHUB_TOKEN=dummy -e GEMINI_API_KEY=bad \
  -v "$PWD/incident.json:/incident/incident.json:ro" smi-agent:0.1.1
```
