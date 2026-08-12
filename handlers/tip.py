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
from utils import fmt_money, back_kb, guard_owner


def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu_tip(:\d+)?$"))
    async def cb_tip_help(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>🎁 Tip</b>\n\n"
            f"Reply to user:\n"
            f"<code>/tip 10</code>\n\n"
            f"Or by username:\n"
            f"<code>/tip @user 10</code>\n\n"
            f"Uses your current mode balance."
        )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
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
                    "Usage: <code>/tip @username amount</code>",
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
                await message.reply("User not found. Unhe pehle /start karna hoga.")
                return

        if amount is None or amount <= 0:
            await message.reply("Amount must be positive.")
            return
        if target_user["_id"] == user["_id"]:
            await message.reply("Khud ko tip nahi de sakte.")
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
        await message.reply(
            f"🎁 Tipped <code>{fmt_money(amount)}</code> → <b>{to_name}</b>",
            parse_mode=ParseMode.HTML,
        )
