# SketchMyInfra

**Turn plain English into production-ready architecture diagrams in seconds.**

[sketchmyinfra.com](https://sketchmyinfra.com) | [About](https://sketchmyinfra.com/about/) | [AWS Diagrams](https://sketchmyinfra.com/aws-architecture-diagram-generator/) | [Lucidchart Alternative](https://sketchmyinfra.com/lucidchart-alternative/)

SketchMyInfra is an AI-powered infrastructure diagram generator. Describe your cloud architecture in natural language and get a rendered PlantUML diagram you can download as SVG or PNG — no drag-and-drop, no manual drawing.

## How it works

1. **Describe** — write what you're building: *"AWS VPC with ECS Fargate, ALB, and RDS Aurora"*
2. **Generate** — AI converts your description into PlantUML code with official cloud provider icons
3. **Download** — export as PNG or SVG, drop into docs, Confluence, Notion, or presentations

## Features

- **AI-powered generation** — Gemini converts natural language to accurate PlantUML with correct AWS icon imports
- **Official cloud icons** — uses [aws-icons-for-plantuml](https://github.com/awslabs/aws-icons-for-plantuml) with proper grouping macros (VPC, subnets, regions)
- **Edit before rendering** — review and tweak PlantUML code, then re-render without hitting the AI again
- **Iterative refinement** — refine your prompt and regenerate; the AI uses the previous diagram as context
- **Export as PNG or SVG** — clean, professional diagrams ready for documentation
- **Session history** — every diagram saved in your browser; compare and restore previous versions
- **OAuth login** — sign in with Google or GitHub to track your generations
- **Privacy-first** — diagrams rendered on the fly and delivered to your browser

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS, Tailwind CSS, nginx |
| Backend | Python, FastAPI, async SQLAlchemy, asyncpg |
| AI | Google Gemini API |
| Diagrams | PlantUML server (Jetty) |
| Database | PostgreSQL 16 |
| Auth | OAuth 2.0 (Google, GitHub), JWT sessions, HttpOnly cookies |
| Infra | k3s (Kubernetes), Traefik ingress, Cloudflare Tunnel |
| Hosting | Raspberry Pi 5 |

## Architecture

```
Cloudflare Tunnel → Traefik Ingress → k3s cluster
                                        ├── nginx (frontend)
                                        ├── FastAPI (API)
                                        ├── PlantUML server (rendering)
                                        └── PostgreSQL (users + generations)
```

Dev and prod run as separate Kubernetes namespaces on the same Pi5, with independent databases, secrets, and OAuth apps.

## Development

### Prerequisites

- Docker
- k3s (or any Kubernetes cluster)
- Google Gemini API key
- Google and/or GitHub OAuth app credentials

### Quick start

```bash
# Clone
git clone https://github.com/ifaakash/sketchmyinfra.git
cd sketchmyinfra

# Build images
docker build -t sketchmyinfra-api:local backend/
docker build -t sketchmyinfra-frontend:local frontend/

# Import into k3s
docker save sketchmyinfra-api:local | sudo k3s ctr images import -
docker save sketchmyinfra-frontend:local | sudo k3s ctr images import -

# Configure secrets
cp k8s/secret.example.yaml k8s/secret.yaml
# Edit k8s/secret.yaml with your credentials

# Deploy
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/plantuml.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# Watch pods come up
kubectl get pods -w
```

### Production deployment

```bash
kubectl create namespace prod
cp k8s/prod/secret.example.yaml k8s/prod/secret.yaml
# Edit with prod credentials (separate OAuth apps, strong passwords)

kubectl apply -f k8s/prod/
kubectl get pods -n prod -w
```

## Keywords

infrastructure diagram generator, cloud architecture diagram, PlantUML AI, AWS architecture diagram, text to diagram, AI diagram generator, infrastructure as code visualization, cloud diagram tool, DevOps diagram, architecture documentation

## License

MIT

---

Built by engineers, for engineers. Powered by AI & PlantUML.
