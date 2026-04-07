"""
handlers/today.py
Today section: Tasks, Lectures, Focus Timer, Test Scores, Doubts, Revision
All inline-button driven. Cancel buttons fully working.
"""

import datetime
import asyncio
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn, update_streak
from ui import E, cancel_btn, back_btn, confirm_delete_kb, subject_kb, timer_kb, today_home_kb, DIVIDER
from handlers.common import check_banned

# ── States ─────────────────────────────────────────────────────
(
    S_TODAY_HOME,
    S_TASK_TEXT, S_TASK_DEL_CONFIRM,
    S_LEC_TITLE, S_LEC_LINK, S_LEC_SUBJ, S_LEC_TIME, S_LEC_MSG,
    S_LEC_EDIT_VAL,
    S_TIMER_CUSTOM,
    S_SCORE_NAME, S_SCORE_PHY, S_SCORE_CHEM, S_SCORE_MATH,
    S_DOUBT_TEXT, S_DOUBT_SUBJ,
) = range(16)


# ── Helper ─────────────────────────────────────────────────────
def _today() -> str:
    return datetime.date.today().isoformat()

def _today_display() -> str:
    return datetime.date.today().strftime("%A, %d %B %Y")


# ═══════════════════════════════════════════════════════════════
#  TODAY HOME
# ═══════════════════════════════════════════════════════════════
async def today_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    conn  = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id", (uid, _today())
    ).fetchall()
    lecs  = conn.execute(
        "SELECT * FROM lectures WHERE user_id=? AND active=1 ORDER BY alert_time", (uid,)
    ).fetchall()
    revisions = conn.execute(
        "SELECT COUNT(*) FROM revision_schedule WHERE user_id=? AND due_date<=? AND done=0",
        (uid, _today())
    ).fetchone()[0]
    doubts = conn.execute(
        "SELECT COUNT(*) FROM doubts WHERE user_id=? AND resolved=0", (uid,)
    ).fetchone()[0]
    conn.close()

    done  = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    task_lines = ""
    for t in tasks:
        mark = E["done"] if t["done"] else E["undone"]
        subj = f" `{t['subject']}`" if t["subject"] else ""
        task_lines += f"{mark}{subj} {t['text']}\n"
    task_block = task_lines.strip() or "_No tasks yet — add one!_"

    lec_lines = ""
    for l in lecs:
        subj = f"[{l['subject']}] " if l["subject"] else ""
        lec_lines += f"{E['clock']} `{l['alert_time']}` {subj}{l['title']}\n"
    lec_block = lec_lines.strip() or "_No lectures scheduled._"

    alerts = []
    if revisions > 0: alerts.append(f"{E['revision']} {revisions} revision(s) due today")
    if doubts   > 0: alerts.append(f"{E['doubt']} {doubts} unresolved doubt(s)")
    alert_block = "\n".join(alerts)

    text = (
        f"{E['calendar']} *{_today_display()}*\n"
        f"{DIVIDER}\n"
        f"{E['task']} *Tasks* — {done}/{total} done\n"
        f"{task_block}\n\n"
        f"{E['lecture']} *Lectures*\n"
        f"{lec_block}"
        + (f"\n\n{alert_block}" if alert_block else "")
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=today_home_kb())
    return S_TODAY_HOME


# ═══════════════════════════════════════════════════════════════
#  TASKS
# ═══════════════════════════════════════════════════════════════
async def task_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['task']} *Add Task*\n\n"
        "Type your task. Optionally prefix with subject:\n"
        "`PHY:` `CHEM:` `MATH:`\n\n"
        "_Example: PHY: Solve HC Verma Ch.5_",
        parse_mode="Markdown",
        reply_markup=cancel_btn("today_home")
    )
    return S_TASK_TEXT


