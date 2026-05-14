import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, get_current_user_optional
from app.models import Drawing, User
from app.schemas import (
    DrawingCreate,
    DrawingListItem,
    DrawingListResponse,
    DrawingOut,
    DrawingUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drawings", tags=["drawings"])

MAX_DRAWINGS_PER_USER = 50


def _generate_share_id() -> str:
    return secrets.token_urlsafe(9)  # 12-char URL-safe string


def _drawing_to_out(d: Drawing) -> DrawingOut:
    return DrawingOut(
        id=str(d.id),
        share_id=d.share_id,
        title=d.title,
        data=d.data,
        thumbnail=d.thumbnail,
        created_at=d.created_at.isoformat(),
        updated_at=d.updated_at.isoformat(),
    )


def _drawing_to_list_item(d: Drawing) -> DrawingListItem:
    return DrawingListItem(
        id=str(d.id),
        share_id=d.share_id,
        title=d.title,
        thumbnail=d.thumbnail,
        created_at=d.created_at.isoformat(),
        updated_at=d.updated_at.isoformat(),
    )


@router.post("", response_model=DrawingOut, status_code=201)
async def create_drawing(
    body: DrawingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Enforce per-user limit
    count_stmt = select(Drawing).where(Drawing.user_id == user.id)
    result = await db.execute(count_stmt)
    if len(result.scalars().all()) >= MAX_DRAWINGS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {MAX_DRAWINGS_PER_USER} drawings reached. Delete some to create new ones.",
        )

    drawing = Drawing(
        user_id=user.id,
        share_id=_generate_share_id(),
        title=body.title,
        data=body.data,
        thumbnail=body.thumbnail,
    )
    db.add(drawing)
    await db.commit()
    await db.refresh(drawing)
    return _drawing_to_out(drawing)


@router.get("", response_model=DrawingListResponse)
async def list_drawings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Drawing)
        .where(Drawing.user_id == user.id)
        .order_by(Drawing.updated_at.desc())
    )
    result = await db.execute(stmt)
    drawings = result.scalars().all()
    return DrawingListResponse(items=[_drawing_to_list_item(d) for d in drawings])


@router.get("/shared/{share_id}", response_model=DrawingOut)
async def get_shared_drawing(
    share_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — no auth required. Used for share links."""
    stmt = select(Drawing).where(Drawing.share_id == share_id)
    result = await db.execute(stmt)
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return _drawing_to_out(drawing)


@router.get("/{drawing_id}", response_model=DrawingOut)
async def get_drawing(
    drawing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drawing).where(Drawing.id == drawing_id, Drawing.user_id == user.id)
    result = await db.execute(stmt)
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return _drawing_to_out(drawing)


@router.put("/{drawing_id}", response_model=DrawingOut)
async def update_drawing(
    drawing_id: str,
    body: DrawingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drawing).where(Drawing.id == drawing_id, Drawing.user_id == user.id)
    result = await db.execute(stmt)
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    if body.title is not None:
        drawing.title = body.title
    if body.data is not None:
        drawing.data = body.data
    if body.thumbnail is not None:
        drawing.thumbnail = body.thumbnail

    await db.commit()
    await db.refresh(drawing)
    return _drawing_to_out(drawing)


@router.delete("/{drawing_id}", status_code=204)
async def delete_drawing(
    drawing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drawing).where(Drawing.id == drawing_id, Drawing.user_id == user.id)
    result = await db.execute(stmt)
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    await db.delete(drawing)
    await db.commit()
