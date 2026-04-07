"""
handlers/memories.py
Sections: Silly | Error | Important | Daily Report (daily journal)
- All cancel buttons working
- Ek ek karke navigation (Next/Prev)
- Text + Image support everywhere
- /search integration
"""

from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn
from ui import E, cancel_btn, back_btn, confirm_delete_kb, nav_kb, mem_home_kb, DIVIDER
from handlers.common import check_banned
import datetime

# ── States ─────────────────────────────────────────────────────
(
    S_MEM_HOME,
    S_ADD_TITLE, S_ADD_CONTENT, S_ADD_ANSWER, S_ADD_KEYPOINTS,
    S_REPORT_DATE, S_REPORT_CONTENT,
    S_VIEW,
) = range(8)

LABELS = {
    "silly":     (f"{E['silly']} Silly",     "Careless mistakes you want to remember"),
    "error":     (f"{E['error']} Error",     "Wrong questions from practice"),
    "important": (f"{E['imp']} Important",   "Important questions to revisit"),
}


# ═══════════════════════════════════════════════════════════════
#  HOME
# ═══════════════════════════════════════════════════════════════
async def mem_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    conn = get_conn()
    counts = {}
    for t in ["silly", "error", "important"]:
        counts[t] = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id=? AND mem_type=?", (uid, t)
        ).fetchone()[0]
    reports = conn.execute(
        "SELECT COUNT(*) FROM daily_reports WHERE user_id=?", (uid,)
    ).fetchone()[0]
    conn.close()

    text = (
        f"{E['memory']} *Memories*\n"
        f"{DIVIDER}\n"
        f"{E['silly']} Silly mistakes: *{counts['silly']}*\n"
        f"{E['error']} Error log: *{counts['error']}*\n"
        f"{E['imp']} Important: *{counts['important']}*\n"
        f"{E['report']} Daily reports: *{reports}*\n\n"
        f"_Tip: Use `/search <title>` to find anything instantly_"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=mem_home_kb())
    return S_MEM_HOME


