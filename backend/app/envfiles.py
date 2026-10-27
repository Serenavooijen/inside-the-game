"""Local settings files for the backend: backend/.env and backend/.env.foundry-agents.

The app reads them at start-up, so `uv run uvicorn app.main:app --reload` gets TACTICS_ENABLED, MODEL_PROVIDER,
the Foundry agent versions and ITG_LANGUAGES without --env-file. Same format as run_fixtures.py: KEY=value per line,
# for comments. A variable that is already in the environment (shell, Container App) always wins; a missing file
is skipped. ITG_ENV_FILES (comma-separated paths) overrides the list; empty turns it off (the tests do that).
"""
import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_FILES = [BACKEND / ".env", BACKEND / ".env.foundry-agents"]


def env_files() -> list[Path]:
    raw = os.environ.get("ITG_ENV_FILES")
    if raw is None:
        return DEFAULT_FILES
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def load_env_files(paths: list[Path] | None = None) -> list[str]:
    """Set every KEY=value of the files that is not in the environment yet. Returns the keys it set."""
    loaded = []
    for path in env_files() if paths is None else paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key and key not in os.environ:
                os.environ[key] = value.strip("'\"")
                loaded.append(key)
    return loaded
