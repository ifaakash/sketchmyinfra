import base64

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


async def render_puml(puml: str, fmt: str = "svg") -> str:
    """Send PUML code to the PlantUML server and return a base64 data URI."""
    path = FORMAT_PATHS.get(fmt, "/svg/")
    mime = MIME_TYPES.get(fmt, "image/svg+xml")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{PLANTUML_URL}{path}",
            content=puml.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    if response.status_code != 200:
        raise PlantUMLError(f"PlantUML server returned {response.status_code}")

    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class PlantUMLError(Exception):
    pass
