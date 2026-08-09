# ============================================================
# Shared helpers & keyboards
# ============================================================

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def fmt_money(v: float) -> str:
    return f"${v:,.4f}"


def bal_emoji(mode: str) -> str:
    return "💵" if mode == "real" else "🪙"


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎯 Limbo", callback_data="menu_limbo"),
                InlineKeyboardButton("🃏 Blackjack", callback_data="menu_bj"),
            ],
            [
                InlineKeyboardButton("👛 Balance", callback_data="menu_balance"),
                InlineKeyboardButton("📢 Profile", callback_data="menu_profile"),
            ],
            [
                InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_lb"),
                InlineKeyboardButton("👑 Rank", callback_data="menu_rank"),
            ],
            [
                InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw"),
            ],
            [
                InlineKeyboardButton("🔄 Rakeback", callback_data="menu_rakeback"),
                InlineKeyboardButton("🎁 Tip", callback_data="menu_tip"),
            ],
            [
                InlineKeyboardButton("📜 History", callback_data="menu_history"),
            ],
        ]
    )


def balance_kb(mode: str) -> InlineKeyboardMarkup:
    real_mark = " ✓" if mode == "real" else ""
    virt_mark = " ✓" if mode == "virtual" else ""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"💵 Real{real_mark}", callback_data="mode_real"),
                InlineKeyboardButton(f"🪙 Virtual{virt_mark}", callback_data="mode_virtual"),
            ],
            [
                InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="menu_balance"),
                InlineKeyboardButton("🔙 Back", callback_data="menu_main"),
            ],
        ]
    )


def back_kb(to: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=to)]])
