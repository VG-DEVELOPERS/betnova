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
from utils import (
    fmt_money,
    bal_emoji,
    balance_kb,
    back_kb,
    main_menu_kb,
    lb_kb,
    rakeback_kb,
    guard_owner,
    parse_cb,
    sep,
)


async def render_main(user: dict) -> str:
    bal = await get_balance(user)
    mode = user.get("mode", "real")
    coins = float(user.get("virtual_coins", 0))
    active = "active" if mode == "real" else ""
    return (
        f"<b>🎰 BetNova</b>\n\n"
        f"💰 Balance: <code>{fmt_money(bal)}</code>"
        + (f"  ← <i>active</i>" if mode == "real" else "")
        + f"\n"
        f"🪙 Coins: <code>{coins:,.0f}</code>"
        + (f"  ← <i>active</i>" if mode == "virtual" else "")
    )


async def render_balance(user: dict) -> str:
    mode = user.get("mode", "real")
    bal = await get_balance(user)
    coins = float(user.get("virtual_coins", 0))
    if mode == "real":
        return (
            f"💰 Current balance: <code>{fmt_money(bal)}</code>  ← <i>active</i>\n"
            f"🪙 Coins: <code>{coins:,.0f}</code>"
        )
    return (
        f"💰 Balance: <code>{fmt_money(float(user.get('real_balance', 0)))}</code>\n"
        f"🪙 Coins: <code>{coins:,.0f}</code>  ← <i>active</i>"
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
        await message.reply(
            text,
            reply_markup=main_menu_kb(message.from_user.id),
            parse_mode=ParseMode.HTML,
        )

    @app.on_callback_query(filters.regex(r"^menu_main(:\d+)?$"))
    async def cb_main(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        text = await render_main(user)
        await cq.message.edit_text(
            text,
            reply_markup=main_menu_kb(cq.from_user.id),
            parse_mode=ParseMode.HTML,
        )
        await cq.answer()

    @app.on_message(filters.command("balance"))
    async def cmd_balance(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        text = await render_balance(user)
        await message.reply(
            text,
            reply_markup=balance_kb(user.get("mode", "real"), message.from_user.id),
            parse_mode=ParseMode.HTML,
        )

    @app.on_callback_query(filters.regex(r"^menu_balance(:\d+)?$"))
    async def cb_balance(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        text = await render_balance(user)
        await cq.message.edit_text(
            text,
            reply_markup=balance_kb(user.get("mode", "real"), cq.from_user.id),
            parse_mode=ParseMode.HTML,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^mode_(real|virtual)(:\d+)?$"))
    async def cb_mode(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        action, _ = parse_cb(cq.data)
        mode = action.split("_")[1]  # real / virtual
        await set_mode(cq.from_user.id, mode)
        user = await get_user(cq.from_user.id)
        text = await render_balance(user)
        await cq.message.edit_text(
            text,
            reply_markup=balance_kb(mode, cq.from_user.id),
            parse_mode=ParseMode.HTML,
        )
        await cq.answer(f"✅ {mode.title()} mode")

    @app.on_callback_query(filters.regex(r"^menu_deposit(:\d+)?$"))
    async def cb_deposit(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>💳 Deposit</b>\n\n"
            f"Send USDT tip to:\n"
            f"<code>@{DEPOSIT_USERNAME}</code>\n\n"
            f"Cwallet confirm → <b>real_balance</b> update."
        )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_withdraw(:\d+)?$"))
    async def cb_withdraw(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>💸 Withdraw</b>\n\n"
            f"Withdrawals are disabled.\n"
            f"No real-money payouts."
        )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_rank(:\d+)?$"))
    async def cb_rank(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        from database import get_rank_tier, RANK_TIERS

        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        wagered = float(user.get("wagered", 0))
        min_w, level, title, _ = get_rank_tier(wagered)

        next_title = "MAX"
        need = 0.0
        for tmin, tlevel, ttitle, _b in RANK_TIERS:
            if tlevel > level:
                next_title = ttitle
                need = max(0.0, tmin - wagered)
                break

        text = (
            f"<b>👑 Rank</b>\n\n"
            f"{title}\n"
            f"Wagered: <code>{fmt_money(wagered)}</code>\n"
        )
        if next_title != "MAX":
            text += f"\nNext: {next_title}\nNeed: <code>{fmt_money(need)}</code>"
        else:
            text += "\n🌟 Max rank reached!"

        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_rakeback(:\d+)?$"))
    async def cb_rakeback_menu(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        user = await ensure_user(
            cq.from_user.id,
            name=cq.from_user.first_name or "",
            username=cq.from_user.username,
        )
        rb = float(user.get("rakeback", 0))
        text = (
            f"<b>🔄 Rakeback</b>\n\n"
            f"Available: <code>{fmt_money(rb)}</code>\n"
            f"Rate: <code>{RAKEBACK_RATE * 100:.0f}%</code>\n\n"
            f"Claim → current mode balance"
        )
        await cq.message.edit_text(
            text, reply_markup=rakeback_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^claim_rakeback(:\d+)?$"))
    async def cb_claim_rakeback(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        user = await get_user(cq.from_user.id)
        if not user:
            await cq.answer("User not found", show_alert=True)
            return
        mode = user.get("mode", "real")
        claimed = await claim_rakeback(cq.from_user.id, mode)
        if claimed and claimed > 0:
            await cq.answer(f"✅ +{fmt_money(claimed)}", show_alert=True)
            text = (
                f"<b>🔄 Rakeback</b>\n\n"
                f"✅ Claimed: <code>{fmt_money(claimed)}</code>\n"
                f"Available: <code>$0.0000</code>"
            )
        else:
            await cq.answer("Nothing to claim", show_alert=True)
            text = (
                f"<b>🔄 Rakeback</b>\n\n"
                f"Available: <code>$0.0000</code>\n"
                f"Rate: <code>{RAKEBACK_RATE * 100:.0f}%</code>"
            )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )

    @app.on_message(filters.command("rakeback"))
    async def cmd_rakeback(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        mode = user.get("mode", "real")
        claimed = await claim_rakeback(message.from_user.id, mode)
        if claimed and claimed > 0:
            await message.reply(f"✅ Rakeback claimed: <code>{fmt_money(claimed)}</code>", parse_mode=ParseMode.HTML)
        else:
            await message.reply("Nothing to claim.")

    @app.on_callback_query(filters.regex(r"^menu_lb(:\d+)?$"))
    async def cb_lb_menu(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>🏆 Leaderboard</b>\n\n"
            f"Choose mode:"
        )
        await cq.message.edit_text(
            text, reply_markup=lb_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^lb_(real|virtual)(:\d+)?$"))
    async def cb_lb(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        action, _ = parse_cb(cq.data)
        mode = action.split("_")[1]
        board = await get_leaderboard(mode, limit=10)
        emoji = "💵" if mode == "real" else "🪙"
        title = "Real" if mode == "real" else "Virtual"
        lines = [
            f"<b>🏆 {title} Leaderboard</b>",
            "",
        ]
        medals = ["🥇", "🥈", "🥉"]
        for i, u in enumerate(board):
            name = u.get("username") or u.get("name") or str(u["_id"])
            bal = float(u.get("real_balance" if mode == "real" else "virtual_coins", 0))
            medal = medals[i] if i < 3 else f"<code>{i+1}.</code>"
            lines.append(f"{medal}  <b>{name}</b>\n{emoji}  <code>{fmt_money(bal)}</code>")
        if not board:
            lines.append("No players yet.")
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data=f"menu_lb:{cq.from_user.id}")]]
        )
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_history(:\d+)?$"))
    async def cb_history(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        items = await get_recent_history(cq.from_user.id, limit=8)
        lines = [
            f"<b>📜 History</b>",
            "",
        ]
        if not items:
            lines.append("No activity yet.")
        for kind, doc in items:
            if kind == "deposit":
                status = doc.get("status", "")
                icon = "🟢" if status == "confirmed" else "🔴"
                lines.append(f"💳  +{fmt_money(doc['amount'])}  {icon}")
            elif kind == "game":
                profit = float(doc.get("profit", 0))
                sign = "+" if profit >= 0 else ""
                result = "✅" if doc.get("win") else "❌"
                lines.append(f"🎯  {doc.get('game', 'game').title()}  {sign}{fmt_money(profit)}  {result}")
            elif kind == "tip":
                direction = "→" if doc.get("from_id") == cq.from_user.id else "←"
                lines.append(f"🎁  Tip {direction} {fmt_money(doc['amount'])}")
        text = "\n".join(lines)
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()
