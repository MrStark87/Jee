# JEE Saarthi Bot — Setup Guide

## Step 1 — Dependencies install karo
```bash
pip install -r requirements.txt
```

## Step 2 — config.py edit karo
```python
BOT_TOKEN = "YOUR_BOT_TOKEN"   # BotFather se
ADMIN_ID   = 123456789          # Apna Telegram ID (https://t.me/userinfobot se pata karo)
ADMIN_PASS = "yourpassword"     # Admin panel ka password
```

## Step 3 — Run karo
```bash
python bot.py
```

## VPS pe 24/7 chalane ke liye (systemd service)
```bash
# /etc/systemd/system/jeebot.service
[Unit]
Description=JEE Saarthi Bot
After=network.target

[Service]
WorkingDirectory=/path/to/jee_saarthi_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable jeebot
sudo systemctl start jeebot
sudo systemctl status jeebot
```

## Bot ka use kaise karein

### Start
- `/start` — Home screen khulega 5 buttons ke saath

### Today Section
- Tasks add/complete/delete — sab inline
- Lectures add — title, koi bhi link, subject, time, custom message
- Timer — 15/25/50 min ya custom

### Memories Section  
- **Silly** — apni silly mistakes (text/image)
- **Error** — galat questions (Question + Answer + Key Points)
- **Important** — important questions (Question + Answer + Key Points)
- Search: `/search q1` — title se seedha dhundho

### Formulas
- Admin jo bhi chapter upload kare, sab button ban jaata hai
- Click karo, PDF/notes aa jayenge

### Motivation
- Apne khud ke quotes — private, sirf tumhare liye

### Thoughts
- Random thoughts — text/image — private

### Admin Panel
- `/start` → Admin button → Password daalo
- Formula upload: Class 11/12 → Chapter naam → File bhejo
- Broadcast: Sabko ek saath message

## File Structure
```
jee_saarthi_bot/
├── bot.py              # Main entry point
├── config.py           # Token, Admin ID, Password
├── database.py         # SQLite schema & helpers
├── scheduler.py        # APScheduler (lecture alerts, morning msg)
├── requirements.txt
└── handlers/
    ├── __init__.py
    ├── common.py       # /start, home keyboard
    ├── today.py        # Tasks + Lectures + Timer
    ├── memories.py     # Silly + Error + Important
    ├── formulas.py     # Formula viewer (shared)
    ├── motivation.py   # Private quotes
    ├── thought.py      # Private thoughts
    ├── admin.py        # Admin panel
    └── search.py       # /search command
```
