# Wiring login into the generator UI (dev)

**Date:** 2026-04-10
**Branch:** `fix/bugs`
**Scope:** Dev only (`dev.sketchmyinfra.com`). No prod changes, no rate limiting.

## Topics covered

- Audited the state of Phase 5 OAuth: backend was complete and working
  end-to-end, but login had no product surface — the active `frontend/index.html`
  was the marketing/waitlist page and the generator UI was parked in
  `frontend/_archive/`.
- Revived the generator UI as the active landing page.
- Added a small auth widget (Google/GitHub buttons ↔ avatar+Logout pill).
- Made `/api/generate` user-aware and made it persist a row to the
  `generations` table per successful call.
- Kept rate limiting (Phase 6) and production cutover deferred.

## Decisions + why

| Decision | Why |
|---|---|
| Keep the full marketing sections (features / how-it-works / testimonials) on the page; just add the generator below the fold. | The archive already had that structure. No reason to split into two pages for a one-user-at-a-time dev environment. Less surface area = fewer bugs. |
| Put login buttons in the navbar, not inline near the generator. | Navbar is where users look for auth. Generator section stays focused on its job. |
| `/api/render` stays unauthenticated and stateless. | Rendering isn't the billable unit, generation is. If we rate-limit later we'll rate-limit `/generate`. No reason to drag `/render` into the auth dependency graph. |
| Only persist a `Generation` row on *success* — not on `GeminiError`. | The table should reflect "diagrams we actually served." Phase 6 rate limiting also only cares about successful calls. |
| Use `request.client.host` as `ip_address` for now (known to be the Traefik pod IP, not the real visitor). | Good enough to verify plumbing. Left a comment in `generate.py`: switch to `X-Forwarded-For` parsing when we wire real per-IP rate limits. |
| `credentials:'include'` instead of `'same-origin'`. | Same-origin would work here, but `include` is a strict superset and means no behavior change if the API domain diverges later. |
| Skip the auth `/me` fetch in local mock mode. | `USE_MOCKS` already guards api.js for localhost. Auth would fail the call and briefly flash login buttons otherwise — ugly. |
| Leave `frontend/js/waitlist.js` in place (dead code). | Not referenced by the new `index.html`. Removing it is scope creep; zero runtime cost. |

## Commands / configs

Files touched:
- `frontend/index.html` — replaced with generator markup, added `#auth-slot` div and `<script src="js/auth.js">`.
- `frontend/_archive/index-waitlist.html` — backup of the old landing page.
- `frontend/js/auth.js` — new. Handles `/api/auth/me`, render login buttons vs avatar+logout, `POST /api/auth/logout`. Exposes `window.currentUser`.
- `frontend/js/api.js` — added `credentials:'include'` to both `apiGenerate` and `apiRender` fetch calls.
- `backend/app/routers/generate.py` — rewrote to inject `Request`, `get_current_user_optional`, `get_db`; inserts a `Generation` row after successful generate.

Deploy (on the Pi5):

```bash
# Frontend — hostPath is bound from ~/sketchmyinfra/frontend, restart is not
# optional because of the inode gotcha (see 2026-04-09-full-k8s-migration.md).
cd ~/sketchmyinfra && git pull
kubectl rollout restart deployment/sketchmyinfra-frontend

# Backend — rebuild and reimport into containerd (k3s doesn't pull from a
# registry; it loads from the local image store).
docker build -t sketchmyinfra-api:local backend/
docker save sketchmyinfra-api:local | sudo k3s ctr images import -
kubectl rollout restart deployment/sketchmyinfra-api

# Watch the rollout
kubectl rollout status deployment/sketchmyinfra-api
kubectl logs -f deploy/sketchmyinfra-api
```

End-to-end verification:

