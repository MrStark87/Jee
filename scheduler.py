"""
scheduler.py — All scheduled jobs (IST timezone)
1. Lecture time-based alerts     — every minute
2. Daily morning message         — 6:00 AM
3. Weekly progress report        — Sunday 8:00 AM
4. Revision due reminders        — 9:00 AM daily
5. Daily formula flash card      — 7:00 AM
"""
import datetime
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from database import get_conn, get_all_users
from ui import E

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def setup_scheduler(app):
    scheduler.add_job(job_lecture_alerts,  "interval", minutes=1,  args=[app], id="lec_alerts",  replace_existing=True)
    scheduler.add_job(job_morning_msg,     CronTrigger(hour=6,  minute=0, timezone="Asia/Kolkata"), args=[app], id="morning",   replace_existing=True)
    scheduler.add_job(job_weekly_report,   CronTrigger(day_of_week="sun", hour=8, timezone="Asia/Kolkata"), args=[app], id="weekly", replace_existing=True)
    scheduler.add_job(job_revision_alerts, CronTrigger(hour=9, minute=0, timezone="Asia/Kolkata"), args=[app], id="revision", replace_existing=True)
    scheduler.add_job(job_formula_flash,   CronTrigger(hour=7, minute=0, timezone="Asia/Kolkata"), args=[app], id="formula_flash", replace_existing=True)
    scheduler.start()


