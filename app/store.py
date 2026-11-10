"""Shared writer for parsed rows."""
from __future__ import annotations

from app.db import db, now


async def store_rows(source: dict, rows, currency: str) -> int:
    """Upsert parsed (country, price) pairs for one source. Returns row count."""
    sid = str(source["_id"])
    for country, price in rows:
        await db.db.prices.update_one(
            {"source_id": sid, "country_code": country.iso2},
            {"$set": {
                "source_id": sid,
                "source": source["username"],
                "country": country.name,
                "country_code": country.iso2,
                "calling_code": country.calling_code,
                "price": price,
                "currency": currency,
                "updated_at": now(),
            }},
            upsert=True,
        )
    return len(rows)