# ============================================================
# Limbo Game
# ============================================================

import random
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from config import LIMBO_MIN, LIMBO_MAX
from database import (
    ensure_user,
    get_user,
    get_balance,
    atomic_bet,
    atomic_credit_win,
    save_game,
)
from utils import fmt_money, bal_emoji, back_kb


def generate_limbo_result() -> float:
    r = random.random()
    if r < 0.70:
        return round(random.uniform(1.00, 2.00), 2)
    if r < 0.95:
        return round(random.uniform(2.00, 10.00), 2)
    if r < 0.995:
        return round(random.uniform(10.00, 50.00), 2)
    if r < 0.9999:
        return round(random.uniform(50.00, 199.99), 2)
    return round(random.uniform(200.00, 900.00), 2)


def register(app: Client):

    @app.on_callback_query(filters.regex("^menu_limbo$"))
    async def cb_limbo_help(_, cq: CallbackQuery):
        text = (
            "🎯 <b>Limbo</b>\n"
            "Usage:\n"
            "<code>/limbo amount multiplier</code>\n\n"
            "Examples:\n"
            "<code>/limbo 0.05 1.5x</code>\n"
            "<code>/limbo 10 2x</code>\n"
            "<code>/limbo 100 10x</code>\n\n"
            f"Multiplier range: {LIMBO_MIN}x – {LIMBO_MAX}x"
        )
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_message(filters.command("limbo"))
    async def cmd_limbo(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        mode = user.get("mode", "real")
        args = message.command[1:] if message.command else []

        if len(args) != 2:
            await message.reply(
                "Usage: <code>/limbo amount multiplier</code>\n"
                "Example: <code>/limbo 0.05 1.5x</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            bet = float(args[0])
        except ValueError:
            await message.reply("Invalid amount. Use a number only.")
            return
        if bet <= 0:
            await message.reply("Amount must be positive.")
            return

        mult_raw = args[1].lower().replace(",", ".").replace("x", "").strip()
        try:
            target = float(mult_raw)
        except ValueError:
            await message.reply("Invalid multiplier.")
            return
        if target < LIMBO_MIN or target > LIMBO_MAX:
            await message.reply(f"Multiplier must be between {LIMBO_MIN}x and {LIMBO_MAX}x.")
            return

        updated = await atomic_bet(user["_id"], bet, mode, game_name="limbo")
        if not updated:
            await message.reply("Insufficient balance.")
            return

        result = generate_limbo_result()
        win = result >= target

        if win:
            total_return = bet * target
            profit = total_return - bet
            await atomic_credit_win(user["_id"], total_return, profit, mode)
        else:
            total_return = 0.0
            profit = -bet

        await save_game({
            "user_id": user["_id"],
            "mode": mode,
            "game": "limbo",
            "bet": bet,
            "target": target,
            "result": result,
            "win": win,
            "total_return": total_return,
            "profit": profit,
            "created_at": datetime.utcnow(),
        })

        user = await get_user(user["_id"])
        new_bal = await get_balance(user)
        old_bal = new_bal - profit

        emoji = bal_emoji(mode)
        status = "✅ WIN" if win else "❌ LOSS"
        text = (
            f"🎯 <b>Limbo</b>\n"
            f"{emoji} {fmt_money(old_bal)} → {fmt_money(new_bal)}\n"
            f"🎯 {target:.2f}×\n"
            f"💥 {result:.2f}×\n"
            f"{status}"
        )
        await message.reply(text, parse_mode=ParseMode.HTML)
