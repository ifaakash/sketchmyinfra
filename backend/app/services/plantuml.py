import base64
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PLANTUML_URL = settings.plantuml_server_url

FORMAT_PATHS = {
    "svg": "/svg/",
    "png": "/png/",
}

MIME_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
}

# GitHub include bases -> library dir inside the plantuml image. Generated code
# keeps the public URLs so it stays portable for users; we swap them only on
# the way to our own server. Any ref is mapped to the vendored, pinned copy.
_LIB_URL_PATTERNS = {
    "aws": re.compile(r"https://raw\.githubusercontent\.com/awslabs/aws-icons-for-plantuml/[^/\s]+/dist"),
    "azure": re.compile(r"https://raw\.githubusercontent\.com/plantuml-stdlib/Azure-PlantUML/[^/\s]+/dist"),
    "gcp": re.compile(r"https://raw\.githubusercontent\.com/Crashedmind/PlantUML-icons-GCP/[^/\s]+/dist"),
}


def _localize_includes(puml: str) -> str:
    """Rewrite known icon library URLs to the server's local copies."""
    lib_dir = settings.plantuml_lib_dir.rstrip("/")
    if not lib_dir:
        return puml
    for name, pattern in _LIB_URL_PATTERNS.items():
        puml = pattern.sub(f"{lib_dir}/{name}", puml)
    return puml


def _header_error(response: httpx.Response) -> str | None:
    """Read the error plantuml-server reports in X-PlantUML-Diagram-Error(-Line)."""
    errors = response.headers.get_list("x-plantuml-diagram-error")
    if not errors:
        return None
    lines = response.headers.get_list("x-plantuml-diagram-error-line")
    if lines:
        return f"{errors[0]} (line {lines[0]})"
    return errors[0]


def _extract_error(response_text: str) -> str | None:
    """Extract error message from PlantUML's error SVG.

    PlantUML error SVGs contain a red (#CC0000) text element with the actual
    error message. We look for that specific pattern to avoid false positives
    from user labels that happen to contain words like 'error' or 'syntax'.
    """
    # Primary: look for red-colored error text (PlantUML's error styling)
    red_texts = re.findall(r'fill="(?:#CC0000|#[Rr][Ee][Dd]|red)"[^>]*>([^<]+)</text>', response_text)
    if red_texts:
        return red_texts[0].strip().replace("&#160;", " ").replace("&amp;", "&")

    # Fallback: look for PlantUML's "[From string (line N)]" marker which only
    # appears in error output, then grab the preceding error description
    if "[From string (line" in response_text:
        texts = re.findall(r">([^<]+)</text>", response_text)
        for t in reversed(texts):
            t = t.strip().replace("&#160;", " ").replace("&amp;", "&")
            if "not found" in t.lower() or "syntax error" in t.lower():
                return t

    return None


async def render_puml(puml: str, fmt: str = "svg") -> str:
    """Send PUML code to the PlantUML server and return a base64 data URI."""
    path = FORMAT_PATHS.get(fmt, "/svg/")
    mime = MIME_TYPES.get(fmt, "image/svg+xml")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{PLANTUML_URL}{path}",
            content=_localize_includes(puml).encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )

    if response.status_code != 200:
        # plantuml-server answers 400 for diagram errors, with the reason in headers
        error_detail = _header_error(response)
        if not error_detail and response.headers.get("content-type", "").startswith("image/svg"):
            error_detail = _extract_error(response.text)
        msg = f"PlantUML render failed: {error_detail}" if error_detail else f"PlantUML server returned {response.status_code}"
        logger.error("PlantUML render error: %s\n--- PUML ---\n%s\n--- END ---", msg, puml)
        raise PlantUMLError(msg)

    # PlantUML returns status 200 even for syntax errors — it renders an error SVG instead.
    # Detect and reject those here so the frontend gets a proper error, not a broken image.
    if fmt == "svg":
        error_detail = _extract_error(response.text)
        if error_detail:
            logger.error("PlantUML syntax error (status 200): %s\n--- PUML ---\n%s\n--- END ---", error_detail, puml)
            raise PlantUMLError(f"PlantUML syntax error: {error_detail}")

    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class PlantUMLError(Exception):
    pass
