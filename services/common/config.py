"""Shared environment and `.env` helpers for services."""

import os
import re
from pathlib import Path

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _env_paths():
    paths = [Path.cwd() / ".env"]
    repo_root = Path(__file__).resolve().parents[2]
    paths.append(repo_root / ".env")
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        yield path


def load_env_file(paths=None):
    """Load simple KEY=VALUE lines without overriding the real environment.

    Missing files are ignored. Values are never printed or logged.
    """
    for path in paths if paths is not None else _env_paths():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, separator, value = line.partition("=")
            if not separator:
                continue
            key = key.strip()
            if not _ENV_KEY.match(key):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def env_csv(value, default):
    if not value:
        return default
    parts = tuple(
        part.strip().upper()
        for part in str(value).split(",")
        if part.strip()
    )
    return parts or default


def env_seconds(value, default, minimum=0.0):
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, seconds)
