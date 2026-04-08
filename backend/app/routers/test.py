import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.schemas import GenerateRequest
from app.services.gemini import generate_puml, GeminiError
from app.services.plantuml import render_puml, PlantUMLError

router = APIRouter(prefix="/api/test", tags=["test"])

OUTPUT_DIR = Path("/backend/test_output")


@router.post("/full-pipeline")
async def test_full_pipeline(req: GenerateRequest):
    """Full pipeline test: prompt → Gemini → PUML → PlantUML → saved image file.

    Saves the PUML code and rendered image to /backend/test_output/.
    Returns the file paths and a preview URL.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: Generate PUML from prompt
    try:
        puml = await generate_puml(req.prompt, req.context)
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=f"Generate failed: {e}")

    # Step 2: Render to SVG and PNG
    results = {}
    for fmt in ("svg", "png"):
        try:
            data_uri = await render_puml(puml, fmt)
        except PlantUMLError as e:
            raise HTTPException(status_code=502, detail=f"Render failed ({fmt}): {e}")

        # Extract base64 data and save to file
        header, b64data = data_uri.split(",", 1)
        raw = base64.b64decode(b64data)

        filename = f"test_diagram.{fmt}"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(raw)
        results[fmt] = str(filepath)

    # Save PUML source
    puml_path = OUTPUT_DIR / "test_diagram.puml"
    puml_path.write_text(puml)

    return {
        "prompt": req.prompt,
        "puml": puml,
        "files": {
            "puml": str(puml_path),
            "svg": results.get("svg"),
            "png": results.get("png"),
        },
        "preview": "/api/test/preview",
    }


@router.get("/preview", response_class=HTMLResponse)
async def preview():
    """View the last generated test diagram in the browser."""
    svg_path = OUTPUT_DIR / "test_diagram.svg"
    puml_path = OUTPUT_DIR / "test_diagram.puml"

    if not svg_path.exists():
        return HTMLResponse("<h2>No test diagram yet. POST to /api/test/full-pipeline first.</h2>")

    svg_content = svg_path.read_text()
    puml_content = puml_path.read_text() if puml_path.exists() else "N/A"

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
        <h3>PlantUML Source</h3>
        <pre>{puml_content}</pre>
    </body>
    </html>
    """)
