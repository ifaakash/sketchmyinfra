from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Generation, User
from app.schemas import HistoryItem, HistoryResponse

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Generation)
        .where(
            Generation.user_id == user.id,
            Generation.puml_code.isnot(None),
        )
        .order_by(Generation.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    generations = result.scalars().all()

    return HistoryResponse(
        items=[
            HistoryItem(
                id=str(g.id),
                prompt=g.prompt,
                puml_code=g.puml_code,
                created_at=g.created_at.isoformat(),
            )
            for g in generations
        ]
    )
