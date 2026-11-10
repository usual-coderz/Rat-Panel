"""One-time: generate a Telethon StringSession for the collector account."""
from __future__ import annotations

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = await client.get_me()
        print("\nlogged in as", me.first_name, me.phone)
        print("\nSESSION_STRING:\n" + client.session.save() + "\n")


if __name__ == "__main__":
    asyncio.run(main())