# ── 1. Lecture Alerts ──────────────────────────────────────────
async def job_lecture_alerts(app):
    now_str = datetime.datetime.now().strftime("%H:%M")
    conn    = get_conn()
    lecs    = conn.execute(
        "SELECT * FROM lectures WHERE alert_time=? AND active=1", (now_str,)
    ).fetchall()
    conn.close()

    for l in lecs:
        try:
            kb = Kb([
                [Btn(f"{E['link']} Open Link",      url=l["link"]),
                 Btn(f"{E['done']} Mark Watched",   callback_data=f"lec_watched_{l['id']}")],
                [Btn(f"Remind in 15 min",            callback_data=f"lec_snooze_{l['id']}"),
                 Btn(f"{E['timer']} Start Timer",    callback_data="timer_25")],
            ])
            subj  = f"`{l['subject']}` " if l["subject"] else ""
            extra = f"\n\n💬 _{l['message']}_" if l["message"] else ""
            text  = (
                f"{E['lecture']} *Lecture Time!*\n"
                f"{DIVIDER if False else ''}"
                f"\n{subj}*{l['title']}*{extra}"
            )
            await app.bot.send_message(l["user_id"], text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            print(f"[Scheduler] Lecture alert failed for {l['user_id']}: {e}")


# ── 2. Morning Message ─────────────────────────────────────────
MORNING_QUOTES = [
    "Small steps every day lead to big results.",
    "Your future self is watching. Make them proud.",
    "The difference between ordinary and extraordinary is that little extra.",
    "Discipline is doing it even when you don't feel like it.",
    "Trust the process. Results take time.",
    "One more chapter. One more problem. One more day.",
    "Champions train even on their worst days.",
]

async def job_morning_msg(app):
    today = datetime.date.today().strftime("%A, %d %B %Y")
    users = get_all_users()
    quote = random.choice(MORNING_QUOTES)
    for uid in users:
        try:
            conn = get_conn()
            tasks_due = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND done=0 AND date=?",
                (uid, datetime.date.today().isoformat())
            ).fetchone()[0]
            streak = conn.execute("SELECT streak FROM users WHERE tg_id=?", (uid,)).fetchone()
            streak = streak["streak"] if streak else 0
            conn.close()

            kb = Kb([[Btn(f"{E['task']} Open Today", callback_data="today_home")]])
            await app.bot.send_message(
                uid,
                f"🌅 *Good morning!*\n"
                f"{E['calendar']} {today}\n"
                f"{E['streak']} Streak: *{streak} day{'s' if streak!=1 else ''}*\n\n"
                f"_{quote}_\n\n"
                f"Set your plan for today 👇",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            print(f"[Scheduler] Morning msg failed for {uid}: {e}")


# ── 3. Weekly Report ───────────────────────────────────────────
async def job_weekly_report(app):
    today = datetime.date.today()
    week_start = (today - datetime.timedelta(days=6)).isoformat()
    users = get_all_users()

    for uid in users:
        try:
            conn = get_conn()
            tasks_done  = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND done=1 AND date>=?",
                (uid, week_start)
            ).fetchone()[0]
            tasks_total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND date>=?",
                (uid, week_start)
            ).fetchone()[0]
            lecs_watched = 0  # Placeholder
            study_mins = conn.execute(
                "SELECT SUM(minutes) FROM study_log WHERE user_id=? AND date>=?",
                (uid, week_start)
            ).fetchone()[0] or 0
            streak = conn.execute("SELECT streak FROM users WHERE tg_id=?", (uid,)).fetchone()
            streak = streak["streak"] if streak else 0

            # Subject breakdown
            subj_rows = conn.execute(
                "SELECT subject, SUM(minutes) as mins FROM study_log WHERE user_id=? AND date>=? GROUP BY subject",
                (uid, week_start)
            ).fetchall()
            conn.close()

            subj_lines = ""
            for s in subj_rows:
                if s["subject"]:
                    subj_lines += f"  • {s['subject']}: {s['mins']} min\n"

            hrs   = study_mins // 60
            mins  = study_mins % 60
            pct   = round((tasks_done / tasks_total * 100) if tasks_total > 0 else 0)

            await app.bot.send_message(
                uid,
                f"📊 *Weekly Report*\n"
                f"_{week_start} → {today.isoformat()}_\n\n"
                f"{E['task']} Tasks: *{tasks_done}/{tasks_total}* ({pct}% done)\n"
                f"{E['timer']} Study time: *{hrs}h {mins}m*\n"
                f"{E['streak']} Current streak: *{streak} days*\n"
                + (f"\n*By subject:*\n{subj_lines}" if subj_lines else ""),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[Scheduler] Weekly report failed for {uid}: {e}")


# ── 4. Revision Due Alerts ─────────────────────────────────────
async def job_revision_alerts(app):
    today = datetime.date.today().isoformat()
    conn  = get_conn()
    items = conn.execute(
        "SELECT * FROM revision_schedule WHERE due_date=? AND done=0", (today,)
    ).fetchall()
    conn.close()

    seen = {}
    for r in items:
        uid = r["user_id"]
        if uid not in seen:
            seen[uid] = []
        seen[uid].append(r)

    for uid, revs in seen.items():
        try:
            lines = "\n".join(f"  • {r['topic']}" for r in revs)
            kb = Kb([[Btn(f"{E['revision']} Open Revisions", callback_data="revision_home")]])
            await app.bot.send_message(
                uid,
                f"{E['revision']} *Revision Due Today!*\n\n{lines}\n\n_Mark them done after revising._",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            print(f"[Scheduler] Revision alert failed for {uid}: {e}")


# ── 5. Formula Flash Card ──────────────────────────────────────
async def job_formula_flash(app):
    conn   = get_conn()
    rows   = conn.execute("SELECT * FROM formulas WHERE file_type='text' AND content!=''").fetchall()
    users  = get_all_users()
    conn.close()

    if not rows:
        return

    formula = random.choice(rows)
    for uid in users:
        try:
            kb = Kb([[Btn(f"{E['done']} Got it!", callback_data="noop"),
                      Btn(f"{E['formula']} Open Formulas", callback_data="formula_home")]])
            await app.bot.send_message(
                uid,
                f"{E['formula']} *Daily Formula Flash*\n\n"
                f"Chapter: *{formula['chapter']}* | Class {formula['class_num']}\n\n"
                f"{formula['content']}",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            print(f"[Scheduler] Formula flash failed for {uid}: {e}")
