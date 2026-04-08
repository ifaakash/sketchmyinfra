import base64
import re

import httpx

from app.config import settings

PLANTUML_URL = settings.plantuml_server_url

FORMAT_PATHS = {
    "svg": "/svg/",
    "png": "/png/",
}

MIME_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
}


def _extract_error(response_text: str) -> str | None:
    """Extract error message from PlantUML's error SVG."""
    texts = re.findall(r">([^<]+)</text>", response_text)
    for t in reversed(texts):
        t = t.strip().replace("&#160;", " ").replace("&amp;", "&")
        if "not found" in t.lower() or "error" in t.lower() or "syntax" in t.lower():
            return t
    return None


async def render_puml(puml: str, fmt: str = "svg") -> str:
    """Send PUML code to the PlantUML server and return a base64 data URI."""
    path = FORMAT_PATHS.get(fmt, "/svg/")
    mime = MIME_TYPES.get(fmt, "image/svg+xml")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{PLANTUML_URL}{path}",
            content=puml.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    if response.status_code != 200:
        error_detail = _extract_error(response.text) if response.headers.get("content-type", "").startswith("image/svg") else None
        msg = f"PlantUML render failed: {error_detail}" if error_detail else f"PlantUML server returned {response.status_code}"
        raise PlantUMLError(msg)

    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class PlantUMLError(Exception):
    pass
