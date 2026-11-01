"""Configuration for the football-data.org sports feed."""

import os
from dataclasses import dataclass

from services.common.config import env_csv, env_seconds, load_env_file

DEFAULT_BASE_URL = "https://api.football-data.org/v4"
DEFAULT_COMPETITIONS = ("PL", "PD", "BL1", "SA", "FL1")


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
            competitions=env_csv(
                env.get("FOOTBALL_COMPETITIONS"), DEFAULT_COMPETITIONS
            ),
            live_interval=env_seconds(
                env.get("FOOTBALL_LIVE_INTERVAL"), 60.0, 30.0
            ),
            day_interval=env_seconds(
                env.get("FOOTBALL_DAY_INTERVAL"), 900.0, 60.0
            ),
            idle_interval=env_seconds(
                env.get("FOOTBALL_IDLE_INTERVAL"), 1800.0, 300.0
            ),
            retry_delay=env_seconds(
                env.get("FOOTBALL_RETRY_DELAY"), 60.0, 15.0
            ),
            timeout=env_seconds(env.get("FOOTBALL_TIMEOUT"), 10.0, 1.0),
        )