```bash
# Logged-out: should see rows with user_id=NULL after generating a diagram
kubectl exec -it deploy/postgres -- \
  psql -U smi sketchmyinfra \
  -c "select id, user_id, ip_address, created_at from generations order by created_at desc limit 5;"

# After login: user_id should match the row in users
kubectl exec -it deploy/postgres -- \
  psql -U smi sketchmyinfra \
  -c "select id, email, created_at from users order by created_at desc limit 5;"
```

Browser DevTools → Network → `/api/generate` request → Request Headers must
include `Cookie: session=...`. If not, `credentials:'include'` didn't land or
the cookie was set with the wrong `path` / `domain`.

## Key takeaways

- **Same-origin + SameSite=Lax is enough for cookie auth when frontend and API
  share a hostname via path-based ingress.** No CORS gymnastics required. The
  only frontend change needed was `credentials:'include'` on `fetch`.
- **Dead code from a previous UX (`frontend/js/waitlist.js`, `frontend/_archive/*`)
  was trivially reusable.** The js files in `frontend/js/` were byte-identical
  to `frontend/_archive/*.js` — a 30-second `diff` before the plan saved us
  from copying files that didn't need copying.
- **FastAPI dep injection made `/generate` auth-aware with zero branching.**
  `user: User | None = Depends(get_current_user_optional)` means "give me the
  user if there is one, don't care if there isn't," and the router body just
  does `user.id if user else None`. No `if authenticated then ... else ...`
  control flow leaking in.
- **Persisting a `Generation` row is the thing that actually proves login is
  wired up.** The cookie could be set, the `me` endpoint could return the
  user, and you'd *still* not know whether authenticated generations were
  being attributed correctly — unless you checked the DB. The `psql` check is
  the real test here, not "I can see my name in the navbar."

## Gotchas

- **`request.client.host` is the ingress pod IP, not the visitor.** Documented
  in the code comment. This will matter the moment we turn on rate limiting —
  every anonymous request will look like it came from the same IP and we'll
  rate-limit the planet to 3/day. Fix: parse `X-Forwarded-For` and trust it
  only for the Traefik pod CIDR.
- **hostPath stale-inode bug still live.** `git pull` + `kubectl rollout
  restart deployment/sketchmyinfra-frontend` is the workaround. The real fix
  (bake frontend into the nginx image) is deferred until before prod cutover.
- **Image rebuild is manual.** `docker save | k3s ctr images import` is the
  manual equivalent of a CI pipeline. Forgetting the import → rolling restart
  reuses the cached image → "why didn't my change take effect?" Automate with
  a Makefile target before this becomes a daily pain.

## Next steps (roughly in order)

1. **Test the full flow on dev** — logged-out generate, login with Google,
   logged-in generate, verify `users` + `generations` rows, logout.
2. **Phase 6 — rate limiting.** Infra is in place (`rate_limit_anonymous=3`,
   `rate_limit_free=5` in config; `ip_address` + `created_at` indexed). Needs
   a dependency that counts rows in the last 24h and raises 429, plus real
   `X-Forwarded-For` parsing.
3. **History from DB.** Replace the localStorage history panel with a real
   `GET /api/generations` call once a user is logged in. Anonymous users
   still use localStorage.
4. **Bake frontend into nginx image.** Kills the hostPath gotcha for good and
   makes rollouts atomic. Blocker for prod.
5. **Prod cutover.** Separate Google/GitHub OAuth apps, separate k8s secret,
   `APP_URL=https://sketchmyinfra.com`, double-check `CORS_ORIGINS`, DNS
   pointed at Cloudflare Tunnel, then `kubectl apply` against a prod
   namespace (or just flip the configmap).

## Open questions

- Do we want a "Login to save your generations" nudge near the generator for
  anonymous users? Currently there's no indication that logging in does
  anything useful from the UI's perspective. Small UX polish, not blocking.
- Should the generations table store `puml_code` at all? It's potentially
  large and currently never read back. Could store just the prompt + user +
  timestamp and save disk. Defer until we see real row counts on dev.
