"""Configuration for the football-data.org sports feed."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.football-data.org/v4"
DEFAULT_COMPETITIONS = ("PL", "PD", "BL1", "SA", "FL1")

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


def _csv(value, default):
    if not value:
        return default
    parts = tuple(
        part.strip().upper()
        for part in str(value).split(",")
        if part.strip()
    )
    return parts or default


def _seconds(value, default, minimum):
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, seconds)


@dataclass(frozen=True)
class SportsConfig:
    token: str = ""
    base_url: str = DEFAULT_BASE_URL
    competitions: tuple[str, ...] = DEFAULT_COMPETITIONS
    live_interval: float = 60.0
    day_interval: float = 900.0
    idle_interval: float = 1800.0
    retry_delay: float = 60.0
    timeout: float = 10.0

    @property
    def configured(self):
        return bool(self.token)

    @classmethod
    def from_env(cls, env=None, load_file=True):
        if env is None:
            if load_file:
                load_env_file()
            env = os.environ
        return cls(
            token=(env.get("FOOTBALL_API_KEY")
                   or env.get("FOOTBALL_DATA_TOKEN")
                   or "").strip(),
            base_url=(env.get("FOOTBALL_API_BASE") or DEFAULT_BASE_URL)
            .strip()
            .rstrip("/"),
            competitions=_csv(
                env.get("FOOTBALL_COMPETITIONS"), DEFAULT_COMPETITIONS
            ),
            live_interval=_seconds(
                env.get("FOOTBALL_LIVE_INTERVAL"), 60.0, 30.0
            ),
            day_interval=_seconds(
                env.get("FOOTBALL_DAY_INTERVAL"), 900.0, 60.0
            ),
            idle_interval=_seconds(
                env.get("FOOTBALL_IDLE_INTERVAL"), 1800.0, 300.0
            ),
            retry_delay=_seconds(
                env.get("FOOTBALL_RETRY_DELAY"), 60.0, 15.0
            ),
            timeout=_seconds(env.get("FOOTBALL_TIMEOUT"), 10.0, 1.0),
        )
