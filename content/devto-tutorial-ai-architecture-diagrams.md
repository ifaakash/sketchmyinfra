---
title: Generate AWS, GCP & Azure Architecture Diagrams from Plain English — For Free
published: false
description: A tutorial on how to generate production-quality cloud architecture diagrams in seconds using AI and PlantUML — no signup required.
tags: devops, aws, tutorial, productivity
cover_image: https://sketchmyinfra.com/assets/og-image.png
canonical_url: https://sketchmyinfra.com
---

Every engineering team has the same problem: architecture diagrams are always out of date.

You draw it once in Lucidchart or Eraser, the system changes three times over the next month, and nobody updates the diagram. Eventually it becomes a lie — a pretty lie, but a lie.

What if you could regenerate your architecture diagram in 5 seconds, every time something changes, just by describing it in plain English?

That's what I built: **[SketchMyInfra](https://sketchmyinfra.com)** — a free AI tool that converts natural language descriptions into production-quality infrastructure diagrams using PlantUML. No signup required. No credit card. Just describe, generate, download.

---

## Why Not Just Use Eraser, Lucidchart, or Miro?

Fair question. Here's how they compare:

| | SketchMyInfra | Eraser | Lucidchart | draw.io |
|---|---|---|---|---|
| AI generation from text | ✅ | ✅ (limited) | ❌ | ❌ |
| Official cloud icons (AWS/GCP/Azure) | ✅ | Partial | ✅ | ✅ |
| Exports editable code (PlantUML) | ✅ | ❌ | ❌ | ❌ |
| Version-controllable output | ✅ | ❌ | ❌ | ❌ |
| Completely free | ✅ | Freemium | Paid | ✅ |
| No account needed | ✅ | ❌ | ❌ | ✅ |

The key differentiator: **SketchMyInfra gives you PlantUML code**, not just an image.

That means:

- You can check the diagram into Git alongside your infrastructure code
- You can tweak the code manually if the AI missed something
- You're not locked into a proprietary format
- You can integrate it into your docs pipeline (Confluence, Notion, GitHub wikis all support PlantUML)

Tools like Eraser are great collaborative whiteboards, but they're overkill when you just need a quick, accurate architecture diagram during a sprint or for a PR description.

---

## Tutorial: Generate Your First Architecture Diagram

### Step 1 — Go to sketchmyinfra.com

No signup. Just open the site and start typing.

### Step 2 — Describe your architecture in plain English

The AI understands cloud service names and infers the provider automatically. Try something like:

> A Node.js app on AWS ECS Fargate behind an ALB, connecting to RDS PostgreSQL in a private subnet, with CloudWatch for logs.

Or for GCP:

> A Python microservice on Cloud Run, backed by Cloud SQL PostgreSQL, with a Cloud Load Balancer in front and Pub/Sub for async events.

Or even multi-cloud:

> Frontend on Vercel, backend API on AWS ECS, database on AWS RDS, with Cloudflare for DNS and CDN.

### Step 3 — Click Generate

In under 5 seconds, you get:

1. A rendered SVG/PNG diagram with **official cloud provider icons** (AWS icon library v20, GCP icons, Azure PlantUML)
2. The **PlantUML source code** — editable, versionable, portable

### Step 4 — Iterate

Not quite right? Just refine your prompt:

> Add a NAT Gateway in the public subnet and a Redis ElastiCache cluster in the private subnet.

The AI uses your previous diagram as context and updates it — it doesn't start from scratch.

### Step 5 — Export

Download as **SVG** (infinitely scalable, great for docs) or **PNG** (for Slack, Confluence, presentations).

---

## What the Output Actually Looks Like

Here's a real example. Prompt:

> Three-tier AWS app: ALB → ECS Fargate → RDS Aurora in us-east-1, with CloudWatch monitoring.

The generated PlantUML:

```plantuml
@startuml
allow_mixing
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/Groups/AWSCloud.puml
!include AWSPuml/Groups/Region.puml
!include AWSPuml/Groups/VPC.puml
!include AWSPuml/Groups/PublicSubnet.puml
!include AWSPuml/Groups/PrivateSubnet.puml
!include AWSPuml/NetworkingContentDelivery/ElasticLoadBalancingApplicationLoadBalancer.puml
!include AWSPuml/Containers/ElasticContainerService.puml
!include AWSPuml/Database/AuroraPostgreSQLInstance.puml
!include AWSPuml/ManagementGovernance/CloudWatch.puml

skinparam actorStyle awesome
top to bottom direction

AWSCloudGroup(cloud) {
  RegionGroup(region, "us-east-1") {
    VPCGroup(vpc, "VPC (10.0.0.0/16)") {
      PublicSubnetGroup(pub, "Public Subnet") {
        ElasticLoadBalancingApplicationLoadBalancer(alb, "ALB", "HTTPS Ingress")
      }
      PrivateSubnetGroup(priv, "Private Subnet") {
        ElasticContainerService(ecs, "ECS Fargate", "App Service")
        AuroraPostgreSQLInstance(db, "Aurora PostgreSQL", "Database")
      }
    }
    CloudWatch(cw, "CloudWatch", "Logs & Metrics")
  }
}

actor "User" as user
user --> alb : HTTPS
alb --> ecs : Routes Traffic
ecs --> db : SQL Queries
ecs .r.> cw : App Logs
@enduml
```

You get this code **plus** the rendered diagram. Edit the code, hit re-render — done.

---

## Real-World Use Cases

**PR descriptions** — attach a diagram showing exactly what infrastructure your PR changes. Reviewers love it.

**Onboarding docs** — generate a current-state diagram of your system in 30 seconds, not 3 hours.

**RFC / design docs** — sketch the proposed architecture while you're writing the doc, not after.

**Client presentations** — professional cloud diagrams without Visio or a designer.

**Incident reviews** — diagram the blast radius of an outage quickly, while the context is fresh.

---

## Tech Behind It (for the curious)

- **AI:** Google Gemini with a carefully tuned system prompt that understands AWS, GCP, and Azure icon library paths and naming conventions
- **Rendering:** PlantUML running as a containerized service — it fetches the icon libraries, compiles the diagram, and returns SVG/PNG
- **Infra:** Runs on a Raspberry Pi 5 with k3s. Yes, really. It handles real traffic just fine.
- **Free tier:** 5 diagrams/day without an account, more with a free login

---

## Try It

**[sketchmyinfra.com](https://sketchmyinfra.com)** — no account needed to start.

Drop a comment below with what architecture you generated — I'd love to see what people are building.

---

*Built by a solo DevOps engineer, running on a Raspberry Pi, powered by coffee and PlantUML.*
