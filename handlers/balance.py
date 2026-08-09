# ============================================================
# Balance / Mode / Deposit / Withdraw / Rank / Rakeback / History / LB
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import DEPOSIT_USERNAME, RAKEBACK_RATE
from database import (
    ensure_user,
    get_user,
    set_mode,
    get_balance,
    claim_rakeback,
    get_leaderboard,
    get_rank_info,
    get_recent_history,
)
from utils import fmt_money, bal_emoji, balance_kb, back_kb, main_menu_kb


async def render_main(user: dict) -> str:
    bal = await get_balance(user)
    mode = user.get("mode", "real")
    coins = float(user.get("virtual_coins", 0))
    active = "💵 Real" if mode == "real" else "🪙 Virtual"
    return (
        "╭──────────────────╮\n"
        "│  🎰 <b>BETNOVA</b>  │\n"
        "╰──────────────────╯\n"
        f"👛 Balance\n"
        f"{bal_emoji(mode)} {fmt_money(bal)}\n"
        f"⬆️ Active  {active}\n"
        f"🪙 Coins\n"
        f"{coins:,.0f}"
    )


async def render_balance(user: dict) -> str:
    mode = user.get("mode", "real")
    bal = await get_balance(user)
    return (
        f"👛 <b>Balance</b>\n"
        f"{bal_emoji(mode)} {fmt_money(bal)}\n"
        f"⬆️ Active"
    )


