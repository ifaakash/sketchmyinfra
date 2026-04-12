from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user_optional
from app.models import Generation, User
from app.schemas import GenerateRequest, GenerateResponse
from app.services.gemini import generate_puml, GeminiError

router = APIRouter(prefix="/api", tags=["generate"])


def _get_client_ip(request: Request) -> str:
    """Return the real visitor IP, honouring X-Forwarded-For added by Traefik.

    The header may be comma-separated when multiple proxies are in the chain
    (Cloudflare Tunnel → Traefik → pod). The leftmost entry is always the
    original client; subsequent entries are added by each intermediate hop.

    We trust X-Forwarded-For because Traefik is the only ingress point into
    the cluster. If you ever expose the pod directly, re-evaluate this.
    """
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
    The check runs BEFORE the Gemini call so we don't waste an API call.
    """
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
            Generation.ip_address == ip,
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
