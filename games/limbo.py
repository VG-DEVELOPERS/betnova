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
    check_and_apply_level_up,
)
from utils import fmt_money, bal_emoji, back_kb, guard_owner


def generate_limbo_result() -> float:
    # House edge: low targets (1.1x) lose more often
    r = random.random()
    if r < 0.35:                          # 35% hard bust under 1.1x
        return round(random.uniform(1.00, 1.09), 2)
    if r < 0.75:                          # mid range
        return round(random.uniform(1.10, 2.50), 2)
    if r < 0.95:
        return round(random.uniform(2.50, 10.00), 2)
    if r < 0.995:
        return round(random.uniform(10.00, 50.00), 2)
    if r < 0.9995:
        return round(random.uniform(50.00, 200.00), 2)
    return round(random.uniform(200.00, 900.00), 2)


def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu_limbo(:\d+)?$"))
    async def cb_limbo_help(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>Play ⬆️ Limbo</b>\n\n"
            f"Chat mein turant khelo:\n"
            f"<code>/limbo &lt;bet&gt; &lt;multiplier&gt;</code>\n\n"
            f"Examples:\n"
            f"<code>/limbo 0.05 1.5x</code>\n"
            f"<code>/limbo 10 2x</code>\n"
            f"<code>/limbo 100 10x</code>\n\n"
            f"ℹ️ Multiplier range: <code>{LIMBO_MIN}x – {LIMBO_MAX}x</code>"
        )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
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
            await message.reply("Invalid amount.")
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
            await message.reply(f"Multiplier {LIMBO_MIN}x – {LIMBO_MAX}x ke beech hona chahiye.")
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

        level_up = await check_and_apply_level_up(user["_id"])

        emoji = bal_emoji(mode)
        status = "✅ <b>WIN</b>" if win else "❌ <b>LOSS</b>"
        # Show only bet amount + profit, not full balance
        if win:
            money_line = f"{emoji} Bet: <code>{fmt_money(bet)}</code>  →  <code>+{fmt_money(profit)}</code>"
        else:
            money_line = f"{emoji} Bet: <code>{fmt_money(bet)}</code>  →  <code>{fmt_money(profit)}</code>"
        text = (
            f"<b>⬆️ Limbo</b>\n\n"
            f"{money_line}\n"
            f"🎯 Target: <code>{target:.2f}×</code>\n"
            f"💥 Result: <code>{result:.2f}×</code>\n\n"
            f"{status}"
        )
        await message.reply(text, parse_mode=ParseMode.HTML)

        if level_up and level_up["total_bonus"] > 0:
            lines = [
                f"🎉 <b>Level Up!</b>",
                "",
                f"{level_up['title']}",
            ]
            for u in level_up["unlocked"]:
                lines.append(f"+{fmt_money(u['bonus'])}  →  {u['title']}")
            lines.append(f"\nBonus  <code>{fmt_money(level_up['total_bonus'])}</code>")
            await message.reply("\n".join(lines), parse_mode=ParseMode.HTML)
