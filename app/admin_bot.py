"""Minimal admin panel that calls the API."""
from __future__ import annotations

import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("bot")

router = Router()
HEADERS = {"X-API-Key": settings.api_key}
TIMEOUT = httpx.Timeout(settings.scan_timeout + 60, connect=15)


class Admin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user) and event.from_user.id in settings.admin_ids


router.message.filter(Admin())
router.callback_query.filter(Admin())


class Flow(StatesGroup):
    account = State()
    source = State()
    price = State()
    times = State()


async def api(method: str, path: str, **kwargs):
    try:
        async with httpx.AsyncClient(base_url=settings.api_base_url, headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        log.warning("api %s %s failed: %s", method, path, exc)
        return 503, {"detail": f"api unreachable ({exc.__class__.__name__})"}
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"detail": resp.text[:200]}


def back(to: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data=to)]])


def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Account", callback_data="account"),
         InlineKeyboardButton(text="🤖 Sources", callback_data="sources")],
        [InlineKeyboardButton(text="🚀 Scan", callback_data="scan"),
         InlineKeyboardButton(text="💰 Prices", callback_data="price")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
    ])


async def home_view():
    _, health = await api("GET", "/health")
    _, acc = await api("GET", "/account")
    text = (
        "📊 <b>MARKET ANALYZER</b>\n\n"
        f"👤 Account: <b>{'connected' if acc.get('connected') else 'none'}</b>\n"
        f"🤖 Sources: <b>{health.get('sources', 0)}</b>\n"
        f"🌍 Countries: <b>{health.get('countries', 0)}</b>"
    )
    return text, home_kb()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    text, kb = await home_view()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "home")
async def home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await home_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


# ------------------------------- account --------------------------------- #
async def account_render(cb: CallbackQuery, state: FSMContext | None):
    if state is not None:
        await state.clear()
    _, acc = await api("GET", "/account")
    if not acc.get("connected"):
        text = "👤 <b>ACCOUNT</b>\n\nnone connected\n\nSend <code>api_id|api_hash|session_string</code>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Connect", callback_data="acc_add")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="home")],
        ])
    else:
        text = (
            "👤 <b>ACCOUNT</b>\n\n"
            f"name: <b>{acc.get('name')}</b>\nphone: <b>{acc.get('phone')}</b>\n"
            f"session: <code>{acc.get('session_masked')}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♻️ Replace", callback_data="acc_add")],
            [InlineKeyboardButton(text="🗑 Remove", callback_data="acc_del")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="home")],
        ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "account")
async def account_view(cb: CallbackQuery, state: FSMContext):
    await account_render(cb, state)


@router.callback_query(F.data == "acc_add")
async def ask_account(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.account)
    await cb.message.edit_text(
        "Send <code>api_id|api_hash|session_string</code>", reply_markup=back("account")
    )
    await cb.answer()


@router.message(Flow.account)
async def save_account(message: Message, state: FSMContext):
    parts = [p.strip() for p in (message.text or "").split("|")]
    if len(parts) != 3 or not parts[0].isdigit():
        await message.answer("❌ Expected <code>api_id|api_hash|session</code>")
        return
    code, data = await api("POST", "/account", json={
        "api_id": int(parts[0]), "api_hash": parts[1], "session_string": parts[2],
    })
    await state.clear()
    await message.answer(
        f"✅ Connected as {data.get('phone')}" if code == 200 else f"❌ {data.get('detail')}",
        reply_markup=back("account"),
    )


@router.callback_query(F.data == "acc_del")
async def delete_account(cb: CallbackQuery, state: FSMContext):
    await api("DELETE", "/account")
    await account_render(cb, state)


