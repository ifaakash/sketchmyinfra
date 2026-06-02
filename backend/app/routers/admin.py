from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Generation, User
from app.schemas import AdminStatsResponse, GenerationStatsItem

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _verify_api_key(key: str = Query(..., alias="key")) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    _: None = Depends(_verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    # Total users
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    # Total generations
    total_gen = (await db.execute(select(func.count()).select_from(Generation))).scalar_one()

    # Generations in last 24h
    gen_24h = (await db.execute(
        select(func.count()).select_from(Generation).where(Generation.created_at >= since_24h)
    )).scalar_one()

    # Generations in last 7d
    gen_7d = (await db.execute(
        select(func.count()).select_from(Generation).where(Generation.created_at >= since_7d)
    )).scalar_one()

    # Status breakdown (all-time)
    status_stmt = select(Generation.status, func.count()).group_by(Generation.status)
    status_result = await db.execute(status_stmt)
    status_counts = {row[0]: row[1] for row in status_result.all()}

    success = status_counts.get("success", 0)
    gemini_err = status_counts.get("gemini_error", 0)
    autofix_err = status_counts.get("autofix_failed", 0)
    mermaid_err = status_counts.get("mermaid_error", 0)
    failure_rate = ((gemini_err + autofix_err + mermaid_err) / total_gen * 100) if total_gen > 0 else 0.0

    # Recent 50 failures
    fail_stmt = (
        select(Generation)
        .where(Generation.status != "success")
        .order_by(Generation.created_at.desc())
        .limit(50)
    )
    fail_result = await db.execute(fail_stmt)
    recent_failures = [
        GenerationStatsItem(
            id=str(g.id),
            prompt=g.prompt,
            status=g.status,
            error_message=g.error_message,
            created_at=g.created_at.isoformat(),
        )
        for g in fail_result.scalars().all()
    ]

    return AdminStatsResponse(
        total_users=user_count,
        total_generations=total_gen,
        generations_24h=gen_24h,
        generations_7d=gen_7d,
        success_count=success,
        gemini_error_count=gemini_err,
        autofix_failed_count=autofix_err,
        mermaid_error_count=mermaid_err,
        failure_rate=round(failure_rate, 2),
        recent_failures=recent_failures,
    )
