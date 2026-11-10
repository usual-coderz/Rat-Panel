"""Market Analyzer API. Swagger at /docs."""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from app import crypto
from app.config import settings
from app.db import ACCOUNT_ID, db, now, oid
from app.countries import resolve
from app.schemas import AccountIn, AccountOut, PriceOut, SettingsIn, SourceIn, SourceOut, SourceUpdate
from app.scanner import run_scan
from app.telegram import account

logging.basicConfig(level=settings.log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("api")

DESCRIPTION = """
Price comparison across authorized Telegram capacity bots.

All endpoints require the `X-API-Key` header.

- **Account** — one authorized account at a time. `POST /account` replaces the current one.
- **Sources** — add bots to query. `start_payload` is used for deep links like `?start=Prices`.
- **Scan** — sends `/cap` (fallback `/capacity`) to every enabled source and stores parsed prices.
- **Prices** — read the stored, sorted prices for one country.
- **Settings** — check times are stored only; the caller triggers `/scan`.
"""

TAGS = [
    {"name": "account", "description": "Single authorized Telegram account."},
    {"name": "sources", "description": "Capacity bots to query."},
    {"name": "scan", "description": "Run collection."},
    {"name": "prices", "description": "Read stored prices."},
    {"name": "settings", "description": "Currency and check times."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    await account.restore()
    yield
    await account._drop()
    await db.close()


app = FastAPI(title="Market Analyzer API", version="1.0.0", description=DESCRIPTION,
              openapi_tags=TAGS, lifespan=lifespan)


async def auth(x_api_key: str = Header(default="", description="Shared API key")) -> None:
    if not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(401, "invalid api key")


# ------------------------------- account --------------------------------- #
@app.get("/account", tags=["account"], response_model=AccountOut, dependencies=[Depends(auth)])
async def get_account():
    doc = await db.db.account.find_one({"_id": ACCOUNT_ID})
    if not doc:
        return AccountOut(connected=False)
    return AccountOut(
        connected=account.connected, name=doc.get("name"), username=doc.get("username"),
        phone=doc.get("phone"), session_masked=doc.get("session_masked"),
        connected_at=doc.get("connected_at"),
    )


@app.post("/account", tags=["account"], response_model=AccountOut, dependencies=[Depends(auth)])
async def set_account(body: AccountIn):
    try:
        doc = await account.connect(body.api_id, body.api_hash, body.session_string)
    except Exception as exc:
        raise HTTPException(400, f"account rejected: {exc}") from exc
    return AccountOut(
        connected=True, name=doc["name"], username=doc["username"], phone=doc["phone"],
        session_masked=doc["session_masked"], connected_at=doc["connected_at"],
    )


@app.delete("/account", tags=["account"], dependencies=[Depends(auth)])
async def delete_account():
    if not await account.disconnect():
        raise HTTPException(404, "no account")
    return {"deleted": True}


# ------------------------------- sources --------------------------------- #
def _source_out(doc: dict) -> SourceOut:
    return SourceOut(
        id=str(doc["_id"]), username=doc["username"], start_payload=doc.get("start_payload"),
        enabled=doc.get("enabled", True), status=doc.get("status", "new"),
        last_checked=doc.get("last_checked"), last_error=doc.get("last_error"),
    )


@app.get("/sources", tags=["sources"], response_model=list[SourceOut], dependencies=[Depends(auth)])
async def list_sources():
    return [_source_out(d) async for d in db.db.sources.find({}).sort("username", 1)]


@app.post("/sources", tags=["sources"], response_model=SourceOut, status_code=201,
          dependencies=[Depends(auth)])
async def add_source(body: SourceIn):
    username = body.username if body.username.startswith("@") else f"@{body.username}"
    if await db.db.sources.find_one({"username": username}):
        raise HTTPException(409, "source already exists")
    doc = {"username": username, "start_payload": body.start_payload, "enabled": True,
           "status": "new", "last_checked": None, "last_error": None, "created_at": now()}
    doc["_id"] = (await db.db.sources.insert_one(dict(doc))).inserted_id
    return _source_out(doc)


@app.patch("/sources/{sid}", tags=["sources"], response_model=SourceOut, dependencies=[Depends(auth)])
async def update_source(sid: str, body: SourceUpdate):
    doc = await db.db.sources.find_one({"_id": oid(sid)})
    if not doc:
        raise HTTPException(404, "not found")

    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "username" in fields and not fields["username"].startswith("@"):
        fields["username"] = f"@{fields['username']}"
    if fields:
        await db.db.sources.update_one({"_id": doc["_id"]}, {"$set": fields})
        doc.update(fields)
    return _source_out(doc)


@app.delete("/sources/{sid}", tags=["sources"], dependencies=[Depends(auth)])
async def delete_source(sid: str):
    if not (await db.db.sources.delete_one({"_id": oid(sid)})).deleted_count:
        raise HTTPException(404, "not found")
    await db.db.prices.delete_many({"source_id": sid})
    return {"deleted": True}


# -------------------------------- scan ----------------------------------- #
@app.post("/scan", tags=["scan"], dependencies=[Depends(auth)])
async def scan():
    if not account.connected:
        raise HTTPException(409, "no account connected")
    return await run_scan()


# ------------------------------- prices ---------------------------------- #
@app.get("/prices", tags=["prices"], response_model=list[PriceOut], dependencies=[Depends(auth)])
async def prices(country: str = Query(description="Country name, ISO code or calling code"),
                 limit: int = 10):
    target = resolve(country)
    if target is None:
        raise HTTPException(404, "unknown country")
    return [
        PriceOut(source=d["source"], price=d["price"], currency=d.get("currency", "USD"),
                 updated_at=d["updated_at"])
        async for d in db.db.prices.find({"country_code": target.iso2}).sort("price", -1).limit(limit)
    ]


# ------------------------------ settings --------------------------------- #
@app.get("/settings", tags=["settings"], dependencies=[Depends(auth)])
async def get_settings():
    doc = await db.settings_doc()
    return {"check_times": doc.get("check_times", []), "currency": doc.get("currency", "USD")}


@app.patch("/settings", tags=["settings"], dependencies=[Depends(auth)])
async def patch_settings(body: SettingsIn):
    fields: dict = {}
    if body.check_times is not None:
        if len(body.check_times) > 2:
            raise HTTPException(400, "at most two check times")
        for value in body.check_times:
            hour, _, minute = value.partition(":")
            if not (hour.isdigit() and minute.isdigit() and 0 <= int(hour) < 24 and 0 <= int(minute) < 60):
                raise HTTPException(400, f"bad time: {value}")
        fields["check_times"] = body.check_times
    if body.currency:
        fields["currency"] = body.currency.upper()
    if fields:
        await db.update_settings(**fields)
    return await get_settings()


# ------------------------------- health ---------------------------------- #
@app.get("/health", tags=["account"])
async def health():
    await db.db.command("ping")
    return {
        "ok": True,
        "account_connected": account.connected,
        "sources": await db.db.sources.count_documents({"enabled": True}),
        "countries": len(await db.db.prices.distinct("country_code")),
    }