"""Generation endpoint — IR-based pipeline.

prompt → Gemini (JSON extraction) → IR → code generator → renderer → response
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.generators.d2_gen import generate_d2
from app.generators.excalidraw_gen import generate_excalidraw
from app.generators.plantuml_gen import generate_plantuml
from app.ir.router import route
from app.ir.schema import DiagramTrack
from app.middleware.auth import get_current_user_optional
from app.models import Generation, User
from app.schemas import (
    GenerateRequest,
    GenerateV2Response,
    GenerationStatsItem,
    GenerationStatsResponse,
    GenerationStatusCounts,
    RenderErrorReport,
)
from app.services.d2 import D2Error, render_d2
from app.services.gemini import GeminiError, extract_diagram_ir
from app.services.plantuml import PlantUMLError, render_puml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    """Return the real visitor IP.

    Priority: CF-Connecting-IP → X-Forwarded-For → X-Real-IP → direct peer
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
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
    """Count generations in the last 24 hours and raise 429 if over limit."""
    if user and user.tier == "pro":
        if user.trial_expires_at is None or user.trial_expires_at > datetime.now(timezone.utc):
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


# ---------------------------------------------------------------------------
# Generate endpoint
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerateV2Response)
async def generate(
    req: GenerateRequest,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Generate a diagram using the IR-based pipeline.

    1. Rate limit check
    2. Gemini extracts structured IR (JSON mode)
    3. Route to renderer based on category
    4. Generate code deterministically
    5. Render server-side (PlantUML/D2) or return Excalidraw JSON
    6. Record in DB
    """
    ip = _get_client_ip(request)
    await _check_rate_limit(user, ip, db)

    # --- Phase 1: Extract IR via Gemini ---
    try:
        ir = await extract_diagram_ir(req.prompt)
    except GeminiError as e:
        db.add(Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            status="gemini_error",
            error_message=str(e),
            ip_address=ip,
        ))
        await db.commit()
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during IR extraction")
        db.add(Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            status="gemini_error",
            error_message=str(e),
            ip_address=ip,
        ))
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to understand the diagram request")

    # --- Phase 2: Route to renderer ---
    track, renderer = route(ir)
    category = ir.category.value

    # --- Phase 3: Generate code / JSON ---
    code: str | None = None
    image: str | None = None
    excalidraw_data: dict | None = None

    try:
        if track == DiagramTrack.SPATIAL:
            excalidraw_data = generate_excalidraw(ir)
            renderer = "excalidraw"

        elif renderer == "plantuml":
            code = generate_plantuml(ir)
            try:
                image = await render_puml(code, "svg")
            except PlantUMLError as render_err:
                logger.warning("PlantUML render failed: %s", render_err)
                db.add(Generation(
                    user_id=user.id if user else None,
                    prompt=req.prompt,
                    puml_code=code,
                    renderer=renderer,
                    category=category,
                    ir_data=ir.model_dump(mode="json"),
                    status="autofix_failed",
                    error_message=str(render_err),
                    ip_address=ip,
                ))
                await db.commit()
                raise HTTPException(
                    status_code=502,
                    detail=f"Diagram rendering failed: {render_err}. Try simplifying your prompt.",
                )

        elif renderer == "d2":
            code = generate_d2(ir)
            try:
                image = await render_d2(code, "svg")
            except D2Error as render_err:
                logger.warning("D2 render failed: %s", render_err)
                db.add(Generation(
                    user_id=user.id if user else None,
                    prompt=req.prompt,
                    puml_code=code,
                    renderer=renderer,
                    category=category,
                    ir_data=ir.model_dump(mode="json"),
                    status="autofix_failed",
                    error_message=str(render_err),
                    ip_address=ip,
                ))
                await db.commit()
                raise HTTPException(
                    status_code=502,
                    detail=f"Diagram rendering failed: {render_err}. Try simplifying your prompt.",
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Code generation failed")
        db.add(Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            renderer=renderer,
            category=category,
            status="gemini_error",
            error_message=f"Code generation error: {e}",
            ip_address=ip,
        ))
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to generate diagram code")

    # --- Phase 4: Record success ---
    db.add(Generation(
        user_id=user.id if user else None,
        prompt=req.prompt,
        puml_code=code,
        renderer=renderer,
        category=category,
        ir_data=ir.model_dump(mode="json"),
        status="success",
        ip_address=ip,
    ))
    await db.commit()

    return GenerateV2Response(
        renderer=renderer,
        category=category,
        code=code,
        image=image,
        excalidraw_data=excalidraw_data,
        prompt_used=req.prompt,
    )


# ---------------------------------------------------------------------------
# Stats & error reporting (migrated from v1 generate router)
# ---------------------------------------------------------------------------

@router.post("/generations/render-error")
async def report_render_error(
    req: RenderErrorReport,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Report a client-side render failure for tracking."""
    ip = _get_client_ip(request)
    db.add(Generation(
        user_id=user.id if user else None,
        prompt=req.prompt,
        renderer=req.renderer,
        status="render_error",
        error_message=req.error_message[:500],
        ip_address=ip,
    ))
    await db.commit()
    return {"status": "recorded"}


@router.get("/generations/stats", response_model=GenerationStatsResponse)
async def generation_stats(
    hours: int = 24,
    limit: int = 20,
    user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return generation status counts and recent attempts for the current user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    count_stmt = (
        select(Generation.status, func.count())
        .where(Generation.user_id == user.id, Generation.created_at >= since)
        .group_by(Generation.status)
    )
    count_result = await db.execute(count_stmt)
    raw_counts = {row[0]: row[1] for row in count_result.all()}
    counts = GenerationStatusCounts(
        success=raw_counts.get("success", 0),
        gemini_error=raw_counts.get("gemini_error", 0),
        autofix_failed=raw_counts.get("autofix_failed", 0),
        mermaid_error=raw_counts.get("mermaid_error", 0),
        total=sum(raw_counts.values()),
    )

    recent_stmt = (
        select(Generation)
        .where(Generation.user_id == user.id, Generation.created_at >= since)
        .order_by(Generation.created_at.desc())
        .limit(limit)
    )
    recent_result = await db.execute(recent_stmt)
    recent = [
        GenerationStatsItem(
            id=str(g.id),
            prompt=g.prompt,
            status=g.status,
            error_message=g.error_message,
            created_at=g.created_at.isoformat(),
        )
        for g in recent_result.scalars().all()
    ]

    return GenerationStatsResponse(counts=counts, recent=recent)