async def task_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    subj = ""
    for p in ["PHY:", "CHEM:", "MATH:", "BIO:"]:
        if text.upper().startswith(p):
            subj = p.rstrip(":")
            text = text[len(p):].strip()
            break

    conn = get_conn()
    conn.execute(
        "INSERT INTO tasks(user_id, text, subject, date) VALUES(?,?,?,?)",
        (uid, text, subj, _today())
    )
    conn.commit()
    conn.close()

    kb = Kb([
        [Btn(f"{E['add']} Add another", callback_data="task_add"),
         Btn(f"{E['task']} Today",       callback_data="today_home")],
    ])
    badge = f" `{subj}`" if subj else ""
    await update.message.reply_text(
        f"{E['done']} Task added!\n{badge} *{text}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def task_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    conn  = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id", (uid, _today())
    ).fetchall()
    conn.close()

    if not tasks:
        await query.edit_message_text(
            f"{E['task']} *No tasks today.*\nAdd your first task!",
            parse_mode="Markdown",
            reply_markup=Kb([[Btn(f"{E['add']} Add Task", callback_data="task_add")], back_btn("today_home")[0]])
        )
        return S_TODAY_HOME

    rows = []
    for t in tasks:
        mark = E["done"] if t["done"] else E["undone"]
        subj = f"[{t['subject']}] " if t["subject"] else ""
        rows.append([Btn(f"{mark} {subj}{t['text']}", callback_data=f"task_tog_{t['id']}")])
    rows.append([Btn(f"{E['delete']} Delete a task", callback_data="task_del_menu")])
    rows.append(back_btn("today_home")[0])

    await query.edit_message_text(
        f"{E['task']} *Today's Tasks*\nTap to toggle done/undone",
        parse_mode="Markdown",
        reply_markup=Kb(rows)
    )
    return S_TODAY_HOME


async def task_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    uid     = query.from_user.id
    conn    = get_conn()
    task    = conn.execute("SELECT done FROM tasks WHERE id=?", (task_id,)).fetchone()
    new_val = 0 if task["done"] else 1
    conn.execute("UPDATE tasks SET done=? WHERE id=?", (new_val, task_id))
    conn.commit()
    conn.close()
    if new_val == 1:
        update_streak(uid)
    return await task_list(update, context)


async def task_del_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    conn  = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id", (uid, _today())
    ).fetchall()
    conn.close()
    rows = []
    for t in tasks:
        rows.append([Btn(f"{E['delete']} {t['text']}", callback_data=f"task_delconf_{t['id']}")])
    rows.append(back_btn("task_list")[0])
    await query.edit_message_text(
        f"{E['delete']} *Delete which task?*",
        parse_mode="Markdown", reply_markup=Kb(rows)
    )
    return S_TASK_DEL_CONFIRM


async def task_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    conn    = get_conn()
    t       = conn.execute("SELECT text FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    await query.edit_message_text(
        f"{E['warn']} *Confirm Delete?*\n\n_{t['text']}_\n\nThis cannot be undone.",
        parse_mode="Markdown",
        reply_markup=confirm_delete_kb(f"task_delyes_{task_id}", "task_list")
    )
    return S_TASK_DEL_CONFIRM


async def task_del_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    conn    = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    await query.answer("Task deleted.", show_alert=False)
    return await task_list(update, context)


# ═══════════════════════════════════════════════════════════════
#  LECTURES
# ═══════════════════════════════════════════════════════════════
async def lec_add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['lecture']} *Add Lecture — Step 1/4*\n\nEnter lecture title:",
        parse_mode="Markdown", reply_markup=cancel_btn("today_home")
    )
    return S_LEC_TITLE


async def lec_got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec"] = {"title": update.message.text.strip()}
    await update.message.reply_text(
        f"{E['link']} *Step 2/4 — Paste the link*\n_(YouTube, Unacademy, PDF, any link)_",
        parse_mode="Markdown", reply_markup=cancel_btn("today_home")
    )
    return S_LEC_LINK


async def lec_got_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec"]["link"] = update.message.text.strip()
    await update.message.reply_text(
        f"{E['task']} *Step 3/4 — Select subject*",
        parse_mode="Markdown", reply_markup=subject_kb("lec_subj")
    )
    return S_LEC_SUBJ


async def lec_got_subj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lec"]["subject"] = query.data.replace("lec_subj_", "")
    await query.edit_message_text(
        f"{E['clock']} *Step 4/4 — Alert time (HH:MM)*\n_Example: 10:30 or 14:00_",
        parse_mode="Markdown", reply_markup=cancel_btn("today_home")
    )
    return S_LEC_TIME


