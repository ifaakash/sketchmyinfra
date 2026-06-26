# 2026-04-08 — Phase 5: Google + GitHub OAuth

## What We Built

### New files
```
backend/app/services/jwt_service.py   # create/decode session + OAuth-state JWTs
backend/app/services/oauth.py         # Google + GitHub Authorization Code flow
backend/app/middleware/auth.py        # get_current_user / _optional dependencies
backend/app/routers/auth.py           # /api/auth/* endpoints
```

### Modified files
```
backend/app/main.py   # includes auth router
.env.example          # documents APP_URL=https://dev.sketchmyinfra.com and callback URLs
```

### Endpoints
| Method | Path                                | Purpose                              |
|--------|-------------------------------------|--------------------------------------|
| GET    | `/api/auth/google/login`            | 302 to Google consent screen         |
| GET    | `/api/auth/google/callback`         | exchange code, upsert user, set cookie, 302 home |
| GET    | `/api/auth/github/login`            | 302 to GitHub consent screen         |
| GET    | `/api/auth/github/callback`         | exchange code, upsert user, set cookie, 302 home |
| GET    | `/api/auth/me`                      | current user JSON (401 if no cookie) |
| POST   | `/api/auth/logout`                  | clears session cookie (204)          |

---

## Key Design Decisions

### 1. Session delivery: HttpOnly cookie, not localStorage
- **Cookie** `session`, HttpOnly, SameSite=Lax, Secure=true when APP_URL is https
- **Why HttpOnly:** JS cannot read it → XSS cannot exfiltrate the token
- **Why SameSite=Lax (not Strict):** Strict would drop the cookie on the cross-site
  redirect back from Google/GitHub. Lax still blocks CSRF on POST/PUT but allows
  top-level navigation.
- **Why cookie over localStorage:** localStorage is readable by any JS running on
  the page, so one XSS = full account takeover. HttpOnly removes that vector.

### 2. Stateless JWT for sessions
- Single source of truth is the signed JWT itself — no session table, no Redis
- Tradeoff: can't revoke individual sessions before their expiry. For a freemium
  SaaS at this stage that's acceptable. If it becomes a problem later: rotate
  `jwt_secret` (nukes all sessions) or add a `sessions` table with a revoke flag.

### 3. OAuth state = signed short-lived JWT
- CSRF protection on the callback without needing server-side state storage
- 10-minute expiry, `type: "oauth_state"`, `provider` bound to the token
- Classic alternative is a random string in a cookie; JWT is equivalent and
  stateless, which matches the rest of the design.

### 4. Raw httpx, no OAuth library
- Skipped `authlib` / `httpx-oauth` — auth-code flow is ~30 lines per provider
- Keeps dependency surface small, protocol explicit (easier to debug)

### 5. Upsert on (oauth_provider, oauth_id), not email
- A user who signs in with Google and later with GitHub using the same email
  gets **two** accounts. That's intentional: the provider id is the stable key,
  email can change. Account linking is a separate feature we can add later.

### 6. `APP_URL` drives callback URLs
- Single env var controls both the Google/GitHub redirect URI and the post-login
  redirect. Dev = `https://dev.sketchmyinfra.com`, prod = `https://sketchmyinfra.com`.
- One place to change when flipping environments.

---

## Manual Setup Required (You, not me)

### Google OAuth App

1. Go to https://console.cloud.google.com/apis/credentials
2. Create project if needed → **Create Credentials → OAuth client ID**
3. If prompted, configure the OAuth **consent screen** first:
   - User type: **External**
   - App name: `SketchMyInfra`
   - User support email + developer email: your email
   - Scopes: `openid`, `email`, `profile` (default)
   - Test users: add your own Google email (while app is in "Testing")
4. Back on Credentials → **Create OAuth client ID**
   - Application type: **Web application**
   - Name: `SketchMyInfra Dev` (create a second one `SketchMyInfra Prod` later)
   - **Authorized redirect URIs:**
     ```
     https://dev.sketchmyinfra.com/api/auth/google/callback
     ```
     (Add `https://sketchmyinfra.com/api/auth/google/callback` too if you want
     one client for both, but two separate clients is cleaner.)
5. Copy **Client ID** and **Client secret** → paste into `.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

### GitHub OAuth App

1. Go to https://github.com/settings/developers → **OAuth Apps → New OAuth App**
2. Fill in:
   - Application name: `SketchMyInfra Dev`
   - Homepage URL: `https://dev.sketchmyinfra.com`
   - Authorization callback URL: `https://dev.sketchmyinfra.com/api/auth/github/callback`
