from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import settings

ACCOUNT_ID = "primary"


def now() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str) -> ObjectId:
    return ObjectId(value)


class DB:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            raise RuntimeError("database not connected")
        return self._db

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(
            settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=8000
        )
        self._db = self._client[settings.db_name]
        await self._client.admin.command("ping")

        await self.db.sources.create_index([("username", ASCENDING)], unique=True)
        await self.db.sources.create_index([("enabled", ASCENDING)])
        await self.db.prices.create_index([("country_code", ASCENDING), ("price", DESCENDING)])
        await self.db.prices.create_index(
            [("source_id", ASCENDING), ("country_code", ASCENDING)], unique=True
        )
        await self.db.prices.create_index([("updated_at", DESCENDING)])
        await self.db.settings.update_one(
            {"_id": "global"},
            {"$setOnInsert": {
                "check_times": ["10:00", "22:00"],
                "currency": settings.default_currency,
            }},
            upsert=True,
        )

    async def close(self) -> None:
        if self._client:
            self._client.close()

    async def settings_doc(self) -> dict[str, Any]:
        doc = await self.db.settings.find_one({"_id": "global"})
        if doc is None:
            doc = {
                "_id": "global",
                "check_times": ["10:00", "22:00"],
                "currency": settings.default_currency,
            }
            await self.db.settings.insert_one(dict(doc))
        return doc

    async def update_settings(self, **fields: Any) -> None:
        fields["updated_at"] = now()
        await self.db.settings.update_one({"_id": "global"}, {"$set": fields}, upsert=True)


db = DB()