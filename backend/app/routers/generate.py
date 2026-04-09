from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user_optional
from app.models import Generation, User
from app.schemas import GenerateRequest, GenerateResponse
from app.services.gemini import generate_puml, GeminiError

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        puml = await generate_puml(req.prompt, req.context)
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate diagram")

    # Only record successful generations — we want the table to reflect
    # "diagrams we actually served", which is also what rate limiting (later)
    # will care about. `request.client.host` is whatever the ASGI server sees;
    # behind Traefik in dev that's the ingress pod IP. Good enough for now —
    # switch to X-Forwarded-For parsing when we wire real per-IP rate limits.
    db.add(
        Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            puml_code=puml,
            ip_address=request.client.host if request.client else "0.0.0.0",
        )
    )
    await db.commit()

    return GenerateResponse(puml=puml, prompt_used=req.prompt)
