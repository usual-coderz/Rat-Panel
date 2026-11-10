"""Shared writer for parsed rows."""
from __future__ import annotations

from app.db import db, now


async def store_rows(source: dict, rows, currency: str) -> int:
    """Upsert parsed rows for one source. Returns row count."""
    sid = str(source["_id"])
    for row in rows:
        await db.db.prices.update_one(
            {"source_id": sid, "country_code": row.country.iso2},
            {"$set": {
                "source_id": sid,
                "source": source["username"],
                "country": row.country.name,
                "country_code": row.country.iso2,
                "calling_code": row.country.calling_code,
                "price": row.price,
                "free": row.free,
                "new": row.new,
                "spam": row.spam,
                "perm": row.perm,
                "stock": row.stock,
                "cooldown": row.cooldown,
                "currency": currency,
                "updated_at": now(),
            }},
            upsert=True,
        )
    return len(rows)