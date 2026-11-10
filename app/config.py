from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _s(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _i(key: str, default: int) -> int:
    try:
        return int(_s(key) or default)
    except ValueError:
        return default


def _b(key: str, default: bool) -> bool:
    raw = _s(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _ids(key: str) -> tuple[int, ...]:
    return tuple(int(x) for x in _s(key).replace(";", ",").split(",") if x.strip().isdigit())


@dataclass(frozen=True)
class Config:
    api_key: str = _s("API_KEY")
    api_base_url: str = _s("API_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    fernet_key: str = _s("FERNET_KEY")
    mongo_uri: str = _s("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name: str = _s("DB_NAME", "market_analyzer")
    bot_token: str = _s("BOT_TOKEN")
    admin_ids: tuple[int, ...] = _ids("ADMIN_IDS")
    default_currency: str = _s("DEFAULT_CURRENCY", "USD").upper()
    reply_timeout: int = _i("REPLY_TIMEOUT", 45)
    send_delay: int = _i("SEND_DELAY", 2)
    scan_concurrency: int = max(1, _i("SCAN_CONCURRENCY", 3))
    scan_timeout: int = _i("SCAN_TIMEOUT", 900)
    live_fetch: bool = _b("LIVE_FETCH", True)
    live_attempts: int = max(1, _i("LIVE_ATTEMPTS", 3))
    log_level: str = _s("LOG_LEVEL", "INFO").upper()


settings = Config()

if not settings.api_key:
    raise RuntimeError("API_KEY is required")
if not settings.fernet_key:
    raise RuntimeError("FERNET_KEY is required")
if not settings.admin_ids:
    raise RuntimeError("ADMIN_IDS is empty - the bot would ignore every message")