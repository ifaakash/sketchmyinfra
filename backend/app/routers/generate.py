from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

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

    # Only record successful generations.
    db.add(
        Generation(
            user_id=user.id if user else None,
            prompt=req.prompt,
            puml_code=puml,
            ip_address=_get_client_ip(request),
        )
    )
    await db.commit()

    return GenerateResponse(puml=puml, prompt_used=req.prompt)
