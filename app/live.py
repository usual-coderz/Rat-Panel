"""On-demand price query for one country, straight from the source bots."""
from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.countries import Country
from app.db import db, now
from app.parser import parse
from app.schemas import PriceOut
from app.store import store_rows
from app.telegram import account

log = logging.getLogger(__name__)


def _attempts(target: Country, query: str) -> list[str]:
    """Try the raw user input first, then the canonical name and ISO code."""
    ordered = list(dict.fromkeys([query.strip(), target.name, target.iso2]))
    return [value for value in ordered if value][: settings.live_attempts]


async def _ask(source: dict, target: Country, query: str) -> list:
    for attempt in _attempts(target, query):
        try:
            text = await asyncio.wait_for(
                account.query_text(source["username"], source.get("start_payload"), attempt),
                settings.reply_timeout + 15,
            )
        except Exception as exc:
            log.warning("live %s (%r) failed: %s", source["username"], attempt, exc)
            continue
        rows = parse(text)
        if rows:
            return rows
    return []


def _to_out(row, source: dict, currency: str) -> PriceOut:
    return PriceOut(
        source=source["username"],
        price=row.price,
        free=row.free,
        new=row.new,
        spam=row.spam,
        perm=row.perm,
        stock=row.stock,
        cooldown=row.cooldown,
        currency=currency,
        updated_at=now(),
    )


async def fetch_live(target: Country, query: str, limit: int) -> list[PriceOut]:
    if not settings.live_fetch or not account.connected:
        return []

    sources = [s async for s in db.db.sources.find({"enabled": True})]
    if not sources:
        return []

    currency = (await db.settings_doc()).get("currency", settings.default_currency)
    sem = asyncio.Semaphore(settings.scan_concurrency)
    found: list[PriceOut] = []

    async def one(source: dict) -> None:
        async with sem:
            rows = await _ask(source, target, query)

            await db.db.sources.update_one(
                {"_id": source["_id"]},
                {"$set": {
                    "status": "active" if rows else "no_data",
                    "last_checked": now(),
                    "last_error": None if rows else "no parsable prices",
                }},
            )
            if not rows:
                return

            await store_rows(source, rows, currency)
            for row in rows:
                if row.country.iso2 == target.iso2:
                    found.append(_to_out(row, source, currency))

    await asyncio.gather(*(one(source) for source in sources))
    found.sort(key=lambda row: row.price, reverse=True)
    return found[:limit]