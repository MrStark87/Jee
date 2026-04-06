"""
scheduler.py — APScheduler for:
1. Lecture time-based alerts
2. Daily morning message (6 AM)
"""
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_conn, get_all_users

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def setup_scheduler(app):
    # Check lectures every minute
    scheduler.add_job(
        send_lecture_alerts,
        trigger="interval",
        minutes=1,
        args=[app],
        id="lecture_alerts",
        replace_existing=True,
    )
    # Daily morning message at 6:00 AM IST
    scheduler.add_job(
        send_morning_message,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"),
        args=[app],
        id="morning_msg",
        replace_existing=True,
    )
    scheduler.start()


async def send_lecture_alerts(app):
    now_str = datetime.datetime.now().strftime("%H:%M")
    conn    = get_conn()
    lecs    = conn.execute(
        "SELECT * FROM lectures WHERE alert_time=? AND active=1",
        (now_str,)
    ).fetchall()
    conn.close()

    for l in lecs:
        try:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Open Link",    url=l["link"]),
                 InlineKeyboardButton("✅ Mark Watched", callback_data=f"lec_watched_{l['id']}")],
                [InlineKeyboardButton("⏰ Remind in 15 min", callback_data=f"lec_snooze_{l['id']}"),
                 InlineKeyboardButton("⏱ Start Timer",       callback_data="timer_25")],
            ])
            sub   = f"[{l['subject']}] " if l["subject"] else ""
            extra = f"\n\n💬 _{l['message']}_" if l["message"] else ""
            text  = (
                f"📚 *Lecture Time!*\n\n"
                f"{sub}*{l['title']}*"
                f"{extra}"
            )
            await app.bot.send_message(
                l["user_id"], text,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            print(f"Alert send failed for user {l['user_id']}: {e}")


async def send_morning_message(app):
    today_str = datetime.date.today().strftime("%A, %d %B %Y")
    users     = get_all_users()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Open Today", callback_data="today_home")],
    ])
    for uid in users:
        try:
            conn = get_conn()
            pending = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND done=0 AND date=?",
                (uid, datetime.date.today().isoformat())
            ).fetchone()[0]
            conn.close()
            text = (
                f"🌅 *Subah ho gayi!*\n"
                f"📅 {today_str}\n\n"
                f"_Uthho, padho, conquer karo!_ 💪\n\n"
                f"Aaj ka plan set karo 👇"
            )
            await app.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            print(f"Morning msg failed for {uid}: {e}")
