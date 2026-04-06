"""
handlers/today.py — Tasks, Lectures, Pomodoro Timer
All inline-button driven. ConversationHandler for multi-step flows.
"""

import datetime
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from database import get_conn
from handlers.common import back_home_btn

# ── States ─────────────────────────────────────────────────────
(
    TODAY_HOME,
    TASK_ADD_TEXT, TASK_EDIT_TEXT, TASK_CONFIRM_DELETE,
    LEC_ADD_TITLE, LEC_ADD_LINK, LEC_ADD_SUBJECT,
    LEC_ADD_TIME, LEC_ADD_MSG,
    LEC_EDIT_CHOOSE, LEC_EDIT_FIELD, LEC_EDIT_VALUE,
    TIMER_CUSTOM,
) = range(13)


# ═══════════════════════════════════════════════════════════════
#  TODAY HOME
# ═══════════════════════════════════════════════════════════════
async def today_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    today = datetime.date.today().isoformat()

    conn = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id",
        (uid, today)
    ).fetchall()
    lecs = conn.execute(
        "SELECT * FROM lectures WHERE user_id=? AND active=1 ORDER BY alert_time",
        (uid,)
    ).fetchall()
    conn.close()

    done  = sum(1 for t in tasks if t["done"])
    total = len(tasks)
    today_str = datetime.date.today().strftime("%A, %d %B %Y")

    task_lines = ""
    for t in tasks:
        mark = "✅" if t["done"] else "⬜"
        task_lines += f"{mark} {t['text']}\n"
    if not task_lines:
        task_lines = "_Koi task nahi — add karo!_\n"

    lec_lines = ""
    for l in lecs:
        lec_lines += f"🔗 {l['alert_time']} — {l['title']}\n"
    if not lec_lines:
        lec_lines = "_Koi lecture nahi — add karo!_\n"

    text = (
        f"📅 *{today_str}*\n\n"
        f"*Tasks* ({done}/{total} done)\n{task_lines}\n"
        f"*Lectures*\n{lec_lines}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Task",    callback_data="task_add"),
         InlineKeyboardButton("✏️ Edit/Done",   callback_data="task_list")],
        [InlineKeyboardButton("📚 Add Lecture", callback_data="lec_add"),
         InlineKeyboardButton("🗂 Lectures",    callback_data="lec_list")],
        [InlineKeyboardButton("⏱ Timer",       callback_data="timer_menu")],
        [InlineKeyboardButton("🏠 Home",        callback_data="home")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return TODAY_HOME


# ═══════════════════════════════════════════════════════════════
#  TASKS
# ═══════════════════════════════════════════════════════════════
async def task_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="today_home")]])
    await query.edit_message_text(
        "📝 *Task kya hai?*\nType karo (subject prefix optional: `PHY:` `CHEM:` `MATH:`)",
        parse_mode="Markdown", reply_markup=kb
    )
    return TASK_ADD_TEXT


async def task_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    text  = update.message.text.strip()
    today = datetime.date.today().isoformat()

    # Parse subject prefix
    subject = ""
    for prefix in ["PHY:", "CHEM:", "MATH:", "BIO:"]:
        if text.upper().startswith(prefix):
            subject = prefix.rstrip(":")
            text = text[len(prefix):].strip()
            break

    conn = get_conn()
    conn.execute(
        "INSERT INTO tasks(user_id, text, subject, date) VALUES(?,?,?,?)",
        (uid, text, subject, today)
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aur add karo", callback_data="task_add"),
         InlineKeyboardButton("📅 Today",        callback_data="today_home")],
    ])
    await update.message.reply_text(
        f"✅ Task add ho gaya!\n*{text}*" + (f" [{subject}]" if subject else ""),
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def task_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    today = datetime.date.today().isoformat()

    conn  = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id",
        (uid, today)
    ).fetchall()
    conn.close()

    if not tasks:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📅 Back", callback_data="today_home")]])
        await query.edit_message_text("_Aaj koi task nahi hai._", parse_mode="Markdown", reply_markup=kb)
        return TODAY_HOME

    buttons = []
    for t in tasks:
        mark = "✅" if t["done"] else "⬜"
        buttons.append([InlineKeyboardButton(
            f"{mark} {t['text']}", callback_data=f"task_toggle_{t['id']}"
        )])
    buttons.append([
        InlineKeyboardButton("🗑 Delete task", callback_data="task_delete_menu"),
        InlineKeyboardButton("📅 Back",        callback_data="today_home"),
    ])

    await query.edit_message_text(
        "*Tasks — tap to toggle done/undone*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return TODAY_HOME


async def task_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    conn    = get_conn()
    task    = conn.execute("SELECT done FROM tasks WHERE id=?", (task_id,)).fetchone()
    new_done = 0 if task["done"] else 1
    conn.execute("UPDATE tasks SET done=? WHERE id=?", (new_done, task_id))
    conn.commit()
    conn.close()
    # Refresh list
    return await task_list(update, context)


async def task_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    today = datetime.date.today().isoformat()

    conn  = get_conn()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND date=? ORDER BY id",
        (uid, today)
    ).fetchall()
    conn.close()

    buttons = []
    for t in tasks:
        buttons.append([InlineKeyboardButton(
            f"🗑 {t['text']}", callback_data=f"task_del_confirm_{t['id']}"
        )])
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="task_list")])
    await query.edit_message_text(
        "*Kaun sa task delete karna hai?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return TODAY_HOME


async def task_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    context.user_data["del_task_id"] = task_id

    conn = get_conn()
    task = conn.execute("SELECT text FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Haan, delete karo", callback_data=f"task_del_yes_{task_id}"),
        InlineKeyboardButton("❌ Nahi",              callback_data="task_list"),
    ]])
    await query.edit_message_text(
        f"⚠️ *Sure ho?*\n\n_{task['text']}_\n\nEk baar delete hua toh wapas nahi aayega.",
        parse_mode="Markdown", reply_markup=kb
    )
    return TASK_CONFIRM_DELETE


