"""D2 diagram renderer — subprocess wrapper.

Renders D2 code to SVG/PNG by invoking the D2 CLI binary.
D2 is installed in the Docker image and runs as a subprocess.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class D2Error(Exception):
    """Raised when D2 rendering fails."""
    pass


async def render_d2(code: str, fmt: str = "svg") -> str:
    """Render D2 code to an image via the D2 CLI.

    Args:
        code: Valid D2 diagram source code.
        fmt: Output format — "svg" or "png".

    Returns:
        Base64 data URI string (e.g. "data:image/svg+xml;base64,...").

    Raises:
        D2Error: If D2 exits with a non-zero code or times out.
    """
    # D2 PNG requires Playwright (browser engine) — force SVG only
    if fmt != "svg":
        fmt = "svg"

    # Write source to a temp file
    tmp_dir = tempfile.mkdtemp(prefix="d2_")
    src_path = os.path.join(tmp_dir, "input.d2")
    out_path = os.path.join(tmp_dir, f"output.{fmt}")

    try:
        Path(src_path).write_text(code, encoding="utf-8")

        d2_bin = settings.d2_binary_path
        layout = settings.d2_layout_engine
        timeout = settings.d2_timeout_seconds

        cmd = [d2_bin, "--layout", layout, src_path, out_path]

        logger.debug("Running D2: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise D2Error(f"D2 rendering timed out after {timeout}s")

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            # Truncate long error messages
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            logger.warning("D2 render failed (rc=%d): %s", proc.returncode, error_msg)
            raise D2Error(f"D2 render failed: {error_msg}")

        # Read the output file
        out_file = Path(out_path)
        if not out_file.exists():
            raise D2Error("D2 produced no output file")

        data = out_file.read_bytes()
        if not data:
            raise D2Error("D2 output file is empty")

        mime = "image/svg+xml" if fmt == "svg" else "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"

    finally:
        # Cleanup temp files
        for f in (src_path, out_path):
            try:
                os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
