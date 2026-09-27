"""Admin dashboard API.

Auth is a shared query-param key (``?key=``) declared on the router itself, so
every endpoint below is covered by construction rather than by remembering to
add a dependency to each one.
"""

import math
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Drawing, Feedback, Generation, User
from app.schemas import (
    AdminGenerationDetail,
    AdminGenerationItem,
    AdminGenerationsResponse,
    AdminStatsResponse,
    AdminUserItem,
    AdminUsersResponse,
    PageMeta,
    TrendPoint,
)

PER_PAGE_DEFAULT = 15
PER_PAGE_MAX = 100

# Pseudo-status accepted by the ?status= filter, meaning "anything but success".
STATUS_FAILED = "failed"

# Categories are nullable; group them under a stable key instead of null.
UNCATEGORIZED = "uncategorized"

TREND_DAYS = 14

# Prompts are unbounded Text. List responses truncate so a single pathological
# row can't dominate the payload; the detail endpoint returns the full value.
PROMPT_PREVIEW_CHARS = 300
ERROR_PREVIEW_CHARS = 500


def _verify_api_key(key: str = Query(..., alias="key")) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if not secrets.compare_digest(key, settings.admin_api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")


router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(_verify_api_key)],
)


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

class Page:
    """Resolved page/per_page pair plus the derived SQL offset."""

    def __init__(self, page: int, per_page: int) -> None:
        self.page = page
        self.per_page = per_page
        self.offset = (page - 1) * per_page

    def meta(self, total: int) -> PageMeta:
        return PageMeta(
            page=self.page,
            per_page=self.per_page,
            total=total,
            total_pages=page_count(total, self.per_page),
        )