async def task_del_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    conn    = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    await query.answer("Task delete ho gaya!", show_alert=False)
    return await task_list(update, context)


# ═══════════════════════════════════════════════════════════════
#  LECTURES
# ═══════════════════════════════════════════════════════════════
async def lec_add_ask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="today_home")]])
    await query.edit_message_text(
        "📚 *Lecture ka naam kya hai?*\n_Example: Wave Optics, Limits, SN1 SN2_",
        parse_mode="Markdown", reply_markup=kb
    )
    return LEC_ADD_TITLE


async def lec_add_got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec_title"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="today_home")]])
    await update.message.reply_text(
        "🔗 *Link bhejo*\n_YouTube, Unacademy, PDF, koi bhi link chalega_",
        parse_mode="Markdown", reply_markup=kb
    )
    return LEC_ADD_LINK


async def lec_add_got_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec_link"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("PHY", callback_data="lec_sub_PHY"),
         InlineKeyboardButton("CHEM", callback_data="lec_sub_CHEM"),
         InlineKeyboardButton("MATH", callback_data="lec_sub_MATH")],
        [InlineKeyboardButton("BIO", callback_data="lec_sub_BIO"),
         InlineKeyboardButton("Other", callback_data="lec_sub_OTHER")],
    ])
    await update.message.reply_text("📖 *Subject?*", parse_mode="Markdown", reply_markup=kb)
    return LEC_ADD_SUBJECT


async def lec_add_got_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lec_subject"] = query.data.replace("lec_sub_", "")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="today_home")]])
    await query.edit_message_text(
        "⏰ *Alert time? (HH:MM format)*\n_Example: 10:30 ya 14:00_",
        parse_mode="Markdown", reply_markup=kb
    )
    return LEC_ADD_TIME


