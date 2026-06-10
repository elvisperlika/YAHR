"""Helpers for reading/writing the project ``.env`` file.

Shared by the ``setup-*`` commands so they agree on the file location and on how
key/value pairs are upserted.
"""

from pathlib import Path

ENV_FILE = Path(".env")


def upsert_env(path: Path, key: str, value: str) -> bool:
    """Set ``key=value`` in the env file at ``path``.

    Existing lines for other keys are preserved. Returns ``True`` if the key was
    already present (and updated), ``False`` if it was newly added.
    """
    line = f"{key}={value}"

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()

    found = False
    for i, current in enumerate(lines):
        stripped = current.lstrip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            lines[i] = line
            found = True
            break

    if not found:
        lines.append(line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found