def register(app: Client):

    @app.on_message(filters.command("start"))
    async def cmd_start(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        text = await render_main(user)
        await message.reply(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    @app.on_callback_query(filters.regex("^menu_main$"))
    async def cb_main(_, cq: CallbackQuery):
        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        text = await render_main(user)
        await cq.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_message(filters.command("balance"))
    async def cmd_balance(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        text = await render_balance(user)
        await message.reply(text, reply_markup=balance_kb(user.get("mode", "real")), parse_mode=ParseMode.HTML)

    @app.on_callback_query(filters.regex("^menu_balance$"))
    async def cb_balance(_, cq: CallbackQuery):
        user = await ensure_user(cq.from_user.id, name=cq.from_user.first_name or "", username=cq.from_user.username)
        text = await render_balance(user)
        await cq.message.edit_text(text, reply_markup=balance_kb(user.get("mode", "real")), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^mode_(real|virtual)$"))
    async def cb_mode(_, cq: CallbackQuery):
        mode = cq.data.split("_")[1]
        await set_mode(cq.from_user.id, mode)
        user = await get_user(cq.from_user.id)
        text = await render_balance(user)
        await cq.message.edit_text(text, reply_markup=balance_kb(mode), parse_mode=ParseMode.HTML)
        await cq.answer(f"Switched to {mode.title()}")

    @app.on_callback_query(filters.regex("^menu_deposit$"))
    async def cb_deposit(_, cq: CallbackQuery):
        text = (
            "💳 <b>Deposit</b>\n"
            f"Send deposit to:\n"
            f"<code>@{DEPOSIT_USERNAME}</code>\n\n"
            "Cwallet confirmation will be monitored.\n"
            "After confirmation → <b>real_balance</b> increases."
        )
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^menu_withdraw$"))
    async def cb_withdraw(_, cq: CallbackQuery):
        text = (
            "💸 <b>Withdraw</b>\n"
            "Withdrawals are currently disabled.\n"
            "This bot does not process real-money payouts."
        )
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^menu_rank$"))
    async def cb_rank(_, cq: CallbackQuery):
        user = await ensure_user(cq.from_user.id, name=cq.from_user.first_name or "", username=cq.from_user.username)
        wagered = float(user.get("wagered", 0))
        rank = await get_rank_info(wagered)
        text = f"👑 <b>Rank</b>\n{rank}\nWagered: {fmt_money(wagered)}"
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^menu_rakeback$"))
    async def cb_rakeback_menu(_, cq: CallbackQuery):
        user = await ensure_user(cq.from_user.id, name=cq.from_user.first_name or "", username=cq.from_user.username)
        rb = float(user.get("rakeback", 0))
        text = (
            f"🔄 <b>Rakeback</b>\n"
            f"Available: {fmt_money(rb)}\n"
            f"Rate: {RAKEBACK_RATE * 100:.0f}%\n\n"
            "Use /rakeback to claim into current mode."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Claim", callback_data="claim_rakeback")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^claim_rakeback$"))
    async def cb_claim_rakeback(_, cq: CallbackQuery):
        user = await get_user(cq.from_user.id)
        if not user:
            await cq.answer("User not found", show_alert=True)
            return
        mode = user.get("mode", "real")
        claimed = await claim_rakeback(cq.from_user.id, mode)
        if claimed and claimed > 0:
            await cq.answer(f"Claimed {fmt_money(claimed)}", show_alert=True)
            text = f"🔄 <b>Rakeback</b>\n✅ Claimed {fmt_money(claimed)}\nAvailable: $0.0000"
        else:
            await cq.answer("Nothing to claim", show_alert=True)
            text = f"🔄 <b>Rakeback</b>\nAvailable: $0.0000\nRate: {RAKEBACK_RATE * 100:.0f}%"
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)

    @app.on_message(filters.command("rakeback"))
    async def cmd_rakeback(_, message: Message):
        user = await ensure_user(message.from_user.id, name=message.from_user.first_name or "", username=message.from_user.username)
        mode = user.get("mode", "real")
        claimed = await claim_rakeback(message.from_user.id, mode)
        if claimed and claimed > 0:
            await message.reply(f"✅ Rakeback claimed: {fmt_money(claimed)}")
        else:
            await message.reply("Nothing to claim.")

    @app.on_callback_query(filters.regex("^menu_lb$"))
    async def cb_lb_menu(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🏆 Real", callback_data="lb_real"),
                    InlineKeyboardButton("🪙 Virtual", callback_data="lb_virtual"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
            ]
        )
        await cq.message.edit_text("🏆 <b>Leaderboard</b>\nChoose mode:", reply_markup=kb, parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^lb_(real|virtual)$"))
    async def cb_lb(_, cq: CallbackQuery):
        mode = cq.data.split("_")[1]
        board = await get_leaderboard(mode, limit=10)
        emoji = "💵" if mode == "real" else "🪙"
        title = "🏆 Real Leaderboard" if mode == "real" else "🪙 Virtual Leaderboard"
        lines = [title, ""]
        medals = ["🥇", "🥈", "🥉"]
        for i, u in enumerate(board):
            name = u.get("username") or u.get("name") or str(u["_id"])
            bal = float(u.get("real_balance" if mode == "real" else "virtual_coins", 0))
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} {name}\n{emoji} {fmt_money(bal)}")
        if not board:
            lines.append("No players yet.")
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_lb")]])
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex("^menu_history$"))
    async def cb_history(_, cq: CallbackQuery):
        items = await get_recent_history(cq.from_user.id, limit=8)
        lines = ["📜 <b>History</b>", ""]
        if not items:
            lines.append("No activity yet.")
        for kind, doc in items:
            if kind == "deposit":
                status = doc.get("status", "")
                icon = "🟢" if status == "confirmed" else "🔴"
                lines.append(f"💳 +{fmt_money(doc['amount'])}\n{icon} {status.title()}")
            elif kind == "game":
                profit = float(doc.get("profit", 0))
                sign = "+" if profit >= 0 else ""
                result = "✅ Win" if doc.get("win") else "❌ Loss"
                lines.append(f"🎯 {doc.get('game', 'game').title()}\n{sign}{fmt_money(profit)}\n{result}")
            elif kind == "tip":
                direction = "→" if doc.get("from_id") == cq.from_user.id else "←"
                lines.append(f"🎁 Tip {direction} {fmt_money(doc['amount'])}")
        text = "\n".join(lines)
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()
