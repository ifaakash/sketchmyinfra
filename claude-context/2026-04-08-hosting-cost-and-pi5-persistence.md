# 2026-04-08 — Hosting Cost & Pi5 Persistence Strategy

## Topics Covered
- AWS hosting cost estimate for the SketchMyInfra stack
- Cheaper hosting alternatives (Hetzner, Oracle Free Tier, Fly.io, etc.)
- Pi5 self-hosting persistence strategy across restarts
- Backup strategy for production-grade resilience

---

## AWS Cost Estimate

| Component | Spec | Monthly |
|---|---|---|
| EC2 t3.small | 2 vCPU, 2GB RAM — runs nginx + FastAPI + PlantUML + Postgres in Docker | ~$15 |
| EBS 20GB gp3 | OS + DB + Docker images | ~$2 |
| Elastic IP | static IP (free if attached to running instance) | $0 |
| Data transfer out | first 100GB free, then $0.09/GB | ~$0–5 |
| Route 53 hosted zone | DNS for sketchmyinfra.com | $0.50 |
| **Total AWS** | | **~$18–25/mo** |

**Plus Gemini API** (separate, not AWS):
- Free tier: 1,500 requests/day on `gemini-2.0-flash` — sufficient for early stage
- Paid: ~$0.075 per 1M input tokens

**Optimization:** Add Cloudflare (free) in front for SSL/CDN — cuts data transfer egress costs.

---

## Cheaper Alternatives

| Option | Monthly | Tradeoffs |
|---|---|---|
| Hetzner Cloud (CX22) | ~€4 (~$4.50) | EU-based, cheapest reliable VPS, great specs |
| DigitalOcean droplet (2GB) | $12 | Simple UI, great docs |
| **Oracle Cloud Free Tier** | **$0** | 2x AMD VMs always free, 4x ARM cores, 24GB RAM total — annoying signup but truly free |
| Fly.io | $0–10 | Free tier covers small apps, scale-to-zero |
| Railway | $5/mo + usage | Easiest deploys, expensive at scale |
| **Pi5 self-hosted** | ~$0 (electricity) | Best long-term once accessible |

---

## Pi5 Persistence Strategy

### Layer 1: Data Persistence (Easy)

Postgres data is already volume-mounted in `docker-compose.yml`:
```yaml
volumes:
  - pgdata:/var/lib/postgresql/data
```

Survives `docker compose down`. Only `docker compose down -v` wipes it.

**Critical gotcha:** Named volumes live in `/var/lib/docker/volumes/` — on the SD card. SD cards die. Two fixes:

**Option A: Bind mount to external SSD/USB**
```yaml
volumes:
  - /mnt/ssd/sketchmyinfra/pgdata:/var/lib/postgresql/data
```

**Option B: Boot Pi5 from NVMe entirely** (Pi5 supports M.2 HAT) — much more reliable than SD.

### Layer 2: Auto-restart on Boot

**Already configured:** `restart: unless-stopped` handles container crashes and Docker daemon restarts.

**Missing piece — Systemd unit for full reboot resilience:**
```ini
# /etc/systemd/system/sketchmyinfra.service
[Unit]
Description=SketchMyInfra Stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/sketchmyinfra
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable sketchmyinfra
```

Reboot → systemd → Docker → Compose → stack up, data intact.

### Layer 3: Backups (Non-Negotiable)

**Restart resilience ≠ disaster resilience.** SSD dies → data gone unless backed up off-device.

**Simple cron approach:**
```bash
# /etc/cron.daily/postgres-backup
docker compose exec -T db pg_dump -U smi sketchmyinfra | gzip > /mnt/backup/smi-$(date +\%F).sql.gz
rclone copy /mnt/backup remote:sketchmyinfra-backups
```

**Off-device storage options:**
- **Cloudflare R2** — 10GB free, S3-compatible, no egress fees ⭐ recommended
- **Backblaze B2** — $0.005/GB/month
- **Second Pi/NAS at home** — physical redundancy
- **rsync.net** — paid, very reliable

### Layer 4: Power Loss Protection

Pis hate sudden power loss, especially with SD cards.
- **UPS** (small uninterruptible power supply) — graceful shutdown
- **PiSugar** or similar Pi UPS HAT
- Configure `systemctl poweroff` triggered by UPS signal before battery dies

---

## Production-Grade Pi5 Checklist

1. ☐ Boot from NVMe (not SD)
2. ☐ Docker volumes on external SSD via bind mount
3. ☐ `restart: unless-stopped` on every container (already done)
4. ☐ Systemd unit to start compose on boot
5. ☐ Daily `pg_dump` cron + sync to R2/B2
6. ☐ UPS for power loss protection

---

## Key Takeaways

- **Docker volumes survive container restarts** but live on whatever disk Docker is on — SD card = fragile
- **`restart: unless-stopped`** handles process-level resilience; **systemd** handles boot-level resilience
- **Backups are the actual job** — restart resilience is trivial, disaster resilience is what separates production from "works on my machine"
- **AWS is $18–25/mo** for this stack, but you can run the same thing on a Pi5 for ~$0 (electricity) or Hetzner for $4.50
- **Oracle Cloud Free Tier** is the dark horse — actually free, surprisingly capable, just painful to sign up

## Open Questions / Next Steps
- Add systemd unit file to repo for Pi5 deployment (when accessible)
- Add backup script + cron config to repo
- Decide on R2 vs B2 for off-device backups
- Consider documenting the Pi5 deployment runbook for future reference
