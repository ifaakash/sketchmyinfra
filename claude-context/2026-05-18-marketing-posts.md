# Marketing Posts — Draw Feature (May 18, 2026)

---

## LinkedIn Post

---

We just shipped something I've wanted for a while.

SketchMyInfra now lets you create, save, and share freehand architecture diagrams — right in the browser. No signup wall. No desktop app. Just open /draw and start sketching.

Here's what it does:

- Full whiteboard with shapes, arrows, text, connectors, and freehand drawing (powered by Excalidraw)
- Auto-save every 3 seconds — never lose a sketch again
- Save to the cloud (logged-in) or locally in the browser (anonymous)
- Share any diagram via link — recipients can view it or fork their own copy
- Gallery view to manage all your drawings in one place
- Dark/light theme toggle for those late-night architecture sessions

Why this matters for engineering teams:

Architecture decisions happen fast. In standups, in Slack threads, on quick calls. You sketch something on a napkin and it's gone by tomorrow.

This gives your team a persistent, shareable canvas where rough ideas actually survive. No need to fire up Lucidchart for a 2-minute sketch. No more screenshots of whiteboard photos. Just describe it, draw it, share the link, move on.

And yes — it works alongside our AI diagram generator. Use AI to generate the polished PlantUML diagram. Use the whiteboard for the messy, early-stage thinking. Both live under one roof.

Try it free: https://sketchmyinfra.com/draw/

No signup required. No limits on the whiteboard.

#DevOps #SoftwareEngineering #InfrastructureAsCode #ArchitectureDiagrams #CloudArchitecture #AWS #BuildInPublic #Excalidraw

---

## Dev.to Post

---

**Title:** We Built a Free Tool to Create, Save, and Share Architecture Diagrams — Here's Why

**Tags:** devops, webdev, cloud, productivity

---

If you've ever drawn an architecture diagram on a whiteboard, snapped a photo, and dropped it in Slack — you know the pain.

The photo is blurry. Nobody can edit it. It lives in a thread that gets buried by Thursday. When the architecture changes (it always does), the diagram is already stale.

We built a better way.

## The Problem with Existing Tools

Most teams reach for one of three options when they need an architecture diagram:

**1. Full-featured tools (Lucidchart, draw.io, Miro)**
These are powerful, but they're overkill for 80% of architecture sketches. You don't need pixel-perfect alignment when you're sketching an RFC in the first 5 minutes of a design review. The setup cost is high, the learning curve is real, and half your team doesn't have a license.

**2. AI generators (including ours)**
SketchMyInfra already lets you describe infrastructure in plain English and get a polished PlantUML diagram in under 5 seconds. That works great for well-defined architectures — AWS VPCs, CI/CD pipelines, microservice flows. But sometimes your idea isn't that concrete yet. Sometimes you need to *think with your hands.*

**3. Physical whiteboards / pen and paper**
Zero friction, maximum speed. But zero persistence, zero shareability. The drawing lives and dies in that room.

None of these cover the middle ground: **fast, freehand, persistent, and shareable.**

## What We Built

SketchMyInfra now has a freehand drawing mode at [sketchmyinfra.com/draw](https://sketchmyinfra.com/draw/). Here's the stack:

### The Canvas
A full-featured whiteboard powered by [Excalidraw](https://excalidraw.com/) — the same engine used by teams at Meta, Notion, and Vercel. You get:

- Shapes (rectangles, circles, diamonds, arrows)
- Freehand drawing
- Text labels
- Connectors with automatic routing
- Color coding
- Dark and light themes

### Persistence
This is where it gets useful. Every drawing auto-saves with a 3-second debounce:

- **Logged-in users** — drawings save to the cloud (PostgreSQL + JSONB). Come back tomorrow, next week, from a different device. Your drawings are there.
- **Anonymous users** — drawings save to browser localStorage. No signup required. You can still create, edit, and manage multiple drawings.
- **Migration path** — when an anonymous user signs in, they get a one-click "Save All to Cloud" option to migrate their local drawings.

### Sharing
Every cloud-saved drawing gets a unique share link. When someone opens your link:

- They see the drawing in **read-only mode** — full zoom, pan, no accidental edits
- They can **fork it** with one click — creates their own editable copy
- No login required to view. Login required to fork to cloud (or they can fork to localStorage)

The share URL looks like: `sketchmyinfra.com/draw/s/a1b2c3d4e5f6`

### Gallery
All your drawings live in a gallery at `/draw/`:

- Visual preview thumbnails of each drawing
- Click-to-zoom lightbox for quick preview
- Create, rename, delete, share — all from one place
- Cloud drawings and local drawings shown separately

## The Technical Implementation

For engineers who care about the details:

**Backend:**
- FastAPI + SQLAlchemy async + PostgreSQL
- `drawings` table: UUID PK, user FK, `share_id` (12-char URL-safe token via `secrets.token_urlsafe`), `title`, `data` (JSONB — stores the full Excalidraw scene), `thumbnail` (base64 PNG), timestamps
- CRUD endpoints + public share endpoint (no auth required to view)
- Max 50 drawings per user to keep storage bounded

**Frontend:**
- React + Vite, served at `/draw/` via nginx
- `react-router-dom` for client-side routing (gallery, editor, shared view)
- Excalidraw's `exportToBlob` generates 400px thumbnails on every save
- `onChange` callback with 3-second debounce for auto-save
- `viewModeEnabled` prop for read-only shared views
- localStorage fallback for anonymous users with the same CRUD interface

**Nginx:**
```nginx
location /draw/ {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /draw/index.html;
}
```

SPA fallback ensures client-side routes like `/draw/edit/abc123` and `/draw/s/xyz789` resolve correctly.

## Why This Beats Alternatives for Quick Architecture Sketches

| Scenario | Lucidchart | draw.io | Slack screenshot | SketchMyInfra Draw |
|---|---|---|---|---|
| Time to first stroke | 30+ sec (login, create, template) | 10+ sec (load, new file) | Instant (but no editing) | 2 clicks from homepage |
| Sharing with team | Share link (needs account) | Export + upload | Already in chat (low quality) | Share link (no account needed to view) |
| Persistence | Cloud (paid tier) | Local file / Google Drive | None | Cloud (free) or localStorage |
| Forking/copying | Manual duplicate | Copy file | Screenshot again | One-click fork |
| Works alongside AI generation | No | No | No | Yes — same platform |

The key differentiator: **SketchMyInfra Draw exists in the same ecosystem as the AI diagram generator.** You can use AI for polished PlantUML output and the whiteboard for early-stage sketching — all under one URL, one account, one workflow.

## Try It

Open [sketchmyinfra.com/draw](https://sketchmyinfra.com/draw/) and start drawing. No signup. No install. No credit card.

If you want persistence and sharing, sign in with Google or GitHub. Your first 50 drawings are free.

---

*SketchMyInfra is a free, open-source tool for generating and sketching infrastructure diagrams. AI-powered PlantUML generation + freehand whiteboard, all in the browser.*
