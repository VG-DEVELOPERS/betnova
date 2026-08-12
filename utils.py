# ============================================================
# Shared helpers, UI & button ownership
# ============================================================

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


# ---------- Money / mode ----------

def fmt_money(v: float) -> str:
    return f"${v:,.4f}"


def bal_emoji(mode: str) -> str:
    return "💵" if mode == "real" else "🪙"


# ---------- Button ownership (anti-steal) ----------

def cb(action: str, user_id: int) -> str:
    """Encode owner into callback_data: action:user_id"""
    return f"{action}:{user_id}"


def parse_cb(data: str):
    """
    Returns (action, owner_id or None).
    Supports both 'action:123' and plain 'action'.
    """
    if ":" in data:
        action, uid = data.rsplit(":", 1)
        if uid.isdigit():
            return action, int(uid)
    return data, None


async def guard_owner(cq: CallbackQuery, owner_id: int = None) -> bool:
    """
    If callback has owner or owner_id given, only that user may press it.
    Returns True if allowed, False if blocked (already answered).
    """
    action, embedded = parse_cb(cq.data)
    expected = owner_id if owner_id is not None else embedded
    if expected is not None and cq.from_user.id != expected:
        await cq.answer("❌ Ye tumhara menu nahi hai!", show_alert=True)
        return False
    return True


# ---------- UI builders ----------

def box(title: str, lines: list = None) -> str:
    """Compact modern card."""
    out = [f"╭──────────────────╮", f"│  {title}", f"╰──────────────────╯"]
    if lines:
        out.append("")
        out.extend(lines)
    return "\n".join(out)


def sep() -> str:
    return "────────────"


def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    u = user_id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎯 Limbo", callback_data=cb("menu_limbo", u)),
                InlineKeyboardButton("🃏 Blackjack", callback_data=cb("menu_bj", u)),
            ],
            [
                InlineKeyboardButton("👛 Balance", callback_data=cb("menu_balance", u)),
                InlineKeyboardButton("📢 Profile", callback_data=cb("menu_profile", u)),
            ],
            [
                InlineKeyboardButton("🏆 Leaderboard", callback_data=cb("menu_lb", u)),
                InlineKeyboardButton("👑 Rank", callback_data=cb("menu_rank", u)),
            ],
            [
                InlineKeyboardButton("💳 Deposit", callback_data=cb("menu_deposit", u)),
                InlineKeyboardButton("💸 Withdraw", callback_data=cb("menu_withdraw", u)),
            ],
            [
                InlineKeyboardButton("🔄 Rakeback", callback_data=cb("menu_rakeback", u)),
                InlineKeyboardButton("🎁 Tip", callback_data=cb("menu_tip", u)),
            ],
            [
                InlineKeyboardButton("📜 History", callback_data=cb("menu_history", u)),
            ],
        ]
    )


def balance_kb(mode: str, user_id: int) -> InlineKeyboardMarkup:
    u = user_id
    # Toggle button shows the OTHER mode to switch to
    if mode == "real":
        toggle = InlineKeyboardButton("🪙 Coin balance", callback_data=cb("mode_virtual", u))
    else:
        toggle = InlineKeyboardButton("💵 Real balance", callback_data=cb("mode_real", u))
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💳 Deposit", callback_data=cb("menu_deposit", u)),
                InlineKeyboardButton("💸 Withdraw", callback_data=cb("menu_withdraw", u)),
            ],
            [toggle],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=cb("menu_balance", u)),
                InlineKeyboardButton("🔙 Back", callback_data=cb("menu_main", u)),
            ],
        ]
    )


def back_kb(user_id: int, to: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back", callback_data=cb(to, user_id))]]
    )


def lb_kb(user_id: int) -> InlineKeyboardMarkup:
    u = user_id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏆 Real", callback_data=cb("lb_real", u)),
                InlineKeyboardButton("🪙 Virtual", callback_data=cb("lb_virtual", u)),
            ],
            [InlineKeyboardButton("🔙 Back", callback_data=cb("menu_main", u))],
        ]
    )


def rakeback_kb(user_id: int) -> InlineKeyboardMarkup:
    u = user_id
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Claim", callback_data=cb("claim_rakeback", u))],
            [InlineKeyboardButton("🔙 Back", callback_data=cb("menu_main", u))],
        ]
    )


def bj_kb(user_id: int, can_double: bool = True) -> InlineKeyboardMarkup:
    u = user_id
    row = [
        InlineKeyboardButton("👊 Hit", callback_data=cb("bj_hit", u)),
        InlineKeyboardButton("✋ Stand", callback_data=cb("bj_stand", u)),
    ]
    if can_double:
        row.append(InlineKeyboardButton("⚡ Double", callback_data=cb("bj_double", u)))
    return InlineKeyboardMarkup(
        [row, [InlineKeyboardButton("❌ Cancel", callback_data=cb("bj_cancel", u))]]
    )
