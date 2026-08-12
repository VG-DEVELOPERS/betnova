# ============================================================
# BetNova Database Layer (Motor / MongoDB)
# ============================================================

from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from config import (
    MONGO_URI,
    DATABASE_NAME,
    STARTING_REAL_BALANCE,
    STARTING_VIRTUAL_COINS,
    RAKEBACK_RATE,
)

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

users = db.users
games = db.games
tips = db.tips
deposits = db.deposits
blackjack_games = db.blackjack_games


async def init_db():
    await users.create_index("username")
    await deposits.create_index("cwallet_message_id", unique=True)
    await games.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await tips.create_index([("from_id", ASCENDING), ("created_at", DESCENDING)])
    await tips.create_index([("to_id", ASCENDING), ("created_at", DESCENDING)])
    await blackjack_games.create_index("user_id", unique=True)
    print("[DB] Indexes ensured")


async def ensure_user(user_id: int, name: str = "", username: str = None):
    now = datetime.utcnow()
    update = {
        "$setOnInsert": {
            "mode": "real",
            "real_balance": float(STARTING_REAL_BALANCE),
            "virtual_coins": float(STARTING_VIRTUAL_COINS),
            "verified_deposits_usdt": 0.0,
            "wagered": 0.0,
            "won": 0.0,
            "lost": 0.0,
            "rakeback": 0.0,
            "games": 0,
            "biggest_win": 0.0,
            "game_counts": {"limbo": 0, "blackjack": 0},
            "rank_level": 0,
            "created_at": now,
        },
        "$set": {
            "name": name or "",
            "username": username.lower() if username else None,
            "updated_at": now,
        },
    }
    await users.update_one({"_id": user_id}, update, upsert=True)
    return await users.find_one({"_id": user_id})


async def get_user(user_id: int):
    return await users.find_one({"_id": user_id})


async def get_user_by_username(username: str):
    if not username:
        return None
    return await users.find_one({"username": username.lower()})


async def set_mode(user_id: int, mode: str):
    if mode not in ("real", "virtual"):
        return False
    result = await users.update_one({"_id": user_id}, {"$set": {"mode": mode}})
    return result.modified_count > 0 or result.matched_count > 0


async def get_balance(user: dict) -> float:
    if user.get("mode") == "virtual":
        return float(user.get("virtual_coins", 0))
    return float(user.get("real_balance", 0))


async def atomic_bet(user_id: int, amount: float, mode: str, game_name: str = None):
    amount = float(amount)
    if amount <= 0:
        return None

    field = "real_balance" if mode == "real" else "virtual_coins"
    filter_q = {"_id": user_id, field: {"$gte": amount}}
    update = {
        "$inc": {
            field: -amount,
            "wagered": amount,
            "games": 1,
            "rakeback": amount * RAKEBACK_RATE,
        }
    }
    if game_name:
        update["$inc"][f"game_counts.{game_name}"] = 1

    result = await users.find_one_and_update(
        filter_q,
        update,
        return_document=ReturnDocument.AFTER,
    )
    return result


async def atomic_credit_win(user_id: int, total_return: float, profit: float, mode: str):
    field = "real_balance" if mode == "real" else "virtual_coins"
    inc = {
        field: float(total_return),
        "won": float(profit) if profit > 0 else 0.0,
    }
    update = {"$inc": inc}
    # Track biggest win
    if profit > 0:
        update["$max"] = {"biggest_win": float(profit)}

    await users.update_one({"_id": user_id}, update)


async def save_game(doc: dict):
    await games.insert_one(doc)


async def save_tip(doc: dict):
    await tips.insert_one(doc)


async def save_deposit(doc: dict):
    await deposits.insert_one(doc)


async def credit_deposit(user_id: int, amount: float):
    amount = float(amount)
    await users.update_one(
        {"_id": user_id},
        {"$inc": {"real_balance": amount, "verified_deposits_usdt": amount}},
    )


async def claim_rakeback(user_id: int, mode: str):
    user = await get_user(user_id)
    if not user:
        return None
    rb = float(user.get("rakeback", 0))
    if rb <= 0:
        return 0.0

    field = "real_balance" if mode == "real" else "virtual_coins"
    result = await users.find_one_and_update(
        {"_id": user_id, "rakeback": {"$gt": 0}},
        {"$inc": {field: rb}, "$set": {"rakeback": 0.0}},
        return_document=ReturnDocument.AFTER,
    )
    return rb if result else 0.0