# ------------------------------- sources --------------------------------- #
def sources_kb(rows: list[dict]) -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(text="➕ Add source", callback_data="src_add")]]
    for row in rows:
        mark = "🟢" if row["enabled"] else "⚪"
        kb.append([
            InlineKeyboardButton(text=f"{mark} {row['username']}", callback_data=f"src_tg:{row['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"src_del:{row['id']}"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def sources_view():
    _, rows = await api("GET", "/sources")
    body = "\n".join(f"{'🟢' if r['enabled'] else '⚪'} {r['username']} — {r['status']}" for r in rows) or "none"
    return (
        f"🤖 <b>SOURCES</b>\n\n{body}\n\nAdd: <code>@username</code> or <code>@username|start_payload</code>\n"
        "Example: <code>@TGLionAPI_bot|Prices</code>",
        sources_kb(rows),
    )


@router.callback_query(F.data == "sources")
async def sources_list(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await sources_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "src_add")
async def ask_source(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.source)
    await cb.message.edit_text(
        "Send <code>@username</code> or <code>@username|start_payload</code>", reply_markup=back("sources")
    )
    await cb.answer()


@router.message(Flow.source)
async def save_source(message: Message, state: FSMContext):
    username, _, payload = (message.text or "").partition("|")
    code, data = await api("POST", "/sources", json={
        "username": username.strip(), "start_payload": payload.strip() or None,
    })
    await state.clear()
    await message.answer(
        f"✅ Added {data.get('username')}" if code == 201 else f"❌ {data.get('detail')}",
        reply_markup=back("sources"),
    )


@router.callback_query(F.data.startswith("src_tg:"))
async def toggle_source(cb: CallbackQuery):
    sid = cb.data.split(":", 1)[1]
    _, rows = await api("GET", "/sources")
    current = next((r for r in rows if r["id"] == sid), None)
    if current:
        await api("PATCH", f"/sources/{sid}", json={"enabled": not current["enabled"]})
    text, kb = await sources_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("updated")


@router.callback_query(F.data.startswith("src_del:"))
async def remove_source(cb: CallbackQuery):
    await api("DELETE", f"/sources/{cb.data.split(':', 1)[1]}")
    text, kb = await sources_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("deleted")


# -------------------------------- scan ----------------------------------- #
@router.callback_query(F.data == "scan")
async def scan(cb: CallbackQuery):
    await cb.answer("scanning")
    await cb.message.edit_text("🚀 Sending /cap to all sources…", reply_markup=back())
    code, data = await api("POST", "/scan")
    if code != 200:
        await cb.message.edit_text(f"⚠️ {data.get('detail')}", reply_markup=back())
        return
    body = f"✅ done\nsources: {data['sources']}\nrecords: {data['records']}"
    if data["errors"]:
        body += "\n\n⚠️ failures:\n" + "\n".join(data["errors"][:5])
    await cb.message.edit_text(body, reply_markup=back())


# ------------------------------- prices ---------------------------------- #
@router.callback_query(F.data == "price")
async def ask_price(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.price)
    await cb.message.edit_text("Send a country name, ISO code or calling code.", reply_markup=back())
    await cb.answer()


@router.message(Flow.price)
async def show_prices(message: Message, state: FSMContext):
    await state.clear()
    country = (message.text or "").strip()
    code, rows = await api("GET", "/prices", params={"country": country, "limit": 3})
    if code != 200:
        await message.answer(f"⚠️ {rows.get('detail')}", reply_markup=home_kb())
        return
    if not rows:
        await message.answer("❌ No data.", reply_markup=home_kb())
        return
    lines = [f"💰 <b>{country.upper()}</b> — top 3", ""]
    for medal, row in zip(("🥇", "🥈", "🥉"), rows):
        lines.append(f"{medal} {row['source']} — {row['currency']} {row['price']:,.2f}")
    lines.append(f"\n🕒 {rows[0]['updated_at'][11:16]} UTC")
    await message.answer("\n".join(lines), reply_markup=home_kb())


# ------------------------------ settings --------------------------------- #
async def settings_view():
    _, doc = await api("GET", "/settings")
    times = doc.get("check_times") or []
    text = (
        "⚙️ <b>SETTINGS</b>\n\n"
        f"⏰ Check times: <b>{', '.join(times) or 'none'}</b>\n"
        f"💱 Currency: <b>{doc.get('currency')}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Set check times", callback_data="set_times")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="home")],
    ])
    return text, kb


@router.callback_query(F.data == "settings")
async def settings_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await settings_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "set_times")
async def ask_times(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.times)
    await cb.message.edit_text("Send one or two times: <code>10:00, 22:00</code>", reply_markup=back("settings"))
    await cb.answer()


@router.message(Flow.times)
async def save_times(message: Message, state: FSMContext):
    values = [v.strip() for v in (message.text or "").split(",") if v.strip()]
    code, data = await api("PATCH", "/settings", json={"check_times": values})
    await state.clear()
    await message.answer("✅ saved" if code == 200 else f"❌ {data.get('detail')}", reply_markup=back("settings"))


@router.errors()
async def on_error(event: ErrorEvent):
    log.exception("handler error: %s", event.exception, exc_info=event.exception)


async def main() -> None:
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    log.info("admin bot polling as admin_ids=%s", settings.admin_ids)
    await dispatcher.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())