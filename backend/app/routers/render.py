from fastapi import APIRouter, HTTPException

from app.schemas import RenderRequest, RenderResponse
from app.services.plantuml import render_puml, PlantUMLError

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    try:
        image = await render_puml(req.puml, req.format)
    except PlantUMLError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Render service unavailable")

    return RenderResponse(image=image, format=req.format)
