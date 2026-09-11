"""Per-node credential storage on worker machines.

Credentials are stored as JSON at ~/.lfhai/credentials.json with mode 0600.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CREDENTIALS_FILENAME = "credentials.json"


def credentials_path() -> Path:
    return Path.home() / ".lfhai" / CREDENTIALS_FILENAME


def load_credentials(path: Path | None = None) -> dict:
    """Return {controller, node_id, node_secret} or empty dict if absent."""
    p = path or credentials_path()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
            if all(k in data for k in ("controller", "node_id", "node_secret")):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_credentials(
    controller: str, node_id: str, node_secret: str, path: Path | None = None
) -> Path:
    """Persist node credentials, readable only by the current user."""
    p = path or credentials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(
            {"controller": controller, "node_id": node_id, "node_secret": node_secret},
            f,
            indent=2,
        )
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def clear_credentials(path: Path | None = None) -> None:
    p = path or credentials_path()
    try:
        p.unlink()
    except FileNotFoundError:
        pass
