"""Fetch capacities from every enabled source and store parsed prices."""
from __future__ import annotations

import logging
from typing import Any

from app.db import db, now
from app.parser import parse
from app.telegram import account

log = logging.getLogger(__name__)


async def run_scan() -> dict[str, Any]:
    if not account.connected:
        return {"status": "no_account", "sources": 0, "records": 0, "errors": []}

    sources = [s async for s in db.db.sources.find({"enabled": True})]
    result: dict[str, Any] = {"status": "completed", "sources": len(sources), "records": 0, "errors": []}

    for source in sources:
        try:
            text = await account.fetch_capacity(source["username"], source.get("start_payload"))
        except Exception as exc:
            log.warning("source %s failed: %s", source["username"], exc)
            result["errors"].append(f"{source['username']}: {exc}")
            await db.db.sources.update_one(
                {"_id": source["_id"]}, {"$set": {"status": "error", "last_error": str(exc)[:250]}}
            )
            continue

        rows = parse(text)
        for country, price in rows:
            await db.db.prices.update_one(
                {"source_id": str(source["_id"]), "country_code": country.iso2},
                {"$set": {
                    "source_id": str(source["_id"]),
                    "source": source["username"],
                    "country": country.name,
                    "country_code": country.iso2,
                    "calling_code": country.calling_code,
                    "price": price,
                    "currency": (await db.settings_doc()).get("currency", "USD"),
                    "updated_at": now(),
                }},
                upsert=True,
            )

        result["records"] += len(rows)
        await db.db.sources.update_one(
            {"_id": source["_id"]},
            {"$set": {
                "status": "active" if rows else "no_data",
                "last_checked": now(),
                "last_error": None if rows else "no parsable prices",
            }},
        )

    if not sources:
        result["status"] = "no_sources"
    return result