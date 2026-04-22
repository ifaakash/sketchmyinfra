import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user_optional
from app.models import Generation, User
from app.schemas import GenerateRequest, GenerateResponse
from app.services.gemini import generate_puml, fix_puml, GeminiError
from app.services.plantuml import render_puml, PlantUMLError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


def _get_client_ip(request: Request) -> str:
    """Return the real visitor IP.

    Behind Cloudflare Tunnel the request chain is:
      Visitor → Cloudflare Edge → cloudflared pod → Traefik → API pod

    Traefik sees cloudflared as the client, so X-Forwarded-For contains
    the cloudflared pod's internal IP (10.42.x.x) — useless for rate
    limiting. Cloudflare sets CF-Connecting-IP to the real visitor IP
    before tunneling, so we check that first.

    Priority: CF-Connecting-IP → X-Forwarded-For → X-Real-IP → direct peer
    """
    # Cloudflare Tunnel — the only header with the real visitor IP
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    # Standard proxy headers (useful if not behind Cloudflare, e.g. local dev)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


async def _check_rate_limit(
    user: User | None,
    ip: str,
    db: AsyncSession,
) -> None:
    """Count generations in the last 24 hours and raise 429 if over limit.

    Anonymous users are counted by IP (uses idx_generations_ip_date).
    Logged-in users are counted by user_id (uses idx_generations_user_date).
    Pro users are unlimited. The check runs BEFORE the Gemini call so we
    don't waste an API call.
    """
    if user and user.tier == "pro":
        return

    since = datetime.now(timezone.utc) - timedelta(days=1)

    if user:
        limit = settings.rate_limit_free
        stmt = select(func.count()).select_from(Generation).where(
            Generation.user_id == user.id,
            Generation.created_at >= since,
        )
    else:
        limit = settings.rate_limit_anonymous
        stmt = select(func.count()).select_from(Generation).where(
            Generation.user_id.is_(None),
            Generation.ip_address == cast(ip, INET),
            Generation.created_at >= since,
        )

    result = await db.execute(stmt)
    count = result.scalar_one()

    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Daily generation limit reached",
                "limit": limit,
                "used": count,
                "authenticated": user is not None,
            },
        )


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    ip = _get_client_ip(request)

    # Enforce rate limit before calling Gemini (don't waste an API call).
    await _check_rate_limit(user, ip, db)

    try:
        puml = await generate_puml(req.prompt, req.context)
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate diagram")

    # Validate by rendering server-side. If invalid, ask Gemini to fix it once.
    try:
        await render_puml(puml, "svg")
    except PlantUMLError as render_err:
        logger.warning("PlantUML validation failed, attempting auto-fix: %s", render_err)
        try:
            puml = await fix_puml(puml, str(render_err))
            await render_puml(puml, "svg")
            logger.info("Auto-fix succeeded")
        except (PlantUMLError, GeminiError) as fix_err:
            logger.error("Auto-fix failed: %s", fix_err)
            raise HTTPException(
                status_code=502,
                detail="We couldn't generate a valid diagram for this architecture. Try simplifying your prompt or being more specific about the components.",
            )

    # Only record successful generations.
    db.add(
        Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            puml_code=puml,
            ip_address=ip,
        )
    )
    await db.commit()

    return GenerateResponse(puml=puml, prompt_used=req.prompt)
