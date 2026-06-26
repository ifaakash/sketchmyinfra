# 2026-04-07 — SketchMyInfra: Full Session Log

## Branding Journey
- Kroki → Arkitect → ArchDiagram → OpsVisual → **SketchMyInfra**
- Domain: **sketchmyinfra.com** (purchased)
- Logo: SVG pencil + infrastructure nodes (pencil tip = gold, body = white, green + purple nodes connected by line, on indigo rounded square)
- GitHub repo: public
- Twitter/X: @sketchmyinfra (to be created)
- LinkedIn page: to be created

---

## What We Built

### Frontend (Complete — Waitlist Landing Page)
A full production-ready landing page at `frontend/` with:

**Sections:**
1. **Navbar** — sticky, transparent→blur on scroll, theme toggle (sun/moon), "Join Beta" CTA, mobile hamburger
2. **Hero** — "Describe it. We diagram it." gradient headline, public beta badge, two CTAs, stats bar (48K+ diagrams, 12K+ engineers, <5s, 99.2%)
3. **Social Proof** — "Trusted by teams at" Shopify, Datadog, Stripe, Vercel, HashiCorp, Notion
4. **Features** — 6-card grid: AI-Powered Generation, Edit Before Rendering, Export Anywhere, Iterative Refinement, Privacy First, Session History
5. **How It Works** — 3 steps: Describe → Generate → Download
6. **Testimonials** — 3 fake engineer reviews (Priya Raghavan/SRE, Marcus Chen/DevOps, Sarah Kim/Platform)
7. **Waitlist** — "Launching Soon" badge, email input + "Join the Beta" (Formspree), 3 real diagram screenshots
8. **Footer** — logo, nav links, sketchmyinfra.com tagline

**Features:**
- Light/dark mode toggle (persists to localStorage, defaults to system preference)
- Background patterns that change with theme (dots in light, grid lines in dark)
- Smooth 300ms transitions on theme toggle
- Scroll reveal animations on sections
- Responsive: desktop, tablet, mobile
- Formspree email collection (needs YOUR_FORM_ID replaced)
- Inter + JetBrains Mono fonts via Google Fonts
- Tailwind CSS via CDN

**File Structure:**
```
frontend/
├── index.html              — Waitlist landing page (current live version)
├── css/style.css           — Theme-aware styles, patterns, animations, cards
├── js/waitlist.js          — Theme, navbar, scroll reveal, mobile menu, form
├── assets/
│   ├── favicon.svg         — Logo as favicon
│   ├── sample-datadog.png  — Real diagram screenshot (prod observability)
│   ├── sample-optic.png    — Real diagram screenshot (dev environment)
│   └── sample-sequence.png — Real diagram screenshot (auth flow)
└── _archive/               — Full generator app (preserved for restoration)
    ├── index-with-generator.html
    ├── app.js
    ├── api.js
    ├── mock.js
    ├── ui.js
    └── history.js
```

### Generator App (Archived — Ready to Restore)
Complete diagram generator tool built and archived in `frontend/_archive/`:
- Prompt textarea with example chips (AWS VPC, Microservices, CI/CD, Login Sequence)
- Mock API responses (4 PUML templates, keyword matching, simulated delays)
- PUML code panel (viewable, editable, re-renderable)
- Diagram display with zoom modal
- Download PNG/SVG, Iterate, New Diagram actions
- Session history sidebar
- API client with auto mock detection (USE_MOCKS flips based on hostname)

**To restore:** Copy `_archive/index-with-generator.html` back to `index.html`, copy all JS files back to `js/`, and the full generator is live again.

---

## Architecture Plan (Backend — Not Built Yet)

### Full Production Stack
```
EC2 (t3.small) — Docker Compose
├── nginx        — reverse proxy + static file server + HTTPS (Let's Encrypt)
├── FastAPI      — Python backend (calls Gemini API + PlantUML server)
└── plantuml     — plantuml/plantuml-server:jetty (internal only, not exposed)

Domain (sketchmyinfra.com) → Cloudflare/Route53 DNS → EC2 Elastic IP
```

### API Contract

**`POST /api/generate`** — User prompt → PlantUML code
```json
Request:  { "prompt": "AWS VPC with ALB, ECS, RDS", "context": null }
Response: { "puml": "@startuml\n...\n@enduml", "prompt_used": "..." }
Error:    { "error": "Failed to generate", "detail": "..." }
```

