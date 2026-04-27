"""User feedback endpoints.

POST /api/feedback  — submit feedback (authenticated users only)
GET  /api/feedback  — list all feedback (public, displayed on site)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Feedback, User
from app.middleware.auth import get_current_user_optional

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackSubmit(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    message: str = Field(..., min_length=1, max_length=2000)


class FeedbackOut(BaseModel):
    name: str | None
    avatar_url: str | None
    rating: int
    message: str
    created_at: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackSubmit,
    user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        raise HTTPException(status_code=401, detail="Login required to submit feedback")

    # One feedback per user
    existing = await db.execute(
        select(Feedback).where(Feedback.user_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already submitted feedback")

    fb = Feedback(
        user_id=user.id,
        rating=body.rating,
        message=body.message,
    )
    db.add(fb)
    await db.commit()
    return {"status": "ok"}


@router.get("")
async def list_feedback(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feedback, User)
        .join(User, Feedback.user_id == User.id)
        .order_by(Feedback.created_at.desc())
    )
    rows = result.all()
    return [
        FeedbackOut(
            name=user.name or "Anonymous",
            avatar_url=user.avatar_url,
            rating=fb.rating,
            message=fb.message,
            created_at=fb.created_at.isoformat(),
        )
        for fb, user in rows
    ]
