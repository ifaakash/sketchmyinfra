"""Gemini AI service — structured IR extraction.

Sends user prompts to the Gemini API and extracts structured diagram
data (JSON mode). The old v1 pipeline (direct PlantUML/Mermaid code
generation with sanitisation) has been removed in favour of the
deterministic IR-based approach.
"""

import logging
import re

import httpx

from app.config import settings
from app.ir.prompts import EXTRACTION_SYSTEM_PROMPT
from app.ir.schema import DiagramIR

logger = logging.getLogger(__name__)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:generateContent"
)


class GeminiError(Exception):
    """Raised when the Gemini API call or response parsing fails."""
    pass


def _strip_fences(text: str) -> str:
    """Strip markdown code fences if Gemini wraps the output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


async def extract_diagram_ir(prompt: str) -> DiagramIR:
    """Extract structured diagram IR from a natural language prompt.

    Uses Gemini's JSON mode for reliable structured output.
    Returns a validated DiagramIR model.

    Raises GeminiError on API failure or invalid JSON.
    """
    payload = {
        "system_instruction": {"parts": [{"text": EXTRACTION_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code != 200:
        error = response.json().get("error", {}).get("message", "Unknown error")
        raise GeminiError(f"Gemini API error: {error}")

    data = response.json()

    # Extract text from response
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GeminiError(f"Unexpected Gemini response structure: {e}")

    # Strip markdown fences if present (safety net)
    text = _strip_fences(text)

    # Parse and validate with Pydantic
    try:
        ir = DiagramIR.model_validate_json(text)
    except Exception as e:
        # Retry once with lower temperature
        logger.warning("IR parse failed, retrying with temperature=0.1: %s", e)
        payload["generationConfig"]["temperature"] = 0.1
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                GEMINI_URL,
                params={"key": settings.gemini_api_key},
                json=payload,
            )
        if response.status_code != 200:
            raise GeminiError(f"Gemini retry failed: {response.status_code}")

        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise GeminiError("Gemini retry returned unexpected structure")

        text = _strip_fences(text)
        try:
            ir = DiagramIR.model_validate_json(text)
        except Exception as parse_err:
            raise GeminiError(f"Failed to parse IR after retry: {parse_err}")

    return ir