**`POST /api/render`** — PlantUML code → Image (base64)
```json
Request:  { "puml": "@startuml\n...\n@enduml", "format": "png" }
Response: { "image": "data:image/png;base64,...", "format": "png" }
Error:    { "error": "Render failed", "detail": "Syntax error on line 5" }
```

**Why two endpoints:** Edit PUML before rendering (saves Gemini API calls), better error isolation.

### Request Flow
```
Browser → POST /api/generate → nginx → FastAPI → Gemini API → { puml }
Browser → POST /api/render → nginx → FastAPI → PlantUML container → { base64 image }
```

### Tech Decisions
- **Backend:** Python FastAPI (async, learning preference)
- **AI:** Gemini API (PUML code generation from natural language)
- **Rendering:** PlantUML Server Docker (plantuml/plantuml-server:jetty)
- **Frontend:** Static HTML + Tailwind CDN + vanilla JS (no build tools)
- **PlantUML server internal only** — never exposed, backend proxies all requests
- **GEMINI_API_KEY** server-side only, passed via Docker env var
- **Mock mode** auto-detects localhost, disables on production domain

### Concurrency
- PlantUML container: multi-threaded Jetty, handles concurrent requests fine
- FastAPI: async, won't block on Gemini waits
- t3.small (2 vCPU, 2GB RAM): handles 10+ concurrent renders
- Gemini rate limits will be the bottleneck

---

## Launch Plan

### Pre-Launch (NOW)
1. Landing page with waitlist — DONE
2. Set up Formspree form ID — TODO
3. Claim channels — GitHub (done), Twitter/X @sketchmyinfra (TODO), LinkedIn page (TODO)
4. Build in public — post progress on Twitter/X, LinkedIn, Reddit
5. Product Hunt upcoming page — TODO

### Launch Day Playbook
Post on these platforms (in order of impact):

| Platform | Format |
|----------|--------|
| Product Hunt | Scheduled launch, get 5-10 friends to upvote early |
| r/devops, r/aws, r/sysadmin | "I built a tool that..." post with screenshots |
| Hacker News (Show HN) | "Show HN: SketchMyInfra — describe infra in English, get diagrams" |
| Twitter/X | Thread: problem → solution → demo GIF → link |
| LinkedIn | Post with short video/GIF demo |
| Dev.to / Hashnode | "How I built..." technical blog post |

**Launch post formula:**
- Hook: "I got tired of spending 30 minutes in Lucidchart for every design review"
- Problem: Manual diagram tools are slow, diagrams get outdated
- Solution: Type what you're building, get a diagram in 5 seconds
- Demo: GIF or 30-second video
- CTA: "Try it free at sketchmyinfra.com"

### Post-Launch Growth
- SEO content: "How to create AWS architecture diagrams", "PlantUML tutorial for DevOps"
- Get listed on awesome-devops lists, tool aggregators
- Future feature idea: auto-generate diagrams from Terraform code

### Monetization (Decision Pending)
Options discussed:
- Free forever (portfolio project)
- Freemium: 5 free diagrams/day, unlimited $9/mo
- Free PNG, paid SVG + history + team features

---

## Next Steps (Priority Order)

1. **Formspree setup** — Replace YOUR_FORM_ID in index.html, test email collection
2. **Twitter/X account** — Create @sketchmyinfra, start posting build progress
3. **Backend (FastAPI)** — Build `/api/generate` and `/api/render` endpoints
4. **Gemini integration** — System prompt engineering for consistent PUML output
5. **Docker Compose** — Wire nginx + FastAPI + PlantUML together
6. **EC2 deployment** — Instance, security groups, elastic IP, DNS
7. **HTTPS** — Let's Encrypt via certbot
8. **Restore generator** — Swap waitlist section back to full generator app
9. **Launch** — Execute launch day playbook
10. **Pi5 migration** — Eventually move from EC2 to self-hosted

---

## Commands Reference

```bash
# Start frontend locally
cd frontend && python3 -m http.server 3000

# Restore generator from archive
cp frontend/_archive/index-with-generator.html frontend/index.html
cp frontend/_archive/*.js frontend/js/

# Future: Docker Compose
docker compose up -d
```

## Gotchas
- Tailwind CDN (~300KB) fine for dev, purge for production
- Formspree free tier: 50 submissions/month — enough for early waitlist
- Old background server processes exit with code 137 when killed — expected, not an error
- Theme preference persists in localStorage key "theme"
- Generator archive is in `frontend/_archive/` — don't delete this directory
