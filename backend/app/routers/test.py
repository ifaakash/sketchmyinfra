import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.generators.plantuml_gen import generate_plantuml
from app.generators.d2_gen import generate_d2
from app.ir.router import route
from app.ir.schema import DiagramTrack
from app.schemas import GenerateRequest
from app.services.d2 import D2Error, render_d2
from app.services.gemini import extract_diagram_ir, GeminiError
from app.services.plantuml import render_puml, PlantUMLError

router = APIRouter(prefix="/api/test", tags=["test"])

OUTPUT_DIR = Path("/backend/test_output")


@router.post("/full-pipeline")
async def test_full_pipeline(req: GenerateRequest):
    """Full pipeline test: prompt → Gemini IR → code generator → render → saved image."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: Extract IR
    try:
        ir = await extract_diagram_ir(req.prompt)
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=f"IR extraction failed: {e}")

    track, renderer = route(ir)

    # Step 2: Generate code
    if track == DiagramTrack.SPATIAL:
        raise HTTPException(status_code=400, detail="Spatial diagrams use Excalidraw — use the main UI")

    if renderer == "plantuml":
        code = generate_plantuml(ir)
    else:
        code = generate_d2(ir)

    # Step 3: Render to SVG and PNG
    results = {}
    for fmt in ("svg", "png"):
        try:
            if renderer == "d2":
                data_uri = await render_d2(code, fmt)
            else:
                data_uri = await render_puml(code, fmt)
        except (PlantUMLError, D2Error) as e:
            raise HTTPException(status_code=502, detail=f"Render failed ({fmt}): {e}")

        header, b64data = data_uri.split(",", 1)
        raw = base64.b64decode(b64data)

        filename = f"test_diagram.{fmt}"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(raw)
        results[fmt] = str(filepath)

    # Save code source
    ext = "puml" if renderer == "plantuml" else "d2"
    code_path = OUTPUT_DIR / f"test_diagram.{ext}"
    code_path.write_text(code)

    return {
        "prompt": req.prompt,
        "category": ir.category.value,
        "renderer": renderer,
        "code": code,
        "files": {
            "source": str(code_path),
            "svg": results.get("svg"),
            "png": results.get("png"),
        },
        "preview": "/api/test/preview",
    }


@router.get("/preview", response_class=HTMLResponse)
async def preview():
    """View the last generated test diagram in the browser."""
    svg_path = OUTPUT_DIR / "test_diagram.svg"

    if not svg_path.exists():
        return HTMLResponse("<h2>No test diagram yet. POST to /api/test/full-pipeline first.</h2>")

    svg_content = svg_path.read_text()

    # Find the source code file (puml or d2)
    code_content = "N/A"
    for ext in ("puml", "d2"):
        p = OUTPUT_DIR / f"test_diagram.{ext}"
        if p.exists():
            code_content = p.read_text()
            break

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head><title>SketchMyInfra — Test Pipeline</title>
    <style>
        body {{ font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
        h1 {{ color: #60a5fa; }}
        .diagram {{ background: white; padding: 1rem; border-radius: 8px; display: inline-block; margin: 1rem 0; }}
        pre {{ background: #1e293b; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.85rem; }}
    </style>
    </head>
    <body>
        <h1>Test Pipeline Result</h1>
        <h3>Rendered Diagram</h3>
        <div class="diagram">{svg_content}</div>
        <h3>Diagram Source</h3>
        <pre>{code_content}</pre>
    </body>
    </html>
    """)
