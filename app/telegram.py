"""Single authorized account via Telethon."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from app import crypto
from app.config import settings
from app.db import ACCOUNT_ID, db, now

log = logging.getLogger(__name__)

CAP_COMMANDS = ("/cap", "/capacity")


class Account:
    def __init__(self) -> None:
        self._client: TelegramClient | None = None
        self._conn_lock = asyncio.Lock()
        self._chat_locks: dict[str, asyncio.Lock] = {}

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected()

    def _chat_lock(self, handle: str) -> asyncio.Lock:
        return self._chat_locks.setdefault(handle, asyncio.Lock())

    def _build(self, api_id: int, api_hash: str, session_string: str) -> TelegramClient:
        return TelegramClient(
            StringSession(session_string), api_id, api_hash, device_model="MarketAnalyzer"
        )

    async def connect(self, api_id: int, api_hash: str, session_string: str) -> dict[str, Any]:
        async with self._conn_lock:
            await self._drop()
            client = self._build(api_id, api_hash, session_string)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise ValueError("session not authorized")

            me = await client.get_me()
            doc = {
                "_id": ACCOUNT_ID,
                "api_id": api_id,
                "api_hash_enc": crypto.encrypt(api_hash),
                "session_enc": crypto.encrypt(session_string),
                "session_masked": crypto.mask(session_string),
                "name": " ".join(filter(None, [me.first_name, me.last_name])) or "account",
                "username": me.username,
                "phone": me.phone,
                "connected_at": now(),
            }
            await db.db.account.replace_one({"_id": ACCOUNT_ID}, doc, upsert=True)
            self._client = client
            log.info("account connected: %s", doc["phone"])
            return doc

    async def restore(self) -> None:
        doc = await db.db.account.find_one({"_id": ACCOUNT_ID})
        if not doc:
            return
        try:
            client = self._build(
                doc["api_id"], crypto.decrypt(doc["api_hash_enc"]), crypto.decrypt(doc["session_enc"])
            )
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("session no longer authorized")
            self._client = client
            log.info("account restored")
        except Exception as exc:
            log.error("account restore failed: %s", exc)

    async def disconnect(self) -> bool:
        async with self._conn_lock:
            existed = await db.db.account.delete_one({"_id": ACCOUNT_ID})
            await self._drop()
            return existed.deleted_count > 0

    async def _drop(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._chat_locks.clear()

    async def _send(self, handle: str, text: str) -> int:
        client = self._client
        if client is None:
            raise RuntimeError("account not connected")
        try:
            message = await client.send_message(handle, text)
        except errors.FloodWaitError as exc:
            log.warning("flood wait %ss", exc.seconds)
            await asyncio.sleep(exc.seconds + 1)
            message = await client.send_message(handle, text)
        return message.id

    async def _await_reply(self, handle: str, baseline: int) -> str:
        client = self._client
        if client is None:
            return ""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.reply_timeout
        while loop.time() < deadline:
            await asyncio.sleep(1.5)
            try:
                messages = await client.get_messages(handle, limit=5, min_id=baseline)
            except errors.FloodWaitError as exc:
                await asyncio.sleep(exc.seconds + 1)
                continue
            incoming = [m for m in messages if not m.out and m.text]
            if incoming:
                return max(incoming, key=lambda m: m.id).text
        return ""

    async def fetch_capacity(self, username: str, start_payload: str | None) -> str:
        """Send /start (with payload) then /cap, falling back to /capacity."""
        handle = username if username.startswith("@") else f"@{username}"
        async with self._chat_lock(handle):
            if start_payload:
                await self._send(handle, f"/start {start_payload}")
                await asyncio.sleep(settings.send_delay)

            baseline = await self._send(handle, CAP_COMMANDS[0])
            text = await self._await_reply(handle, baseline)
            if text:
                return text

            baseline = await self._send(handle, CAP_COMMANDS[1])
            text = await self._await_reply(handle, baseline)
            await asyncio.sleep(settings.send_delay)
            return text


account = Account()