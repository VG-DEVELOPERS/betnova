# BetNova – Telegram Casino Bot (Real Balance)

Modular production bot: **Pyrogram** + **Telethon** + **MongoDB Motor**.

```
betnova/
├── config.py
├── database.py
├── bot.py                 # Entry point
├── userbot.py             # Cwallet monitor
├── utils.py               # Shared helpers / keyboards
├── games/
│   ├── limbo.py
│   └── blackjack.py
├── handlers/
│   ├── balance.py         # Start, balance, mode, deposit, rank, lb, history, rakeback
│   ├── profile.py         # /profile /stats
│   └── tip.py
├── requirements.txt
└── README.md
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Edit `config.py`, then:

```bash
python bot.py          # Terminal 1
python userbot.py      # Terminal 2
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu |
| `/balance` | Show balance + mode switch |
| `/profile` or `/stats` | Full player profile |
| `/limbo <amt> <mult>` | Play Limbo |
| `/blackjack <amt>` | Play Blackjack |
| `/tip <amt>` | Tip (reply) |
| `/tip @user <amt>` | Tip by username |
| `/rakeback` | Claim rakeback |

## Profile Example

```
📢 Profile

ℹ️ User: Tanjiro (7958077163)
⬆️ Rank: ⚡️ Iron I
👛 Balance: $0.00
🪙 Coins: 8

⚡️ Total games: 152
Total bets: $126.3562
Total wins: $123.1262

🎲 Favorite game: ⬆️ Limbo
🎉 Biggest win: $9.6

🕒 Registration date: 17.01.2026
```

## Notes

- Cwallet tips → `real_balance`
- Withdrawals disabled
- Commands work in groups + private
- Games & stats in separate modules
