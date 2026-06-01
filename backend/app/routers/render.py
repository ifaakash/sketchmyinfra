from fastapi import APIRouter, HTTPException

from app.schemas import RenderRequest, RenderResponse
from app.services.plantuml import render_puml, PlantUMLError

router = APIRouter(prefix="/api", tags=["render"])


MERMAID_MARKERS = ("graph ", "flowchart ", "sequenceDiagram", "classDiagram",
                   "stateDiagram", "erDiagram", "gantt", "%%{")


@router.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    # Guard: reject Mermaid code — it must render client-side, not via PlantUML
    code_start = req.puml.strip()[:50]
    if any(code_start.startswith(m) for m in MERMAID_MARKERS):
        raise HTTPException(
            status_code=400,
            detail="This is Mermaid code — it renders in your browser, not via PlantUML. Please refresh the page.",
        )

    try:
        image = await render_puml(req.puml, req.format)
    except PlantUMLError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Render service unavailable")

    return RenderResponse(image=image, format=req.format)
