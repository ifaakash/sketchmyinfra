"""Apply the model's fix as exact search/replace edits.

Search/replace instead of unified diffs: LLMs get diff line numbers and
context wrong, but they can copy a snippet exactly. An edit only applies if
`old` occurs exactly once, so a hallucinated snippet fails loudly instead of
patching the wrong place.
"""

import posixpath
from pathlib import Path

from pydantic import BaseModel


class Edit(BaseModel):
    path: str
    old: str
    new: str


class EditError(Exception):
    pass


def check_path(path: str, allowed_prefixes: tuple[str, ...]) -> str:
    """Normalise a repo-relative path and refuse anything outside the allowlist."""
    if not path or path.startswith("/") or "\\" in path:
        raise EditError(f"invalid path: {path!r}")
    norm = posixpath.normpath(path)
    if norm.startswith("..") or "/../" in f"/{norm}/":
        raise EditError(f"path escapes repo: {path!r}")
    if not norm.startswith(allowed_prefixes):
        raise EditError(f"path not allowed: {norm} (allowed: {', '.join(allowed_prefixes)})")
    return norm


def apply_edits(
    repo: Path, edits: list[Edit], allowed_prefixes: tuple[str, ...], max_edits: int
) -> list[str]:
    """Apply all edits or none. Returns the changed paths."""
    if not edits:
        raise EditError("no edits")
    if len(edits) > max_edits:
        raise EditError(f"{len(edits)} edits > max {max_edits}")

    root = repo.resolve()
    staged: dict[str, str] = {}
    for e in edits:
        rel = check_path(e.path, allowed_prefixes)
        # A symlink inside backend/app/ could point anywhere (even at a
        # Dockerfile elsewhere in the repo), so refuse links outright
        target = repo / rel
        if target.is_symlink() or not target.resolve().is_relative_to(root) or not target.is_file():
            raise EditError(f"not a regular file in the repo: {rel}")
        if not e.old:
            raise EditError(f"empty 'old' for {rel}")
        text = staged.get(rel, target.read_text(encoding="utf-8"))
        count = text.count(e.old)
        if count != 1:
            raise EditError(f"'old' found {count} times in {rel} (must be exactly 1)")
        staged[rel] = text.replace(e.old, e.new, 1)

    for rel, text in staged.items():
        (repo / rel).write_text(text, encoding="utf-8")
    return sorted(staged)
