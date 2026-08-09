# ============================================================
# Tip System
# ============================================================

from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from database import (
    ensure_user,
    get_user_by_username,
    atomic_bet,
    save_tip,
    users,
)
from utils import fmt_money, back_kb


def register(app: Client):

    @app.on_callback_query(filters.regex("^menu_tip$"))
    async def cb_tip_help(_, cq: CallbackQuery):
        text = (
            "🎁 <b>Tip</b>\n"
            "Reply to a user:\n"
            "<code>/tip 10</code>\n\n"
            "Or:\n"
            "<code>/tip @username 10</code>\n\n"
            "Uses your current mode balance."
        )
        await cq.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_message(filters.command("tip"))
    async def cmd_tip(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        mode = user.get("mode", "real")
        args = message.command[1:] if message.command else []

        target_user = None
        amount = None

        if message.reply_to_message and message.reply_to_message.from_user:
            if len(args) != 1:
                await message.reply("Usage: reply with <code>/tip amount</code>", parse_mode=ParseMode.HTML)
                return
            try:
                amount = float(args[0])
            except ValueError:
                await message.reply("Invalid amount.")
                return
            target_user = await ensure_user(
                message.reply_to_message.from_user.id,
                name=message.reply_to_message.from_user.first_name or "",
                username=message.reply_to_message.from_user.username,
            )
        else:
            if len(args) != 2:
                await message.reply(
                    "Usage: <code>/tip @username amount</code> or reply with <code>/tip amount</code>",
                    parse_mode=ParseMode.HTML,
                )
                return
            uname = args[0].lstrip("@").lower()
            try:
                amount = float(args[1])
            except ValueError:
                await message.reply("Invalid amount.")
                return
            target_user = await get_user_by_username(uname)
            if not target_user:
                await message.reply("User not found. They must start the bot first.")
                return

        if amount is None or amount <= 0:
            await message.reply("Amount must be positive.")
            return
        if target_user["_id"] == user["_id"]:
            await message.reply("You cannot tip yourself.")
            return

        updated = await atomic_bet(user["_id"], amount, mode)
        if not updated:
            await message.reply("Insufficient balance.")
            return

        field = "real_balance" if mode == "real" else "virtual_coins"
        await users.update_one({"_id": target_user["_id"]}, {"$inc": {field: amount}})

        await save_tip({
            "from_id": user["_id"],
            "to_id": target_user["_id"],
            "amount": amount,
            "mode": mode,
            "created_at": datetime.utcnow(),
        })

        to_name = target_user.get("username") or target_user.get("name") or str(target_user["_id"])
        await message.reply(f"🎁 Tipped {fmt_money(amount)} to {to_name}")