def page_count(total: int, per_page: int) -> int:
    """Number of pages for ``total`` rows. Always at least 1 so an empty table
    still renders as "page 1 of 1" rather than "page 1 of 0"."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return max(1, math.ceil(total / per_page))


def _page_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(PER_PAGE_DEFAULT, ge=1, le=PER_PAGE_MAX),
) -> Page:
    return Page(page, per_page)


async def _count(db: AsyncSession, stmt: Select) -> int:
    """Total row count for a filtered SELECT, without fetching the rows.

    Wrapping the statement in a subquery keeps the count in lockstep with the
    list query's WHERE clause — the two can't drift apart.
    """
    subq = stmt.order_by(None).subquery()
    return (await db.execute(select(func.count()).select_from(subq))).scalar_one()


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit] + "…"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def trend_window_start(now: datetime, days: int = TREND_DAYS) -> datetime:
    """Midnight UTC of the earliest day the trend covers.

    Anchoring to a day boundary rather than "days*24h ago" makes the SQL window
    line up exactly with the calendar columns build_trend emits; otherwise the
    earliest day is a partial window and silently loses rows.
    """
    return datetime.combine(
        now.date() - timedelta(days=days - 1), time.min, tzinfo=timezone.utc
    )


def build_trend(
    rows: list[tuple[date, int, int]],
    end: date,
    days: int = TREND_DAYS,
) -> list[TrendPoint]:
    """Gap-fill grouped daily counts into exactly ``days`` ascending points.

    Postgres only returns rows for days that had generations, but the chart
    needs a fixed number of columns so bar widths stay stable.
    """
    by_day = {day: (total, success) for day, total, success in rows}
    start = end - timedelta(days=days - 1)
    points = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        total, success = by_day.get(day, (0, 0))
        points.append(
            TrendPoint(
                date=day.isoformat(),
                total=total,
                success=success,
                failed=total - success,
            )
        )
    return points


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    async def scalar(stmt) -> int:
        return (await db.execute(stmt)).scalar_one()

    user_count = await scalar(select(func.count()).select_from(User))
    drawing_count = await scalar(select(func.count()).select_from(Drawing))
    feedback_count = await scalar(select(func.count()).select_from(Feedback))
    total_gen = await scalar(select(func.count()).select_from(Generation))

    gen_24h = await scalar(
        select(func.count()).select_from(Generation).where(Generation.created_at >= since_24h)
    )
    gen_7d = await scalar(
        select(func.count()).select_from(Generation).where(Generation.created_at >= since_7d)
    )
    new_users_7d = await scalar(
        select(func.count()).select_from(User).where(User.created_at >= since_7d)
    )

    # Status breakdown (all-time). Everything that isn't "success" counts as a
    # failure, so a newly introduced status can never be silently excluded.
    status_result = await db.execute(
        select(Generation.status, func.count()).group_by(Generation.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}
    success = status_counts.get("success", 0)
    failures = total_gen - success
    failure_rate = (failures / total_gen * 100) if total_gen > 0 else 0.0

    renderer_result = await db.execute(
        select(Generation.renderer, func.count()).group_by(Generation.renderer)
    )
    renderer_counts = {row[0]: row[1] for row in renderer_result.all()}

    category_result = await db.execute(
        select(Generation.category, func.count()).group_by(Generation.category)
    )
    category_counts = {(row[0] or UNCATEGORIZED): row[1] for row in category_result.all()}

    # Bucket in UTC explicitly. Bare date_trunc() uses the session TimeZone, so
    # on a non-UTC server a generation at 02:00 UTC would be filed under the
    # previous or next local day and land in the wrong bar — or in no bar at all.
    day = func.date_trunc("day", func.timezone("UTC", Generation.created_at)).label("day")
    trend_result = await db.execute(
        select(
            day,
            func.count().label("total"),
            # count() ignores NULLs, so the CASE with no ELSE tallies successes.
            func.count(case((Generation.status == "success", 1))).label("success"),
        )
        .where(Generation.created_at >= trend_window_start(now))
        .group_by(day)
        .order_by(day)
    )
    trend = build_trend(
        [(row.day.date(), row.total, row.success) for row in trend_result.all()],
        end=now.date(),
    )

    return AdminStatsResponse(
        total_users=user_count,
        total_generations=total_gen,
        total_drawings=drawing_count,
        total_feedback=feedback_count,
        generations_24h=gen_24h,
        generations_7d=gen_7d,
        new_users_7d=new_users_7d,
        success_count=success,
        failure_count=failures,
        failure_rate=round(failure_rate, 2),
        status_counts=status_counts,
        renderer_counts=renderer_counts,
        category_counts=category_counts,
        trend=trend,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

USER_SORTS = ("newest", "oldest", "most_generations", "recently_active")


@router.get("/users", response_model=AdminUsersResponse)
async def admin_users(
    page: Page = Depends(_page_params),
    q: str | None = Query(None, max_length=200, description="Match email or name"),
    tier: str | None = Query(None, max_length=20),
    sort: str = Query("newest"),
    db: AsyncSession = Depends(get_db),
):
    if sort not in USER_SORTS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {', '.join(USER_SORTS)}")

    # Correlated subqueries rather than a GROUP BY over every user column, and
    # they match the existing partial index idx_generations_user_date.
    gen_count = (
        select(func.count())
        .select_from(Generation)
        .where(Generation.user_id == User.id)
        .scalar_subquery()
        .label("generation_count")
    )
    last_gen = (
        select(func.max(Generation.created_at))
        .where(Generation.user_id == User.id)
        .scalar_subquery()
        .label("last_generation_at")
    )

    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    if tier:
        filters.append(User.tier == tier)

    order = {
        "newest": User.created_at.desc(),
        "oldest": User.created_at.asc(),
        "most_generations": gen_count.desc(),
        "recently_active": last_gen.desc().nullslast(),
    }[sort]

    stmt = select(User, gen_count, last_gen).where(*filters)
    total = await _count(db, select(User.id).where(*filters))

    result = await db.execute(
        stmt.order_by(order, User.id).limit(page.per_page).offset(page.offset)
    )

    items = [
        AdminUserItem(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            oauth_provider=user.oauth_provider,
            tier=user.tier,
            created_at=user.created_at.isoformat(),
            generation_count=count,
            last_generation_at=_iso(last),
        )
        for user, count, last in result.all()
    ]

    return AdminUsersResponse(items=items, meta=page.meta(total))


# ---------------------------------------------------------------------------
# Generations
# ---------------------------------------------------------------------------

def _generation_filters(
    status: str | None,
    renderer: str | None,
    category: str | None,
    q: str | None,
    user_id: uuid.UUID | None,
    anonymous: bool | None,
) -> list:
    filters = []
    if status == STATUS_FAILED:
        filters.append(Generation.status != "success")
    elif status:
        filters.append(Generation.status == status)
    if renderer:
        filters.append(Generation.renderer == renderer)
    if category == UNCATEGORIZED:
        filters.append(Generation.category.is_(None))
    elif category:
        filters.append(Generation.category == category)
    if q:
        filters.append(Generation.prompt.ilike(f"%{q}%"))
    if user_id is not None:
        filters.append(Generation.user_id == user_id)
    elif anonymous is True:
        filters.append(Generation.user_id.is_(None))
    elif anonymous is False:
        filters.append(Generation.user_id.isnot(None))
    return filters


@router.get("/generations", response_model=AdminGenerationsResponse)
async def admin_generations(
    page: Page = Depends(_page_params),
    status: str | None = Query(None, max_length=20, description="Exact status, or 'failed'"),
    renderer: str | None = Query(None, max_length=20),
    category: str | None = Query(None, max_length=30),
    q: str | None = Query(None, max_length=200, description="Substring match on prompt"),
    user_id: uuid.UUID | None = Query(None),
    anonymous: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = _generation_filters(status, renderer, category, q, user_id, anonymous)

    # outerjoin, not join: Generation.user_id is nullable for anonymous
    # generations and an inner join would silently drop every one of them.
    base = (
        select(Generation, User.email)
        .outerjoin(User, Generation.user_id == User.id)
        .where(*filters)
    )
    total = await _count(db, select(Generation.id).where(*filters))

    result = await db.execute(
        base.order_by(Generation.created_at.desc(), Generation.id)
        .limit(page.per_page)
        .offset(page.offset)
    )

    items = [
        AdminGenerationItem(
            id=str(g.id),
            prompt=_truncate(g.prompt, PROMPT_PREVIEW_CHARS),
            status=g.status,
            renderer=g.renderer,
            category=g.category,
            error_message=_truncate(g.error_message, ERROR_PREVIEW_CHARS),
            created_at=g.created_at.isoformat(),
            user_id=str(g.user_id) if g.user_id else None,
            user_email=email,
            ip_address=str(g.ip_address) if g.ip_address else None,
        )
        for g, email in result.all()
    ]

    return AdminGenerationsResponse(items=items, meta=page.meta(total))


@router.get("/generations/{generation_id}", response_model=AdminGenerationDetail)
async def admin_generation_detail(
    generation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Generation, User.email)
        .outerjoin(User, Generation.user_id == User.id)
        .where(Generation.id == generation_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    g, email = row
    return AdminGenerationDetail(
        id=str(g.id),
        prompt=g.prompt,
        status=g.status,
        renderer=g.renderer,
        category=g.category,
        error_message=g.error_message,
        created_at=g.created_at.isoformat(),
        user_id=str(g.user_id) if g.user_id else None,
        user_email=email,
        ip_address=str(g.ip_address) if g.ip_address else None,
        puml_code=g.puml_code,
        ir_data=g.ir_data,
    )