async def mem_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    mem_type = query.data.replace("mem_", "").replace("_home", "")
    context.user_data["mem_type"] = mem_type
    label, desc = LABELS[mem_type]
    uid  = query.from_user.id
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE user_id=? AND mem_type=?", (uid, mem_type)
    ).fetchone()[0]
    conn.close()
    kb = Kb([
        [Btn(f"{E['add']} Add", callback_data=f"mem_add_{mem_type}"),
         Btn(f"{E['see']} See all ({count})", callback_data=f"mem_see_{mem_type}_0")],
        back_btn("mem_home")[0],
    ])
    await query.edit_message_text(
        f"{label}\n_{desc}_\n\nTotal saved: *{count}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return S_MEM_HOME


# ═══════════════════════════════════════════════════════════════
#  ADD FLOW
# ═══════════════════════════════════════════════════════════════
async def mem_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    mem_type = query.data.replace("mem_add_", "")
    context.user_data["mem_type"]    = mem_type
    context.user_data["mem_data"]    = {}
    await query.edit_message_text(
        f"{E['add']} *Add Entry*\n\n"
        "Enter a short *title* for this entry.\n"
        "_Used for search later — keep it simple_\n"
        "_Example: q1, silly-sin-cos, optics-doubt_",
        parse_mode="Markdown",
        reply_markup=cancel_btn(f"mem_{mem_type}_home")
    )
    return S_ADD_TITLE


async def mem_got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mem_data"]["title"] = update.message.text.strip()
    mem_type = context.user_data["mem_type"]

    if mem_type == "silly":
        prompt = f"{E['silly']} *What was the silly mistake?*\nSend text or an image"
    else:
        prompt = f"{E['error'] if mem_type=='error' else E['imp']} *Send the question*\nText or image — both work"

    await update.message.reply_text(
        prompt, parse_mode="Markdown",
        reply_markup=cancel_btn(f"mem_{mem_type}_home")
    )
    return S_ADD_CONTENT


async def mem_got_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["mem_data"]
    if update.message.photo:
        d["file_id"], d["file_type"], d["content"] = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        d["file_id"], d["file_type"], d["content"] = update.message.document.file_id, "document", update.message.caption or ""
    else:
        d["file_id"], d["file_type"], d["content"] = "", "", update.message.text.strip()

    if context.user_data["mem_type"] == "silly":
        return await _mem_save(update, context)

    await update.message.reply_text(
        f"✅ *Answer?*\nText or image",
        parse_mode="Markdown",
        reply_markup=Kb([[Btn("Skip", callback_data="mem_ans_skip")]])
    )
    return S_ADD_ANSWER


async def mem_got_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["mem_data"]
    if update.message.photo:
        d["ans_file"], d["ans_ftype"], d["answer"] = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        d["ans_file"], d["ans_ftype"], d["answer"] = update.message.document.file_id, "document", update.message.caption or ""
    else:
        d["ans_file"], d["ans_ftype"], d["answer"] = "", "", update.message.text.strip()

    await update.message.reply_text(
        f"{E['imp']} *Key points?* _(optional)_\nBullet points format",
        parse_mode="Markdown",
        reply_markup=Kb([[Btn("Skip", callback_data="mem_kp_skip")]])
    )
    return S_ADD_KEYPOINTS


async def mem_ans_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data["mem_data"]
    d["ans_file"], d["ans_ftype"], d["answer"] = "", "", ""
    await query.edit_message_text(
        f"{E['imp']} *Key points?* _(optional)_",
        parse_mode="Markdown",
        reply_markup=Kb([[Btn("Skip", callback_data="mem_kp_skip")]])
    )
    return S_ADD_KEYPOINTS


async def mem_got_keypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mem_data"]["keypoints"] = update.message.text.strip()
    return await _mem_save(update, context)


async def mem_kp_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mem_data"]["keypoints"] = ""
    return await _mem_save(update, context)


async def _mem_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid      = update.effective_user.id
    mt       = context.user_data["mem_type"]
    d        = context.user_data["mem_data"]
    conn     = get_conn()
    conn.execute("""
        INSERT INTO memories(user_id,mem_type,title,content,file_id,file_type,answer,ans_file,ans_ftype,keypoints)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        uid, mt, d.get("title",""), d.get("content",""),
        d.get("file_id",""), d.get("file_type",""),
        d.get("answer",""), d.get("ans_file",""), d.get("ans_ftype",""),
        d.get("keypoints","")
    ))
    conn.commit()
    conn.close()

    label = LABELS[mt][0]
    kb = Kb([
        [Btn(f"{E['add']} Add another", callback_data=f"mem_add_{mt}"),
         Btn(f"{E['see']} See all",     callback_data=f"mem_see_{mt}_0")],
        back_btn("mem_home")[0],
    ])
    text = f"{E['done']} Saved to *{label}*\n📌 Title: `{d.get('title','')}`"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  SEE — ek ek karke
# ═══════════════════════════════════════════════════════════════
async def mem_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts    = query.data.split("_")   # mem_see_silly_0
    mt       = parts[2]
    idx      = int(parts[3])
    uid      = query.from_user.id

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM memories WHERE user_id=? AND mem_type=? ORDER BY created DESC", (uid, mt)
    ).fetchall()
    conn.close()

    if not entries:
        await query.edit_message_text(
            f"_No entries yet in {LABELS[mt][0]}._",
            parse_mode="Markdown",
            reply_markup=Kb([
                [Btn(f"{E['add']} Add first entry", callback_data=f"mem_add_{mt}")],
                back_btn("mem_home")[0],
            ])
        )
        return S_VIEW

    total = len(entries)
    idx   = max(0, min(idx, total - 1))
    e     = entries[idx]

    # Nav row
    nav = []
    if idx > 0:         nav.append(Btn(f"{E['back']} Prev", callback_data=f"mem_see_{mt}_{idx-1}"))
    nav.append(Btn(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1: nav.append(Btn(f"Next {E['next']}", callback_data=f"mem_see_{mt}_{idx+1}"))

    extra = []
    if mt in ("error","important") and (e["answer"] or e["ans_file"] or e["keypoints"]):
        extra = [[Btn(f"💡 Answer & Key Points", callback_data=f"mem_ans_{e['id']}")]]

    del_row = [[Btn(f"{E['delete']} Delete this", callback_data=f"mem_del_{e['id']}_{mt}_{idx}"),
                Btn(f"{E['back']} Back",          callback_data=f"mem_{mt}_home")]]

    kb  = Kb([nav] + extra + del_row)
    hdr = f"{LABELS[mt][0]} — {idx+1}/{total}\n📌 *{e['title']}*\n_{e['created'][:10]}_"
    body = f"{hdr}\n\n{e['content']}" if e["content"] else hdr

    if e["file_id"]:
        try: await query.message.delete()
        except: pass
        send = query.message.chat.send_photo if e["file_type"] == "photo" else query.message.chat.send_document
        await send(e["file_id"], caption=body, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(body, parse_mode="Markdown", reply_markup=kb)
    return S_VIEW


async def mem_show_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    mem_id = int(query.data.split("_")[-1])
    conn   = get_conn()
    e      = conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
    conn.close()

    label = LABELS.get(e["mem_type"], ("?",""))[0]
    text  = f"{label} — *{e['title']}*\n{DIVIDER}\n"
    if e["answer"]:
        text += f"✅ *Answer:*\n{e['answer']}\n\n"
    if e["keypoints"]:
        text += f"{E['imp']} *Key Points:*\n{e['keypoints']}"
    if not e["answer"] and not e["keypoints"]:
        text += "_No answer or key points saved._"

    mt  = e["mem_type"]
    kb  = Kb([[Btn(f"{E['back']} Back", callback_data=f"mem_see_{mt}_0")]])

    if e["ans_file"]:
        try: await query.message.delete()
        except: pass
        send = query.message.chat.send_photo if e["ans_ftype"] == "photo" else query.message.chat.send_document
        await send(e["ans_file"], caption=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return S_VIEW


async def mem_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")  # mem_del_id_mt_idx
    mem_id = int(parts[2])
    mt     = parts[3]
    idx    = int(parts[4])
    conn   = get_conn()
    e      = conn.execute("SELECT title FROM memories WHERE id=?", (mem_id,)).fetchone()
    conn.close()
    await query.edit_message_text(
        f"{E['warn']} *Delete this entry?*\n\n📌 _{e['title']}_\n\nThis cannot be undone.",
        parse_mode="Markdown",
        reply_markup=confirm_delete_kb(f"mem_delyes_{mem_id}_{mt}", f"mem_see_{mt}_{idx}")
    )
    return S_VIEW


async def mem_del_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")  # mem_delyes_id_mt
    mem_id = int(parts[2])
    mt     = parts[3]
    conn   = get_conn()
    conn.execute("DELETE FROM memories WHERE id=?", (mem_id,))
    conn.commit()
    conn.close()
    # Redirect to see from beginning
    query.data = f"mem_see_{mt}_0"
    return await mem_see(update, context)


# ═══════════════════════════════════════════════════════════════
#  DAILY REPORT
# ═══════════════════════════════════════════════════════════════
async def report_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    today = datetime.date.today().isoformat()
    conn  = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM daily_reports WHERE user_id=?", (uid,)).fetchone()[0]
    today_exists = conn.execute(
        "SELECT id FROM daily_reports WHERE user_id=? AND date=?", (uid, today)
    ).fetchone()
    conn.close()

    kb_rows = []
    if today_exists:
        kb_rows.append([Btn(f"{E['see']} See today's report", callback_data="report_see_0")])
    else:
        kb_rows.append([Btn(f"{E['add']} Write today's report", callback_data="report_add_today")])
    kb_rows.append([Btn(f"{E['see']} Browse all reports ({count})", callback_data="report_see_0")])
    kb_rows.append(back_btn("mem_home")[0])

    await query.edit_message_text(
        f"{E['report']} *Daily Log*\n\nWrite what you did today — your personal diary.\nTotal entries: *{count}*\n\n"
        f"_Tip: `/search <date>` to find any day's report_",
        parse_mode="Markdown",
        reply_markup=Kb(kb_rows)
    )
    return S_MEM_HOME


async def report_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = datetime.date.today().strftime("%A, %d %B %Y")
    context.user_data["report_date"] = datetime.date.today().isoformat()
    await query.edit_message_text(
        f"{E['report']} *Daily Log — {today}*\n\nWrite what you did today.\nText or image — both work:",
        parse_mode="Markdown",
        reply_markup=cancel_btn("mem_report_home")
    )
    return S_REPORT_CONTENT


async def report_got_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    date = context.user_data.get("report_date", datetime.date.today().isoformat())

    if update.message.photo:
        file_id, ftype, content = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        file_id, ftype, content = update.message.document.file_id, "document", update.message.caption or ""
    else:
        file_id, ftype, content = "", "", update.message.text.strip()

    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM daily_reports WHERE user_id=? AND date=?", (uid, date)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE daily_reports SET content=?, file_id=?, file_type=? WHERE id=?",
            (content, file_id, ftype, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO daily_reports(user_id, date, content, file_id, file_type) VALUES(?,?,?,?,?)",
            (uid, date, content, file_id, ftype)
        )
    conn.commit()
    conn.close()

    kb = Kb([
        [Btn(f"{E['see']} Browse reports", callback_data="report_see_0"),
         Btn(f"{E['memory']} Memories",    callback_data="mem_home")],
    ])
    await update.message.reply_text(
        f"{E['done']} *Daily log saved!*\n📅 {date}",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def report_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx  = int(query.data.split("_")[-1])
    uid  = query.from_user.id

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM daily_reports WHERE user_id=? ORDER BY date DESC", (uid,)
    ).fetchall()
    conn.close()

    if not entries:
        await query.edit_message_text(
            "_No daily reports yet._",
            parse_mode="Markdown",
            reply_markup=Kb([
                [Btn(f"{E['add']} Write first report", callback_data="report_add_today")],
                back_btn("mem_home")[0],
            ])
        )
        return S_VIEW

    total = len(entries)
    idx   = max(0, min(idx, total - 1))
    e     = entries[idx]

    nav = []
    if idx > 0:         nav.append(Btn(f"{E['back']} Prev", callback_data=f"report_see_{idx-1}"))
    nav.append(Btn(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1: nav.append(Btn(f"Next {E['next']}", callback_data=f"report_see_{idx+1}"))

    kb = Kb([nav, back_btn("mem_report_home")[0]])

    date_display = datetime.datetime.strptime(e["date"], "%Y-%m-%d").strftime("%A, %d %B %Y")
    hdr  = f"{E['report']} *{date_display}*\n{DIVIDER}\n"
    body = hdr + (e["content"] or "_No text_")

    if e["file_id"]:
        try: await query.message.delete()
        except: pass
        send = query.message.chat.send_photo if e["file_type"] == "photo" else query.message.chat.send_document
        await send(e["file_id"], caption=body, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(body, parse_mode="Markdown", reply_markup=kb)
    return S_VIEW


# ═══════════════════════════════════════════════════════════════
#  CONVERSATION HANDLER
# ═══════════════════════════════════════════════════════════════
def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(mem_home, pattern="^mem_home$")],
        states={
            S_MEM_HOME: [
                CallbackQueryHandler(mem_section,   pattern="^mem_(silly|error|important)_home$"),
                CallbackQueryHandler(mem_add_start, pattern="^mem_add_"),
                CallbackQueryHandler(mem_see,       pattern="^mem_see_"),
                CallbackQueryHandler(report_home,   pattern="^mem_report_home$"),
                CallbackQueryHandler(report_add_ask,pattern="^report_add_today$"),
                CallbackQueryHandler(report_see,    pattern="^report_see_"),
            ],
            S_ADD_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, mem_got_title)],
            S_ADD_CONTENT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, mem_got_content),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mem_got_content),
            ],
            S_ADD_ANSWER: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, mem_got_answer),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mem_got_answer),
                CallbackQueryHandler(mem_ans_skip, pattern="^mem_ans_skip$"),
            ],
            S_ADD_KEYPOINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mem_got_keypoints),
                CallbackQueryHandler(mem_kp_skip, pattern="^mem_kp_skip$"),
            ],
            S_REPORT_CONTENT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, report_got_content),
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_got_content),
            ],
            S_VIEW: [
                CallbackQueryHandler(mem_see,         pattern="^mem_see_"),
                CallbackQueryHandler(mem_show_answer, pattern="^mem_ans_"),
                CallbackQueryHandler(mem_del_confirm, pattern="^mem_del_"),
                CallbackQueryHandler(mem_del_yes,     pattern="^mem_delyes_"),
                CallbackQueryHandler(mem_section,     pattern="^mem_(silly|error|important)_home$"),
                CallbackQueryHandler(report_see,      pattern="^report_see_"),
                CallbackQueryHandler(report_home,     pattern="^mem_report_home$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(mem_home, pattern="^mem_home$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
