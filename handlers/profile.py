# ============================================================
# Profile / Stats
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from database import ensure_user, get_rank_info, get_favorite_game
from utils import fmt_money, back_kb, guard_owner


def format_date(dt) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y")


async def build_profile_text(user: dict) -> str:
    uid = user["_id"]
    name = user.get("name") or user.get("username") or "User"
    username = user.get("username")
    display = f"{name}" + (f" (@{username})" if username else "")
    rank = await get_rank_info(float(user.get("wagered", 0)))
    real_bal = float(user.get("real_balance", 0))
    coins = float(user.get("virtual_coins", 0))
    total_games = int(user.get("games", 0))
    total_bets = float(user.get("wagered", 0))
    total_wins = float(user.get("won", 0))
    biggest = float(user.get("biggest_win", 0))
    favorite = get_favorite_game(user)
    reg = format_date(user.get("created_at"))

    return (
        f"<b>👤 Profile</b>\n\n"
        f"ℹ️ User: <b>{display}</b> (<code>{uid}</code>)\n"
        f"📊 Rank: {rank}\n"
        f"💰 Balance: <code>{fmt_money(real_bal)}</code>\n"
        f"🪙 Coins: <code>{coins:,.0f}</code>\n\n"
        f"⚡️ Total games: <code>{total_games}</code>\n"
        f"Total bets: <code>{fmt_money(total_bets)}</code>\n"
        f"Total wins: <code>{fmt_money(total_wins)}</code>\n\n"
        f"🎲 Favorite game: {favorite}\n"
        f"🎉 Biggest win: <code>{fmt_money(biggest)}</code>\n\n"
        f"🕒 Registration date: <code>{reg}</code>"
    )


def register(app: Client):

    @app.on_message(filters.command(["profile", "stats"]))
    async def cmd_profile(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        text = await build_profile_text(user)
        await message.reply(
            text,
            reply_markup=back_kb(message.from_user.id),
            parse_mode=ParseMode.HTML,
        )

    @app.on_callback_query(filters.regex(r"^menu_profile(:\d+)?$"))
    async def cb_profile(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        text = await build_profile_text(user)
        await cq.message.edit_text(
            text,
            reply_markup=back_kb(cq.from_user.id),
            parse_mode=ParseMode.HTML,
        )
        await cq.answer()
