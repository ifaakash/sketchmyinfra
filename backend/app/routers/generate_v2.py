"""V2 generation endpoint — IR-based pipeline.

prompt → Gemini (JSON extraction) → IR → code generator → renderer → response

Replaces the v1 pipeline where Gemini generated raw PlantUML/Mermaid syntax.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.generators.d2_gen import generate_d2
from app.generators.excalidraw_gen import generate_excalidraw
from app.generators.plantuml_gen import generate_plantuml
from app.ir.router import route
from app.ir.schema import DiagramTrack
from app.middleware.auth import get_current_user_optional
from app.models import Generation, User
from app.schemas import GenerateRequest, GenerateV2Response
from app.services.d2 import D2Error, render_d2
from app.services.gemini import GeminiError, extract_diagram_ir
from app.services.plantuml import PlantUMLError, render_puml

# Reuse rate limiting from v1
from app.routers.generate import _check_rate_limit, _get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate-v2"])


@router.post("/v2/generate", response_model=GenerateV2Response)
async def generate_v2(
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
            # Excalidraw path — no server rendering needed
            excalidraw_data = generate_excalidraw(ir)
            renderer = "excalidraw"

        elif renderer == "plantuml":
            code = generate_plantuml(ir)

            # Validate by rendering
            try:
                image = await render_puml(code, "svg")
            except PlantUMLError as render_err:
                logger.warning("PlantUML render failed: %s", render_err)
                # Record failure — no auto-fix with Gemini in v2
                # (the code generator should produce valid syntax)
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