async def lec_add_got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    # Validate time format
    try:
        datetime.datetime.strptime(time_text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Format galat hai! HH:MM mein likho, jaise `10:30`")
        return LEC_ADD_TIME
    context.user_data["lec_time"] = time_text
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Skip (koi message nahi)", callback_data="lec_msg_skip")]])
    await update.message.reply_text(
        "💬 *Koi custom message? (optional)*\n_Jo alert ke saath aayega_",
        parse_mode="Markdown", reply_markup=kb
    )
    return LEC_ADD_MSG


async def lec_add_got_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lec_msg"] = update.message.text.strip()
    return await _lec_save(update, context)


async def lec_msg_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lec_msg"] = ""
    return await _lec_save(update, context)


async def _lec_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d   = context.user_data
    conn = get_conn()
    conn.execute(
        "INSERT INTO lectures(user_id, title, link, subject, alert_time, message) VALUES(?,?,?,?,?,?)",
        (uid, d["lec_title"], d["lec_link"], d.get("lec_subject",""), d["lec_time"], d.get("lec_msg",""))
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Aur add karo", callback_data="lec_add"),
         InlineKeyboardButton("📅 Today",         callback_data="today_home")],
    ])
    msg_text = (
        f"✅ *Lecture add ho gaya!*\n\n"
        f"📌 {d['lec_title']}\n"
        f"⏰ Alert: {d['lec_time']}\n"
        f"📖 {d.get('lec_subject','')}"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(msg_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END


async def lec_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id

    conn  = get_conn()
    lecs  = conn.execute(
        "SELECT * FROM lectures WHERE user_id=? AND active=1 ORDER BY alert_time",
        (uid,)
    ).fetchall()
    conn.close()

    if not lecs:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Lecture", callback_data="lec_add")],
            [InlineKeyboardButton("📅 Back",        callback_data="today_home")],
        ])
        await query.edit_message_text("_Koi lecture nahi hai._", parse_mode="Markdown", reply_markup=kb)
        return TODAY_HOME

    buttons = []
    for l in lecs:
        buttons.append([InlineKeyboardButton(
            f"⏰{l['alert_time']} — {l['title']} [{l['subject']}]",
            callback_data=f"lec_view_{l['id']}"
        )])
    buttons.append([InlineKeyboardButton("📅 Back", callback_data="today_home")])
    await query.edit_message_text(
        "*Tumhare lectures* — tap karo edit/view karne ke liye",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return TODAY_HOME


async def lec_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    context.user_data["edit_lec_id"] = lec_id

    conn = get_conn()
    l    = conn.execute("SELECT * FROM lectures WHERE id=?", (lec_id,)).fetchone()
    conn.close()

    text = (
        f"📚 *{l['title']}*\n\n"
        f"🔗 Link: {l['link']}\n"
        f"📖 Subject: {l['subject']}\n"
        f"⏰ Alert: {l['alert_time']}\n"
        f"💬 Message: {l['message'] or '—'}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Title",   callback_data=f"ledit_title_{lec_id}"),
         InlineKeyboardButton("✏️ Edit Link",    callback_data=f"ledit_link_{lec_id}")],
        [InlineKeyboardButton("✏️ Edit Time",    callback_data=f"ledit_time_{lec_id}"),
         InlineKeyboardButton("✏️ Edit Message", callback_data=f"ledit_msg_{lec_id}")],
        [InlineKeyboardButton("🗑 Delete",        callback_data=f"lec_del_confirm_{lec_id}"),
         InlineKeyboardButton("◀️ Back",          callback_data="lec_list")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return LEC_EDIT_CHOOSE


async def lec_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")   # ledit_title_5
    field  = parts[1]
    lec_id = int(parts[2])
    context.user_data["edit_lec_id"]    = lec_id
    context.user_data["edit_lec_field"] = field

    prompts = {
        "title": "📌 Naya title kya hoga?",
        "link":  "🔗 Naya link bhejo",
        "time":  "⏰ Naya alert time? (HH:MM)",
        "msg":   "💬 Naya message kya hoga?",
    }
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"lec_view_{lec_id}")]])
    await query.edit_message_text(prompts.get(field, "?"), parse_mode="Markdown", reply_markup=kb)
    return LEC_EDIT_VALUE


async def lec_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val    = update.message.text.strip()
    field  = context.user_data.get("edit_lec_field")
    lec_id = context.user_data.get("edit_lec_id")

    col_map = {"title": "title", "link": "link", "time": "alert_time", "msg": "message"}
    col = col_map.get(field, "title")

    conn = get_conn()
    conn.execute(f"UPDATE lectures SET {col}=? WHERE id=?", (val, lec_id))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to lecture", callback_data=f"lec_view_{lec_id}")]])
    await update.message.reply_text("✅ Update ho gaya!", reply_markup=kb)
    return ConversationHandler.END


async def lec_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    context.user_data["del_lec_id"] = lec_id

    conn = get_conn()
    l    = conn.execute("SELECT title FROM lectures WHERE id=?", (lec_id,)).fetchone()
    conn.close()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Haan, delete", callback_data=f"lec_del_yes_{lec_id}"),
        InlineKeyboardButton("❌ Nahi",          callback_data=f"lec_view_{lec_id}"),
    ]])
    await query.edit_message_text(
        f"⚠️ *Sure ho?*\n\n_{l['title']}_\n\nEk baar delete hua toh wapas nahi aayega.",
        parse_mode="Markdown", reply_markup=kb
    )
    return LEC_EDIT_CHOOSE


async def lec_del_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lec_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    conn.execute("DELETE FROM lectures WHERE id=?", (lec_id,))
    conn.commit()
    conn.close()
    await query.answer("Lecture delete ho gaya!", show_alert=False)
    return await lec_list(update, context)


# ═══════════════════════════════════════════════════════════════
#  TIMER
# ═══════════════════════════════════════════════════════════════
async def timer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("25 min (Pomodoro)", callback_data="timer_25"),
         InlineKeyboardButton("50 min (Deep)",     callback_data="timer_50")],
        [InlineKeyboardButton("15 min (Quick)",    callback_data="timer_15"),
         InlineKeyboardButton("Custom ⌨️",         callback_data="timer_custom")],
        [InlineKeyboardButton("◀️ Back",            callback_data="today_home")],
    ])
    await query.edit_message_text("⏱ *Timer — kitne minute?*", parse_mode="Markdown", reply_markup=kb)
    return TIMER_CUSTOM


