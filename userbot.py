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

client = TelegramClient(USERBOT_SESSION, API_ID, API_HASH)

# ---------- parsers ----------

def _clean(text: str) -> str:
    t = re.sub(r"[*_`~]", "", text or "")
    t = t.replace("\xa0", " ")
    return t


def parse_tip_message(text: str):
    """
    Supports formats like:
      Tanjiro841 tip details:
      USDT +0.1 novadepos

      **user** tip details:
      USDT +0.10 novadepos

      user tipped 0.1 USDT to novadepos
    """
    if not text:
        return None
    clean = _clean(text)
    lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
    joined = " ".join(lines)

    username = None
    amount = None
    currency = None
    destination = None

    # --- Pattern A: "username tip details" ---
    m = re.search(r"([\w\d_]+)\s+tip\s+details", clean, re.I)
    if m:
        username = m.group(1).lower()

    # --- Pattern B: "username tipped" ---
    m2 = re.search(r"([\w\d_]+)\s+tipped\s+(\d+(?:[.,]\d+)?)\s*(USDT|BTC|ETH|TON|TRX)", clean, re.I)
    if m2:
        username = m2.group(1).lower()
        amount = float(m2.group(2).replace(",", "."))
        currency = m2.group(3).upper()

    # --- Amount + currency anywhere ---
    # USDT +0.1  /  +0.1 USDT  /  0.1 USDT
    if amount is None:
        m3 = re.search(
            r"(?:(USDT|BTC|ETH|TON|TRX)\s*\+?\s*(\d+(?:[.,]\d+)?)|\+?\s*(\d+(?:[.,]\d+)?)\s*(USDT|BTC|ETH|TON|TRX))",
            clean,
            re.I,
        )
        if m3:
            if m3.group(1):
                currency = m3.group(1).upper()
                amount = float(m3.group(2).replace(",", "."))
            else:
                amount = float(m3.group(3).replace(",", "."))
                currency = m3.group(4).upper()

    # --- Destination: look for DEPOSIT_USERNAME in text ---
    dest_wanted = DEPOSIT_USERNAME.lower().lstrip("@")
    if re.search(rf"@?{re.escape(dest_wanted)}\b", clean, re.I):
        destination = dest_wanted

    # Fallback: last word after amount line that looks like username
    if destination is None:
        m4 = re.search(
            rf"(?:USDT|BTC|ETH|TON|TRX)\s*\+?\s*\d+(?:[.,]\d+)?\s+@?([\w\d_]+)",
            clean,
            re.I,
        )
        if m4:
            destination = m4.group(1).lower()

    # Username fallback: first token on first line if still missing
    if username is None and lines:
        first = re.sub(r"[^\w\d_]", "", lines[0].split()[0]) if lines[0].split() else ""
        if first and first.lower() not in ("usdt", "btc", "eth", "tip", "details"):
            # only if "tip" appears in message
            if "tip" in clean.lower():
                username = first.lower()

    if not username or amount is None or not currency or not destination:
        return None
    if amount <= 0:
        return None
    if destination in ("usdt", "btc", "eth", "ton", "trx", "tip", "details"):
        return None

    return {
        "username": username.lstrip("@"),
        "amount": float(amount),
        "currency": currency.upper(),
        "destination": destination.lstrip("@"),
    }


async def process_tip(event, text: str):
    log.info("[CWallet] RAW (%s chars): %s", len(text or ""), (text or "")[:400].replace("\n", " || "))

    parsed = parse_tip_message(text)
    if not parsed:
        log.info("[CWallet] ❌ parse failed — check message format")
        return

    log.info(
        "[CWallet] Parsed user=%s amt=%s %s dest=%s",
        parsed["username"], parsed["amount"], parsed["currency"], parsed["destination"],
    )

    if parsed["destination"] != DEPOSIT_USERNAME.lower().lstrip("@"):
        log.info("[CWallet] dest mismatch want=@%s got=%s", DEPOSIT_USERNAME, parsed["destination"])
        return

    if parsed["currency"] != "USDT":
        log.info("[CWallet] skip non-USDT: %s", parsed["currency"])
        return

    deposit_doc = {
        "user_id": None,
        "username": parsed["username"],
        "amount": parsed["amount"],
        "currency": "USDT",
        "destination": DEPOSIT_USERNAME,
        "cwallet_message_id": event.id,
        "chat_id": event.chat_id,
        "status": "pending",
        "type": "real",
        "created_at": datetime.utcnow(),
        "raw_text": (text or "")[:500],
    }

    user = await get_user_by_username(parsed["username"])
    if not user:
        deposit_doc["status"] = "user_not_found"
        try:
            await save_deposit(deposit_doc)
        except Exception as e:
            if "duplicate" in str(e).lower() or "E11000" in str(e):
                log.info("[CWallet] duplicate ignored")
                return
            raise
        log.info("[CWallet] ⚠️ user @%s not in DB — unhe /start karna hoga", parsed["username"])
        return

    deposit_doc["user_id"] = user["_id"]
    deposit_doc["status"] = "confirmed"
    try:
        await save_deposit(deposit_doc)
    except Exception as e:
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            log.info("[CWallet] duplicate ignored")
            return
        raise

    await credit_deposit(user["_id"], parsed["amount"])
    log.info("[CWallet] ✅ +%.4f USDT → @%s (id=%s)", parsed["amount"], parsed["username"], user["_id"])


@client.on(events.NewMessage(chats=CWALLET_GROUP_ID))
async def on_cwallet_message(event):
    try:
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        text = event.raw_text or getattr(event.message, "message", "") or ""

        log.info("[CWallet] msg id=%s chat=%s sender=%s", event.id, event.chat_id, sender_id)

        # Prefer Cwallet bot, but also try any tip-like text in this group
        if sender_id != CWALLET_BOT_ID:
            low = text.lower()
            if "tip" not in low and "usdt" not in low:
                return
            log.info("[CWallet] sender != bot (%s), still parsing tip-like msg", sender_id)

        await process_tip(event, text)
    except Exception as e:
        log.exception("[CWallet] error: %s", e)


@client.on(events.MessageEdited(chats=CWALLET_GROUP_ID))
async def on_cwallet_edit(event):
    try:
        sender = await event.get_sender()
        if getattr(sender, "id", None) != CWALLET_BOT_ID:
            return
        text = event.raw_text or ""
        log.info("[CWallet] edit id=%s", event.id)
        await process_tip(event, text)
    except Exception as e:
        log.exception("[CWallet] edit error: %s", e)


async def main():
    await init_db()
    await client.start()
    me = await client.get_me()
    log.info("Userbot = %s id=%s", me.username or me.first_name, me.id)
    log.info("Watch group=%s bot=%s deposit=@%s", CWALLET_GROUP_ID, CWALLET_BOT_ID, DEPOSIT_USERNAME)

    try:
        entity = await client.get_entity(CWALLET_GROUP_ID)
        log.info("Group OK: %s", getattr(entity, "title", entity))
    except Exception as e:
        log.error("❌ Group access fail %s: %s", CWALLET_GROUP_ID, e)
        log.error("→ Userbot must JOIN the Cwallet group")
        log.error("→ Fix CWALLET_GROUP_ID in config.py")

    # Self-test parser
    test = "Tanjiro841 tip details:\nUSDT +0.1 novadepos"
    p = parse_tip_message(test)
    log.info("Parser self-test: %s", p)

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