3. Click **Register application**
4. **Generate a new client secret** (GitHub only shows it once — copy immediately)
5. Paste into `.env`:
   ```
   GITHUB_CLIENT_ID=...
   GITHUB_CLIENT_SECRET=...
   ```
6. Repeat for a prod app later with `sketchmyinfra.com` URLs.

### Cloudflare Tunnel — add `dev.sketchmyinfra.com`

Since you created the subdomain but the tunnel config was set up for
`sketchmyinfra.com`, add an ingress rule:

```yaml
# ~/.cloudflared/config.yml  (on the Pi5)
ingress:
  - hostname: sketchmyinfra.com
    service: http://localhost:80
  - hostname: www.sketchmyinfra.com
    service: http://localhost:80
  - hostname: dev.sketchmyinfra.com
    service: http://localhost:80
  - service: http_status:404
```

Then in Cloudflare DNS, add a CNAME `dev → <tunnel-id>.cfargotunnel.com` (proxied).

Restart cloudflared: `sudo systemctl restart cloudflared`

---

## Testing Checklist

1. **Environment:**
   ```bash
   cp .env.example .env
   # Fill in JWT_SECRET (python -c "import secrets; print(secrets.token_hex(32))")
   # Fill in GOOGLE_CLIENT_ID / SECRET and GITHUB_CLIENT_ID / SECRET
   # Set APP_URL=https://dev.sketchmyinfra.com
   ```

2. **Rebuild the API container** (new imports):
   ```bash
   docker compose up --build -d api
   docker compose logs -f api
   ```

3. **Health check:**
   ```bash
   curl https://dev.sketchmyinfra.com/api/health
   # {"status":"ok","version":"2.0.0"}
   ```

4. **Google login flow (in browser):**
   - Visit `https://dev.sketchmyinfra.com/api/auth/google/login`
   - Should redirect to Google consent screen
   - Approve → should land back at `https://dev.sketchmyinfra.com/`
   - Open devtools → Application → Cookies → should see `session` (HttpOnly)

5. **Verify /me works:**
   ```bash
   # In the same browser, open:
   https://dev.sketchmyinfra.com/api/auth/me
   # Should return your user JSON
   ```

6. **Verify DB row created:**
   ```bash
   docker compose exec db psql -U smi -d sketchmyinfra -c "SELECT id, email, oauth_provider, tier FROM users;"
   ```

7. **Logout:**
   ```bash
   curl -X POST https://dev.sketchmyinfra.com/api/auth/logout -i
   # 204, Set-Cookie clearing session
   ```

8. **Repeat 4–7 with GitHub.**

9. **CSRF sanity check:**
   ```bash
   # Hit callback with a tampered state — should 400
   curl "https://dev.sketchmyinfra.com/api/auth/google/callback?code=fake&state=nope"
   ```

---

## Gotchas to Watch For

- **Google redirect_uri mismatch:** must match **exactly**, including scheme,
  host, and trailing slash behavior. `http://localhost:80` ≠ `http://localhost`.
- **GitHub email null:** if the user keeps their email private, `/user` returns
  `email: null`. We fall back to `/user/emails` and pick the primary+verified one.
  Make sure the OAuth scope includes `user:email`.
- **Cookie not set in browser:** usually SameSite or Secure. If APP_URL is https
  but you're testing via plain IP, Secure=true means the browser drops it.
  Always test through `dev.sketchmyinfra.com`, never via raw IP.
- **State token expiry:** if the user sits on the Google consent screen for
  >10 minutes, the state will be expired and callback returns 400. Acceptable
  UX cost, but worth knowing.
- **Two accounts per human:** signing in with Google and GitHub using the same
  email creates **two** users. Intentional (see decision #5).

---

## Open Questions / Next Steps

- **Phase 6 — Rate limiting:** use `get_current_user_optional` in the generate
  router, count today's rows in `generations` (partial index already exists),
  enforce `rate_limit_anonymous` (3) vs `rate_limit_free` (5).
- **Phase 7 — Frontend auth UI:** "Sign in with Google/GitHub" buttons pointing
  at `/api/auth/{provider}/login`, a `useUser()` hook that hits `/api/auth/me`,
  a user menu with logout button.
- **Account linking:** merge Google + GitHub for the same email. Not urgent.
- **Refresh tokens / session revocation:** only needed if we grow past
  "rotate JWT secret kills everyone" as an acceptable blast radius.
- **Prod OAuth apps:** separate clients for `sketchmyinfra.com` with their own
  secrets, stored in Pi5 `.env` (not committed).