async def lec_got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    try:
        datetime.datetime.strptime(t, "%H:%M")
    except ValueError:
        await update.message.reply_text(f"{E['warn']} Wrong format! Use HH:MM like `10:30`")
        return S_LEC_TIME
    context.user_data["lec"]["time"] = t
    kb = Kb([[Btn("Skip (no message)", callback_data="lec_msg_skip")]])
    await update.message.reply_text(
        f"💬 *Custom alert message? (optional)*\n_Shown with the alert_",
        parse_mode="Markdown", reply_markup=kb
    )
    return S_LEC_MSG


async def lec_got_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec"]["message"] = update.message.text.strip()
    return await _lec_save(update, context)


async def lec_msg_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lec"]["message"] = ""
    return await _lec_save(update, context)


async def _lec_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d   = context.user_data["lec"]
    conn = get_conn()
    conn.execute(
        "INSERT INTO lectures(user_id,title,link,subject,alert_time,message) VALUES(?,?,?,?,?,?)",
        (uid, d["title"], d["link"], d.get("subject",""), d["time"], d.get("message",""))
    )
    conn.commit()
    conn.close()
    kb = Kb([
        [Btn(f"{E['add']} Add another", callback_data="lec_add"),
         Btn(f"{E['task']} Today",      callback_data="today_home")],
    ])
    text = (
        f"{E['done']} *Lecture added!*\n\n"
        f"{E['lecture']} *{d['title']}*\n"
        f"{E['clock']} Alert: `{d['time']}`\n"
        f"Subject: `{d.get('subject','—')}`"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END


async def lec_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    conn = get_conn()
    lecs = conn.execute(
        "SELECT * FROM lectures WHERE user_id=? AND active=1 ORDER BY alert_time", (uid,)
    ).fetchall()
    conn.close()

    if not lecs:
        await query.edit_message_text(
            f"{E['lecture']} *No lectures yet.*",
            parse_mode="Markdown",
            reply_markup=Kb([[Btn(f"{E['add']} Add Lecture", callback_data="lec_add")], back_btn("today_home")[0]])
        )
        return S_TODAY_HOME

    rows = []
    for l in lecs:
        subj = f"[{l['subject']}] " if l["subject"] else ""
        rows.append([Btn(f"{E['clock']}{l['alert_time']} — {subj}{l['title']}", callback_data=f"lec_view_{l['id']}")])
    rows.append(back_btn("today_home")[0])
    await query.edit_message_text(
        f"{E['lecture']} *Lectures* — tap to edit",
        parse_mode="Markdown", reply_markup=Kb(rows)
    )
    return S_TODAY_HOME


async def lec_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    l      = conn.execute("SELECT * FROM lectures WHERE id=?", (lec_id,)).fetchone()
    conn.close()

    text = (
        f"{E['lecture']} *{l['title']}*\n"
        f"{DIVIDER}\n"
        f"{E['link']} Link: {l['link']}\n"
        f"Subject: `{l['subject'] or '—'}`\n"
        f"{E['clock']} Alert: `{l['alert_time']}`\n"
        f"💬 Message: _{l['message'] or '—'}_"
    )
    kb = Kb([
        [Btn(f"{E['edit']} Title",   callback_data=f"ledit_title_{lec_id}"),
         Btn(f"{E['edit']} Link",    callback_data=f"ledit_link_{lec_id}")],
        [Btn(f"{E['edit']} Time",    callback_data=f"ledit_time_{lec_id}"),
         Btn(f"{E['edit']} Message", callback_data=f"ledit_msg_{lec_id}")],
        [Btn(f"{E['delete']} Delete", callback_data=f"lec_delconf_{lec_id}"),
         Btn(f"{E['back']} Back",     callback_data="lec_list")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return S_LEC_EDIT_VAL


async def lec_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")   # ledit_title_5
    field  = parts[1]
    lec_id = int(parts[2])
    context.user_data["elec_id"]    = lec_id
    context.user_data["elec_field"] = field
    prompts = {
        "title": "Enter new title:",
        "link":  "Paste new link:",
        "time":  "Enter new time (HH:MM):",
        "msg":   "Enter new message:",
    }
    await query.edit_message_text(
        f"{E['edit']} *Edit {field.title()}*\n\n{prompts.get(field,'?')}",
        parse_mode="Markdown",
        reply_markup=cancel_btn(f"lec_view_{lec_id}")
    )
    return S_LEC_EDIT_VAL


async def lec_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val    = update.message.text.strip()
    field  = context.user_data.get("elec_field")
    lec_id = context.user_data.get("elec_id")
    cols   = {"title":"title","link":"link","time":"alert_time","msg":"message"}
    col    = cols.get(field,"title")
    conn   = get_conn()
    conn.execute(f"UPDATE lectures SET {col}=? WHERE id=?", (val, lec_id))
    conn.commit()
    conn.close()
    kb = Kb([[Btn(f"{E['back']} Back to lecture", callback_data=f"lec_view_{lec_id}")]])
    await update.message.reply_text(f"{E['done']} Updated!", reply_markup=kb)
    return ConversationHandler.END


async def lec_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    l      = conn.execute("SELECT title FROM lectures WHERE id=?", (lec_id,)).fetchone()
    conn.close()
    await query.edit_message_text(
        f"{E['warn']} *Confirm Delete?*\n\n_{l['title']}_\n\nThis cannot be undone.",
        parse_mode="Markdown",
        reply_markup=confirm_delete_kb(f"lec_delyes_{lec_id}", f"lec_view_{lec_id}")
    )
    return S_LEC_EDIT_VAL


async def lec_del_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    conn.execute("DELETE FROM lectures WHERE id=?", (lec_id,))
    conn.commit()
    conn.close()
    await query.answer("Lecture deleted.", show_alert=False)
    return await lec_list(update, context)


async def lec_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer(f"{E['done']} Marked as watched!", show_alert=False)
    lec_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    l      = conn.execute("SELECT * FROM lectures WHERE id=?", (lec_id,)).fetchone()
    conn.close()
    if l:
        # Schedule revision reminders: 1d, 3d, 7d, 30d
        import datetime as dt
        today  = dt.date.today()
        uid    = query.from_user.id
        conn   = get_conn()
        for days in [1, 3, 7, 30]:
            due = (today + dt.timedelta(days=days)).isoformat()
            conn.execute(
                "INSERT INTO revision_schedule(user_id, lecture_id, topic, due_date) VALUES(?,?,?,?)",
                (uid, lec_id, l["title"], due)
            )
        conn.commit()
        conn.close()
        await query.edit_message_reply_markup(reply_markup=None)


async def lec_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Reminder set for 15 minutes!", show_alert=True)
    lec_id = int(query.data.split("_")[-1])

    async def remind():
        await asyncio.sleep(15 * 60)
        conn = get_conn()
        l    = conn.execute("SELECT * FROM lectures WHERE id=?", (lec_id,)).fetchone()
        conn.close()
        if l:
            kb = Kb([[Btn(f"{E['link']} Open Link", url=l["link"])]])
            await context.bot.send_message(
                query.from_user.id,
                f"{E['clock']} *Snooze reminder!*\n\n{E['lecture']} *{l['title']}*",
                parse_mode="Markdown", reply_markup=kb
            )
    asyncio.create_task(remind())


# ═══════════════════════════════════════════════════════════════
#  TIMER
# ═══════════════════════════════════════════════════════════════
async def timer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['timer']} *Focus Timer*\nSelect duration:",
        parse_mode="Markdown", reply_markup=timer_kb()
    )
    return S_TIMER_CUSTOM


async def timer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    minutes = int(query.data.split("_")[-1])
    return await _run_timer(query, context, minutes)


async def timer_custom_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['timer']} Enter minutes (1–300):",
        reply_markup=cancel_btn("timer_menu")
    )
    return S_TIMER_CUSTOM


async def timer_custom_got(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        m = int(update.message.text.strip())
        if not 1 <= m <= 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text(f"{E['warn']} Enter a number between 1 and 300.")
        return S_TIMER_CUSTOM
    uid = update.effective_user.id
    chat_id = update.message.chat_id
    bot = update.message.get_bot()
    await update.message.reply_text(
        f"{E['timer']} *{m}-minute timer started!*\nFocus up {E['star']}",
        parse_mode="Markdown",
        reply_markup=Kb([[Btn(f"{E['task']} Today", callback_data="today_home")]])
    )
    asyn