async def get_leaderboard(mode: str, limit: int = 10):
    field = "real_balance" if mode == "real" else "virtual_coins"
    cursor = users.find({field: {"$gt": 0}}).sort(field, DESCENDING).limit(limit)
    return await cursor.to_list(length=limit)


# Rank thresholds: (min_wagered, level, title, level_up_bonus)
# No rank until $100 wagered. Level-ups grant bonus to real_balance.
RANK_TIERS = [
    (0,       0,  "⬜ Unranked",     0.0),
    (100,     1,  "⚡️ Iron I",       0.50),
    (300,     2,  "⚡️ Iron II",      1.00),
    (750,     3,  "⚡️ Iron III",     2.00),
    (1500,    4,  "🥉 Bronze I",     3.00),
    (3000,    5,  "🥉 Bronze II",    5.00),
    (6000,    6,  "🥉 Bronze III",   8.00),
    (10000,   7,  "🥈 Silver I",    12.00),
    (18000,   8,  "🥈 Silver II",   18.00),
    (30000,   9,  "🥈 Silver III",  25.00),
    (50000,  10,  "🥇 Gold I",      40.00),
    (80000,  11,  "🥇 Gold II",     60.00),
    (120000, 12,  "🥇 Gold III",    90.00),
    (200000, 13,  "👑 Platinum",   150.00),
    (350000, 14,  "💎 Diamond",    250.00),
    (600000, 15,  "🔥 Master",     400.00),
    (1000000,16,  "🌟 Legend",     750.00),
]


def get_rank_tier(wagered: float):
    """Return (min_wager, level, title, bonus) for current wagered amount."""
    current = RANK_TIERS[0]
    for tier in RANK_TIERS:
        if wagered >= tier[0]:
            current = tier
        else:
            break
    return current


async def get_rank_info(wagered: float) -> str:
    _, _, title, _ = get_rank_tier(float(wagered or 0))
    return title


async def check_and_apply_level_up(user_id: int):
    """
    After wager increases, check if rank_level went up.
    Credits level-up bonus(es) to real_balance and updates rank_level.
    Returns info dict if leveled up, else None.
    """
    user = await get_user(user_id)
    if not user:
        return None

    wagered = float(user.get("wagered", 0))
    old_level = int(user.get("rank_level", 0))
    _, new_level, title, _ = get_rank_tier(wagered)

    if new_level <= old_level:
        return None

    total_bonus = 0.0
    unlocked = []
    for tier_min, tier_level, tier_title, tier_bonus in RANK_TIERS:
        if old_level < tier_level <= new_level and tier_bonus > 0:
            total_bonus += tier_bonus
            unlocked.append({"level": tier_level, "title": tier_title, "bonus": tier_bonus})

    if total_bonus > 0:
        await users.update_one(
            {"_id": user_id},
            {
                "$set": {"rank_level": new_level},
                "$inc": {"real_balance": total_bonus},
            },
        )
    else:
        await users.update_one({"_id": user_id}, {"$set": {"rank_level": new_level}})

    return {
        "old_level": old_level,
        "new_level": new_level,
        "title": title,
        "total_bonus": total_bonus,
        "unlocked": unlocked,
    }


def get_favorite_game(user: dict) -> str:
    counts = user.get("game_counts") or {}
    if not counts:
        return "—"
    best = max(counts, key=counts.get)
    if counts.get(best, 0) <= 0:
        return "—"
    icons = {"limbo": "⬆️ Limbo", "blackjack": "🃏 Blackjack"}
    return icons.get(best, best.title())


async def get_recent_history(user_id: int, limit: int = 8):
    deps = await deposits.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(5).to_list(5)
    gms = await games.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(5).to_list(5)
    tps = await tips.find({"$or": [{"from_id": user_id}, {"to_id": user_id}]}).sort("created_at", DESCENDING).limit(5).to_list(5)

    items = []
    for d in deps:
        items.append(("deposit", d))
    for g in gms:
        items.append(("game", g))
    for t in tps:
        items.append(("tip", t))

    items.sort(key=lambda x: x[1].get("created_at", datetime.min), reverse=True)
    return items[:limit]


# ---------- Blackjack state ----------

async def save_bj_state(user_id: int, state: dict):
    state["updated_at"] = datetime.utcnow()
    await blackjack_games.update_one({"user_id": user_id}, {"$set": state}, upsert=True)


async def get_bj_state(user_id: int):
    return await blackjack_games.find_one({"user_id": user_id})


async def delete_bj_state(user_id: int):
    await blackjack_games.delete_one({"user_id": user_id})
