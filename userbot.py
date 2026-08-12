# ============================================================
# BetNova Cwallet Userbot (Telethon)
# Monitors Cwallet group for tip messages → credits real_balance
# ============================================================

import re
import asyncio
import logging
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.types import User, Channel, Chat

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

# Multiple patterns — Cwallet message formats vary
PATTERNS = [
    # Tanjiro841 tip details:\nUSDT +0.1 novadepos
    re.compile(
        r"(?P<username>[\w\d_]+)\s+tip\s+details[:\s]*.*?"
        r"(?P<currency>USDT|BTC|ETH|TON|TRX|LTC|BNB)\s*\+?\s*(?P<amount>\d+(?:[.,]\d+)?)\s+"
        r"@?(?P<destination>[\w\d_]+)",
        re.IGNORECASE | re.DOTALL,
    ),
    # USDT +0.1 novadepos  (with username earlier in text)
    re.compile(
        r"(?P<username>[\w\d_]+).*?"
        r"(?P<currency>USDT|BTC|ETH|TON|TRX)\s*\+?\s*(?P<amount>\d+(?:[.,]\d+)?)\s+"
        r"@?(?P<destination>[\w\d_]+)",
        re.IGNORECASE | re.DOTALL,
    ),
    # tipped 0.1 USDT to @novadepos / Username tipped ...
    re.compile(
        r"(?P<username>[\w\d_]+)\s+tipped\s+"
        r"(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<currency>USDT|BTC|ETH|TON|TRX)\s+"
        r"(?:to\s+)?@?(?P<destination>[\w\d_]+)",
        re.IGNORECASE | re.DOTALL,
    ),
    # +0.1 USDT → @novadepos from username
    re.compile(
        r"\+?\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<currency>USDT|BTC|ETH|TON|TRX).*?"
        r"@?(?P<destination>[\w\d_]+).*?(?:from|by)\s+@?(?P<username>[\w\d_]+)",
        re.IGNORECASE | re.DOTALL,
    ),
]

client = TelegramClient(USERBOT_SESSION, API_ID, API_HASH)


def parse_tip_message(text: str):
    if not text:
        return None
    # Strip markdown / special chars
    clean = re.sub(r"[*_`~\[\]()]", "", text)
    clean = clean.replace("\xa0", " ")

    for pat in PATTERNS:
        m = pat.search(clean)
        if not m:
            continue
        try:
            amount = float(m.group("amount").replace(",", "."))
        except (ValueError, IndexError):
            continue
        try:
            username = m.group("username").lower().lstrip("@")
            currency = m.group("currency").upper()
            destination = m.group("destination").lower().lstrip("@")
        except IndexError:
            continue
        # Skip false positives (destination looking like currency etc.)
        if destination in ("usdt", "btc", "eth", "ton", "trx", "tip", "details"):
            continue
        if username in ("usdt", "btc", "eth", "ton", "trx", "tip"):
            continue
        if amount <= 0:
            continue
        return {
            "username": username,
            "amount": amount,
            "currency": currency,
            "destination": destination,
        }
    return None


async def process_tip(event, text: str):
    log.info("[CWallet] RAW: %s", text[:300].replace("\n", " | "))

    parsed = parse_tip_message(text)
    if not parsed:
        log.info("[CWallet] No tip pattern matched")
        return

    log.info(
        "[CWallet] Parsed → user=%s amount=%s %s dest=%s",
        parsed["username"], parsed["amount"], parsed["currency"], parsed["destination"],
    )

    if parsed["destination"] != DEPOSIT_USERNAME.lower():
        log.info("[CWallet] Destination mismatch (want %s)", DEPOSIT_USERNAME)
        return

    if parsed["currency"] != "USDT":
        log.info("[CWallet] Non-USDT ignored")
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
                log.info("[CWallet] Duplicate ignored")
                return
            raise
        log.info("[CWallet] User not found in DB: %s (must /start bot first)", parsed["username"])
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
        "[CWallet] ✅ CREDITED user=%s +%.4f USDT → real_balance",
        parsed["username"], parsed["amount"],
    )


@client.on(events.NewMessage(chats=CWALLET_GROUP_ID))
async def on_cwallet_message(event):
    try:
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        log.info(
            "[CWallet] Msg id=%s chat=%s sender=%s",
            event.id, event.chat_id, sender_id,
        )

        # Accept from Cwallet bot OR any message in the deposit group that looks like a tip
        if sender_id != CWALLET_BOT_ID:
            # Still try parse — some setups forward / different bot id
            text = event.raw_text or ""
            if "tip" not in text.lower() and "usdt" not in text.lower():
                return
            log.info("[CWallet] Non-bot sender %s but tip-like text, trying parse", sender_id)

        text = event.raw_text or ""
        if not text.strip():
            # Try message text from entities
            text = getattr(event.message, "message", "") or ""
        await process_tip(event, text)

    except Exception as e:
        log.exception("[CWallet] Error: %s", e)


# Also catch edits (sometimes tips appear as edits)
@client.on(events.MessageEdited(chats=CWALLET_GROUP_ID))
async def on_cwallet_edit(event):
    try:
        sender = await event.get_sender()
        if getattr(sender, "id", None) != CWALLET_BOT_ID:
            return
        text = event.raw_text or ""
        log.info("[CWallet] Edited message id=%s", event.id)
        await process_tip(event, text)
    except Exception as e:
        log.exception("[CWallet] Edit error: %s", e)


async def main():
    await init_db()
    await client.start()
    me = await client.get_me()
    log.info("Userbot started as %s (id=%s)", me.username or me.first_name, me.id)
    log.info("Monitoring group=%s bot_id=%s deposit=@%s", CWALLET_GROUP_ID, CWALLET_BOT_ID, DEPOSIT_USERNAME)

    # Verify group access
    try:
        entity = await client.get_entity(CWALLET_GROUP_ID)
        title = getattr(entity, "title", str(entity))
        log.info("Group OK: %s", title)
    except Exception as e:
        log.error("❌ Cannot access group %s: %s", CWALLET_GROUP_ID, e)
        log.error("→ Userbot account must be MEMBER of the Cwallet group")
        log.error("→ Set correct CWALLET_GROUP_ID in config.py")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
