"""Wikipedia reader service and its stored configuration."""

import os
import re

from minitel.data.services import service

from services.common.config import env_seconds, load_env_file
from services.common.reader import ReaderService

from .source import DEFAULT_USER_AGENT, WikipediaSource

LANG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def _language():
    value = (os.environ.get("WIKIPEDIA_LANG") or "en").strip().lower()
    return value if LANG_PATTERN.match(value) else "en"


def _user_agent():
    value = (os.environ.get("WIKIPEDIA_USER_AGENT") or "").strip()
    return value or DEFAULT_USER_AGENT


@service("wikipedia", description="Wikipedia linked reader")
def build_wikipedia_service():
    load_env_file()
    timeout = env_seconds(
        os.environ.get("WIKIPEDIA_TIMEOUT"), 8.0, minimum=1.0
    )
    return ReaderService(
        WikipediaSource(
            lang=_language(),
            user_agent=_user_agent(),
            timeout=timeout,
        ),
        ttl=3600.0,
        retry_delay=300.0,
        max_entries=64,
    )
