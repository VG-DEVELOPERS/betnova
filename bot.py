# ============================================================
# BetNova Telegram Bot (Pyrogram) – Entry Point
# ============================================================

import logging

from pyrogram import Client, idle
from pyrogram.session import Session

from config import API_ID, API_HASH, BOT_TOKEN
from database import init_db

from handlers import balance, profile, tip
from games import limbo, blackjack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("BetNova")

# Silence noisy pyrogram logs a bit
logging.getLogger("pyrogram").setLevel(logging.WARNING)

app = Client(
    "betnova_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


def register_all(client: Client):
    balance.register(client)
    profile.register(client)
    tip.register(client)
    limbo.register(client)
    blackjack.register(client)
    log.info("All handlers registered")


async def main():
    register_all(app)
    await init_db()
    await app.start()
    me = await app.get_me()
    log.info("Bot started as @%s (id=%s)", me.username, me.id)
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(main())
