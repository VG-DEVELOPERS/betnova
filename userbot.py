# ============================================================
# BetNova Cwallet Userbot (Telethon)
# ============================================================

import re
import asyncio
import logging
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.types import User

from config import (
    API_ID,
    API_HASH,
    CWALLET_GROUP_ID,
    CWALLET_BOT_ID,
    DEPOSIT_USERNAME,
    USERBOT_SESSION,
)
from database import (
    init_db,
    get_user_by_username,
    credit_deposit,
    save_deposit,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("CWallet")

TIP_PATTERN = re.compile(
    r"(?P<username>[\w\d_]+)\s+tip\s+details[:\s]*"
    r".*?"
    r"(?P<currency>USDT|BTC|ETH|TON|TRX)\s*\+?(?P<amount>\d+(?:\.\d+)?)\s+"
    r"(?P<destination>[\w\d_]+)",
    re.IGNORECASE | re.DOTALL,
)

client = TelegramClient(USERBOT_SESSION, API_ID, API_HASH)


def parse_tip_message(text: str):
    if not text:
        return None
    clean = re.sub(r"[*_`]", "", text)
    m = TIP_PATTERN.search(clean)
    if not m:
        return None
    try:
        amount = float(m.group("amount"))
    except ValueError:
        return None
    return {
        "username": m.group("username").lower(),
        "amount": amount,
        "currency": m.group("currency").upper(),
        "destination": m.group("destination").lower(),
    }


@client.on(events.NewMessage(chats=CWALLET_GROUP_ID))
async def on_cwallet_message(event):
    try:
        sender = await event.get_sender()
        if not isinstance(sender, User) or sender.id != CWALLET_BOT_ID:
            return

        text = event.raw_text or ""
        log.info("[CWallet] Message received (id=%s)", event.id)

        parsed = parse_tip_message(text)
        if not parsed:
            log.info("[CWallet] Message did not match tip pattern")
            return

        log.info("[CWallet] Parsed username: %s", parsed["username"])
        log.info("[CWallet] Parsed amount: %s %s → %s", parsed["amount"], parsed["currency"], parsed["destination"])

        if parsed["destination"] != DEPOSIT_USERNAME.lower():
            log.info("[CWallet] Destination mismatch, ignoring")
            return

        if parsed["currency"] != "USDT":
            log.info("[CWallet] Non-USDT tip ignored")
            return

        deposit_doc = {
            "user_id": None,
            "username": parsed["username"],
            "amount": parsed["amount"],
            "currency": "USDT",
            "destination": DEPOSIT_USERNAME,
            "cwallet_message_id": event.id,
            "status": "pending",
            "type": "real",
            "created_at": datetime.utcnow(),
            "raw_text": text[:500],
        }

        user = await get_user_by_username(parsed["username"])
        if not user:
            deposit_doc["status"] = "user_not_found"
            try:
                await save_deposit(deposit_doc)
            except Exception as e:
                if "duplicate" in str(e).lower() or "E11000" in str(e):
                    log.info("[CWallet] Duplicate ignored (user_not_found)")
                    return
                raise
            log.info("[CWallet] User not found: %s", parsed["username"])
            return

        deposit_doc["user_id"] = user["_id"]
        deposit_doc["status"] = "confirmed"

        try:
            await save_deposit(deposit_doc)
        except Exception as e:
            if "duplicate" in str(e).lower() or "E11000" in str(e):
                log.info("[CWallet] Duplicate ignored")
                return
            raise

        await credit_deposit(user["_id"], parsed["amount"])
        log.info(
            "[CWallet] Deposit credited | user=%s | +%.4f USDT → real_balance",
            parsed["username"],
            parsed["amount"],
        )

    except Exception as e:
        log.exception("[CWallet] Error processing message: %s", e)


async def main():
    await init_db()
    await client.start()
    me = await client.get_me()
    log.info("Userbot started as %s (id=%s)", me.username or me.first_name, me.id)
    log.info("Monitoring Cwallet group %s for bot %s", CWALLET_GROUP_ID, CWALLET_BOT_ID)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