async def timer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    minutes = int(query.data.split("_")[-1])
    return await _run_timer(update, context, minutes)


async def timer_custom_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="timer_menu")]])
    await query.edit_message_text("⌨️ *Kitne minute?* (Number type karo)", parse_mode="Markdown", reply_markup=kb)
    return TIMER_CUSTOM


async def timer_custom_got(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(update.message.text.strip())
        if minutes < 1 or minutes > 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valid number do (1–300 minute)")
        return TIMER_CUSTOM
    return await _run_timer(update, context, minutes)


async def _run_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, minutes: int):
    uid = update.effective_user.id
    import asyncio

    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"⏱ *Timer start!*\n\n*{minutes} minute* — concentrate karo!\n\n_Timer khatam hone par alert aayega._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📅 Today", callback_data="today_home")]])
        )
        bot = update.callback_query.get_bot()
        chat_id = update.callback_query.message.chat_id
    else:
        await update.message.reply_text(
            f"⏱ *{minutes} min timer start!*", parse_mode="Markdown"
        )
        bot = update.message.get_bot()
        chat_id = update.message.chat_id

    async def fire():
        await asyncio.sleep(minutes * 60)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Phir se", callback_data=f"timer_{minutes}"),
             InlineKeyboardButton("5 min break", callback_data="timer_5")],
            [InlineKeyboardButton("📅 Today", callback_data="today_home")],
        ])
        await bot.send_message(
            chat_id,
            f"⏰ *Timer done!*\n\n*{minutes} minute* poore ho gaye!\nShabaash — ek aur pomodoro? 💪",
            parse_mode="Markdown",
            reply_markup=kb
        )

    asyncio.create_task(fire())
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  CONVERSATION HANDLER
# ═══════════════════════════════════════════════════════════════
def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(today_home, pattern="^today_home$")],
        states={
            TODAY_HOME: [
                CallbackQueryHandler(task_add_ask,      pattern="^task_add$"),
                CallbackQueryHandler(task_list,         pattern="^task_list$"),
                CallbackQueryHandler(task_toggle,       pattern="^task_toggle_"),
                CallbackQueryHandler(task_delete_menu,  pattern="^task_delete_menu$"),
                CallbackQueryHandler(task_del_confirm,  pattern="^task_del_confirm_"),
                CallbackQueryHandler(task_del_yes,      pattern="^task_del_yes_"),
                CallbackQueryHandler(lec_add_ask_title, pattern="^lec_add$"),
                CallbackQueryHandler(lec_list,          pattern="^lec_list$"),
                CallbackQueryHandler(lec_view,          pattern="^lec_view_"),
                CallbackQueryHandler(lec_del_confirm,   pattern="^lec_del_confirm_"),
                CallbackQueryHandler(lec_del_yes,       pattern="^lec_del_yes_"),
                CallbackQueryHandler(timer_menu,        pattern="^timer_menu$"),
                CallbackQueryHandler(timer_start,       pattern="^timer_(25|50|15|5)$"),
                CallbackQueryHandler(timer_custom_ask,  pattern="^timer_custom$"),
            ],
            TASK_ADD_TEXT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, task_add_save)],
            TASK_CONFIRM_DELETE:[
                CallbackQueryHandler(task_del_yes,  pattern="^task_del_yes_"),
                CallbackQueryHandler(task_list,     pattern="^task_list$"),
            ],
            LEC_ADD_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, lec_add_got_title)],
            LEC_ADD_LINK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, lec_add_got_link)],
            LEC_ADD_SUBJECT: [CallbackQueryHandler(lec_add_got_subject, pattern="^lec_sub_")],
            LEC_ADD_TIME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, lec_add_got_time)],
            LEC_ADD_MSG:     [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lec_add_got_msg),
                CallbackQueryHandler(lec_msg_skip, pattern="^lec_msg_skip$"),
            ],
            LEC_EDIT_CHOOSE: [
                CallbackQueryHandler(lec_edit_field,   pattern="^ledit_"),
                CallbackQueryHandler(lec_del_confirm,  pattern="^lec_del_confirm_"),
                CallbackQueryHandler(lec_del_yes,      pattern="^lec_del_yes_"),
                CallbackQueryHandler(lec_list,         pattern="^lec_list$"),
                CallbackQueryHandler(lec_view,         pattern="^lec_view_"),
            ],
            LEC_EDIT_VALUE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, lec_edit_save)],
            TIMER_CUSTOM:    [
                CallbackQueryHandler(timer_start,      pattern="^timer_(25|50|15|5)$"),
                CallbackQueryHandler(timer_custom_ask, pattern="^timer_custom$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, timer_custom_got),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(today_home, pattern="^today_home$"),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
