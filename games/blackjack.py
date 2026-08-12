# ============================================================
# Blackjack Game
# ============================================================

import random
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from config import RAKEBACK_RATE
from database import (
    ensure_user,
    get_user,
    get_balance,
    atomic_bet,
    atomic_credit_win,
    save_game,
    save_bj_state,
    get_bj_state,
    delete_bj_state,
    users,
    check_and_apply_level_up,
)
from utils import fmt_money, bal_emoji, back_kb, bj_kb, guard_owner, parse_cb

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def card_value(card):
    r = card[0]
    if r in ("J", "Q", "K"):
        return 10
    if r == "A":
        return 11
    return int(r)


def hand_total(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def hand_str(hand, hide_second=False):
    if hide_second and len(hand) >= 2:
        return f"{hand[0][0]}{hand[0][1]}  🃏"
    return "  ".join(f"{c[0]}{c[1]}" for c in hand)


def render_bj(state: dict, hide_dealer: bool = True) -> str:
    mode = state["mode"]
    emoji = bal_emoji(mode)
    p_hand = state["player"]
    d_hand = state["dealer"]
    p_total = hand_total(p_hand)
    showing = card_value(d_hand[0]) if hide_dealer else hand_total(d_hand)

    return (
        f"<b>🃏 Blackjack</b>\n\n"
        f"{emoji} Bet: <code>{fmt_money(state['bet'])}</code>\n\n"
        f"👤 You:\n"
        f"{hand_str(p_hand)}\n"
        f"Total: <code>{p_total}</code>\n\n"
        f"🎰 Dealer:\n"
        f"{hand_str(d_hand, hide_second=hide_dealer)}\n"
        f"{'Showing' if hide_dealer else 'Total'}: <code>{showing if hide_dealer else hand_total(d_hand)}</code>"
    )


async def finish_blackjack(message_or_cq, user_id: int, state: dict, natural: bool = False):
    mode = state["mode"]
    bet = float(state["bet"])
    player = state["player"]
    dealer = state["dealer"]
    deck = state["deck"]

    while hand_total(dealer) < 17:
        dealer.append(deck.pop())

    p_total = hand_total(player)
    d_total = hand_total(dealer)

    if p_total > 21:
        win, push, payout_mult, result_txt = False, False, 0.0, "💥 Bust"
    elif natural and p_total == 21 and len(player) == 2:
        if d_total == 21 and len(dealer) == 2:
            win, push, payout_mult, result_txt = False, True, 1.0, "🤝 Push (both BJ)"
        else:
            win, push, payout_mult, result_txt = True, False, 2.5, "🃏 Blackjack!"
    elif d_total > 21:
        win, push, payout_mult, result_txt = True, False, 2.0, "🎰 Dealer Bust"
    elif p_total > d_total:
        win, push, payout_mult, result_txt = True, False, 2.0, "✅ Win"
    elif p_total == d_total:
        win, push, payout_mult, result_txt = False, True, 1.0, "🤝 Push"
    else:
        win, push, payout_mult, result_txt = False, False, 0.0, "❌ Loss"

    total_return = bet * payout_mult
    profit = total_return - bet

    if total_return > 0:
        await atomic_credit_win(user_id, total_return, profit if win else 0.0, mode)

    await save_game({
        "user_id": user_id,
        "mode": mode,
        "game": "blackjack",
        "bet": bet,
        "player_total": p_total,
        "dealer_total": d_total,
        "win": win,
        "push": push,
        "total_return": total_return,
        "profit": profit,
        "created_at": datetime.utcnow(),
    })
    await delete_bj_state(user_id)

    level_up = await check_and_apply_level_up(user_id)

    user = await get_user(user_id)
    new_bal = await get_balance(user)
    emoji = bal_emoji(mode)

    text = (
        f"<b>🃏 Blackjack</b>\n\n"
        f"{emoji} Bet: <code>{fmt_money(bet)}</code>\n\n"
        f"👤 You: {hand_str(player)} (<code>{p_total}</code>)\n"
        f"🎰 Dealer: {hand_str(dealer)} (<code>{d_total}</code>)\n\n"
        f"<b>{result_txt}</b>\n"
        f"{emoji} Balance: <code>{fmt_money(new_bal)}</code>"
    )

    level_msg = None
    if level_up and level_up["total_bonus"] > 0:
        lines = [
            f"🎉 <b>Level Up!</b>",
            "",
            f"{level_up['title']}",
        ]
        for u in level_up["unlocked"]:
            lines.append(f"+{fmt_money(u['bonus'])}  →  {u['title']}")
        lines.append(f"\nBonus  <code>{fmt_money(level_up['total_bonus'])}</code>")
        level_msg = "\n".join(lines)

    if isinstance(message_or_cq, Message):
        await message_or_cq.reply(text, parse_mode=ParseMode.HTML)
        if level_msg:
            await message_or_cq.reply(level_msg, parse_mode=ParseMode.HTML)
    else:
        await message_or_cq.message.edit_text(text, parse_mode=ParseMode.HTML)
        await message_or_cq.answer()
        if level_msg:
            await message_or_cq.message.reply(level_msg, parse_mode=ParseMode.HTML)


def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu_bj(:\d+)?$"))
    async def cb_bj_help(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return
        text = (
            f"<b>Play 🃏 Blackjack</b>\n\n"
            f"Chat mein turant khelo:\n"
            f"<code>/blackjack &lt;bet&gt;</code>\n\n"
            f"Example:\n"
            f"<code>/blackjack 10</code>"
        )
        await cq.message.edit_text(
            text, reply_markup=back_kb(cq.from_user.id), parse_mode=ParseMode.HTML
        )
        await cq.answer()

    @app.on_message(filters.command("blackjack"))
    async def cmd_blackjack(_, message: Message):
        user = await ensure_user(
            message.from_user.id,
            name=message.from_user.first_name or "",
            username=message.from_user.username,
        )
        mode = user.get("mode", "real")

        existing = await get_bj_state(user["_id"])
        if existing:
            await message.reply("Pehle active game finish/cancel karo.")
            return

        args = message.command[1:] if message.command else []
        if len(args) != 1:
            await message.reply("Usage: <code>/blackjack amount</code>", parse_mode=ParseMode.HTML)
            return
        try:
            bet = float(args[0])
        except ValueError:
            await message.reply("Invalid amount.")
            return
        if bet <= 0:
            await message.reply("Amount must be positive.")
            return

        updated = await atomic_bet(user["_id"], bet, mode, game_name="blackjack")
        if not updated:
            await message.reply("Insufficient balance.")
            return

        deck = new_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        state = {
            "user_id": user["_id"],
            "mode": mode,
            "bet": bet,
            "deck": deck,
            "player": player,
            "dealer": dealer,
            "status": "playing",
            "doubled": False,
        }
        await save_bj_state(user["_id"], state)

        p_total = hand_total(player)
        d_total = hand_total(dealer)
        if p_total == 21 or d_total == 21:
            await finish_blackjack(message, user["_id"], state, natural=True)
            return

        text = render_bj(state, hide_dealer=True)
        await message.reply(
            text,
            reply_markup=bj_kb(user["_id"], can_double=True),
            parse_mode=ParseMode.HTML,
        )

    @app.on_callback_query(filters.regex(r"^bj_(hit|stand|double|cancel)(:\d+)?$"))
    async def cb_bj_action(_, cq: CallbackQuery):
        if not await guard_owner(cq):
            return

        user_id = cq.from_user.id
        state = await get_bj_state(user_id)
        if not state or state.get("status") != "playing":
            await cq.answer("No active game.", show_alert=True)
            return

        # Extra safety: state owner must match
        if state.get("user_id") != user_id:
            await cq.answer("❌ Ye tumhara game nahi hai!", show_alert=True)
            return

        action, _ = parse_cb(cq.data)
        action = action.replace("bj_", "")  # hit / stand / double / cancel

        mode = state["mode"]
        bet = float(state["bet"])
        deck = state["deck"]
        player = state["player"]

        if action == "cancel":
            field = "real_balance" if mode == "real" else "virtual_coins"
            await users.update_one(
                {"_id": user_id},
                {"$inc": {
                    field: bet,
                    "wagered": -bet,
                    "games": -1,
                    "rakeback": -bet * RAKEBACK_RATE,
                    "game_counts.blackjack": -1,
                }},
            )
            await delete_bj_state(user_id)
            await cq.message.edit_text("❌ Game cancelled. Bet refunded.")
            await cq.answer()
            return

        if action == "double":
            if len(player) != 2 or state.get("doubled"):
                await cq.answer("Ab double nahi kar sakte.", show_alert=True)
                return
            updated = await atomic_bet(user_id, bet, mode)
            if not updated:
                await cq.answer("Balance kam hai double ke liye.", show_alert=True)
                return
            state["bet"] = bet * 2
            state["doubled"] = True
            player.append(deck.pop())
            state["player"] = player
            state["deck"] = deck
            await save_bj_state(user_id, state)
            await finish_blackjack(cq, user_id, state)
            return

        if action == "hit":
            player.append(deck.pop())
            state["player"] = player
            state["deck"] = deck
            if hand_total(player) > 21:
                await save_bj_state(user_id, state)
                await finish_blackjack(cq, user_id, state)
                return
            await save_bj_state(user_id, state)
            text = render_bj(state, hide_dealer=True)
            can_double = len(player) == 2 and not state.get("doubled")
            await cq.message.edit_text(
                text,
                reply_markup=bj_kb(user_id, can_double=can_double),
                parse_mode=ParseMode.HTML,
            )
            await cq.answer()
            return

        if action == "stand":
            await finish_blackjack(cq, user_id, state)
            return
