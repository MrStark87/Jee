"""
handlers/memories.py
Sections: Silly | Error | Important
Each: add (text/image) + see (ek ek karke) + search
Error/Important: Question + Answer + Key Points
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn

# ── States ─────────────────────────────────────────────────────
(
    MEM_HOME,
    MEM_ADD_TITLE,
    MEM_ADD_CONTENT,      # text or image for silly/thought; question for error/imp
    MEM_ADD_ANSWER,       # answer (error/imp only)
    MEM_ADD_KEYPOINTS,    # key points (error/imp only)
    MEM_VIEW,
) = range(6)

MEM_LABELS = {
    "silly":     ("🤦 Silly",     "apni silly mistakes"),
    "error":     ("❌ Error",     "galat questions"),
    "important": ("⭐ Important", "important questions"),
}


# ── Keyboards ──────────────────────────────────────────────────
def mem_home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤦 Silly",     callback_data="mem_silly_home"),
         InlineKeyboardButton("❌ Error",     callback_data="mem_error_home")],
        [InlineKeyboardButton("⭐ Important", callback_data="mem_important_home")],
        [InlineKeyboardButton("🏠 Home",      callback_data="home")],
    ])


def mem_section_kb(mem_type: str):
    label = MEM_LABELS[mem_type][0]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"➕ Add",  callback_data=f"mem_add_{mem_type}"),
         InlineKeyboardButton(f"👁 See",  callback_data=f"mem_see_{mem_type}_0")],
        [InlineKeyboardButton("◀️ Back",  callback_data="mem_home")],
    ])


# ═══════════════════════════════════════════════════════════════
#  HOME
# ═══════════════════════════════════════════════════════════════
async def mem_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🧠 *Memories*\n\nApni knowledge vault — kya dekhna/add karna hai?",
        parse_mode="Markdown",
        reply_markup=mem_home_kb()
    )
    return MEM_HOME


async def mem_section_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    mem_type = query.data.replace("mem_", "").replace("_home", "")
    label, desc = MEM_LABELS[mem_type]
    uid = query.from_user.id

    conn  = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE user_id=? AND mem_type=?",
        (uid, mem_type)
    ).fetchone()[0]
    conn.close()

    await query.edit_message_text(
        f"{label}\n\n_{desc}_\nTotal entries: *{count}*\n\nTip: `/search <title>` se seedha search karo!",
        parse_mode="Markdown",
        reply_markup=mem_section_kb(mem_type)
    )
    return MEM_HOME


# ═══════════════════════════════════════════════════════════════
#  ADD FLOW
# ═══════════════════════════════════════════════════════════════
async def mem_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    mem_type = query.data.replace("mem_add_", "")
    context.user_data["mem_type"] = mem_type

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"mem_{mem_type}_home")]])
    await query.edit_message_text(
        f"📝 *Title daalo*\n_Short naam — baad mein isi se search hoga_\n_Example: q1, silly1, optics mistake_",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return MEM_ADD_TITLE


async def mem_add_got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mem_title"] = update.message.text.strip()
    mem_type = context.user_data["mem_type"]

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"mem_{mem_type}_home")]])

    if mem_type == "silly":
        await update.message.reply_text(
            "🤦 *Silly mistake kya thi?*\nText type karo ya image bhejo",
            parse_mode="Markdown", reply_markup=kb
        )
    else:
        await update.message.reply_text(
            "❓ *Question bhejo*\nText type karo ya image bhejo",
            parse_mode="Markdown", reply_markup=kb
        )
    return MEM_ADD_CONTENT


async def mem_add_got_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem_type = context.user_data["mem_type"]

    if update.message.photo:
        context.user_data["mem_content"]   = ""
        context.user_data["mem_file_id"]   = update.message.photo[-1].file_id
        context.user_data["mem_file_type"] = "photo"
    elif update.message.document:
        context.user_data["mem_content"]   = ""
        context.user_data["mem_file_id"]   = update.message.document.file_id
        context.user_data["mem_file_type"] = "document"
    else:
        context.user_data["mem_content"]   = update.message.text.strip()
        context.user_data["mem_file_id"]   = ""
        context.user_data["mem_file_type"] = ""

    if mem_type == "silly":
        # Silly: no answer/keypoints needed
        return await _save_memory(update, context)

    # Error / Important: ask for answer
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Skip", callback_data="mem_ans_skip")]])
    await update.message.reply_text(
        "✅ *Answer kya hai?*\nText ya image — dono chalega",
        parse_mode="Markdown", reply_markup=kb
    )
    return MEM_ADD_ANSWER


async def mem_add_got_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["mem_answer"]    = ""
        context.user_data["mem_ans_file"]  = update.message.photo[-1].file_id
        context.user_data["mem_ans_ftype"] = "photo"
    elif update.message.document:
        context.user_data["mem_answer"]    = ""
        context.user_data["mem_ans_file"]  = update.message.document.file_id
        context.user_data["mem_ans_ftype"] = "document"
    else:
        context.user_data["mem_answer"]    = update.message.text.strip()
        context.user_data["mem_ans_file"]  = ""
        context.user_data["mem_ans_ftype"] = ""

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Skip", callback_data="mem_kp_skip")]])
    await update.message.reply_text(
        "🔑 *Key points? (optional)*\nBullet points mein likho",
        parse_mode="Markdown", reply_markup=kb
    )
    return MEM_ADD_KEYPOINTS


async def mem_ans_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mem_answer"]    = ""
    context.user_data["mem_ans_file"]  = ""
    context.user_data["mem_ans_ftype"] = ""
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Skip", callback_data="mem_kp_skip")]])
    await query.edit_message_text(
        "🔑 *Key points? (optional)*\nBullet points mein likho",
        parse_mode="Markdown", reply_markup=kb
    )
    return MEM_ADD_KEYPOINTS


async def mem_add_got_keypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mem_keypoints"] = update.message.text.strip()
    return await _save_memory(update, context)


async def mem_kp_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mem_keypoints"] = ""
    return await _save_memory(update, context)


async def _save_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d   = context.user_data
    mt  = d["mem_type"]

    conn = get_conn()
    conn.execute("""
        INSERT INTO memories
        (user_id, mem_type, title, content, file_id, file_type, answer, ans_file, keypoints)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        uid, mt,
        d.get("mem_title", ""),
        d.get("mem_content", ""),
        d.get("mem_file_id", ""),
        d.get("mem_file_type", ""),
        d.get("mem_answer", ""),
        d.get("mem_ans_file", ""),
        d.get("mem_keypoints", ""),
    ))
    conn.commit()
    conn.close()

    label = MEM_LABELS[mt][0]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"➕ Aur add karo", callback_data=f"mem_add_{mt}"),
         InlineKeyboardButton(f"👁 See all",      callback_data=f"mem_see_{mt}_0")],
        [InlineKeyboardButton("🧠 Memories",      callback_data="mem_home")],
    ])

    text = f"✅ *{label}* mein save ho gaya!\n\n📌 Title: `{d.get('mem_title','')}`"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  SEE — ek ek karke with Next/Prev
# ═══════════════════════════════════════════════════════════════
async def mem_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")   # mem_see_silly_0
    mt     = parts[2]
    idx    = int(parts[3])
    uid    = query.from_user.id

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM memories WHERE user_id=? AND mem_type=? ORDER BY created DESC",
        (uid, mt)
    ).fetchall()
    conn.close()

    if not entries:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=f"mem_{mt}_home")]])
        await query.edit_message_text(f"_Koi entry nahi hai abhi._", parse_mode="Markdown", reply_markup=kb)
        return MEM_HOME

    total = len(entries)
    idx   = max(0, min(idx, total - 1))
    e     = entries[idx]
    mt_   = e["mem_type"]
    label = MEM_LABELS[mt_][0]

    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"mem_see_{mt}_{idx-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"mem_see_{mt}_{idx+1}"))

    extra_btns = []
    if mt_ in ("error", "important") and (e["answer"] or e["ans_file"] or e["keypoints"]):
        extra_btns.append(InlineKeyboardButton("💡 Answer & Key Points", callback_data=f"mem_ans_{e['id']}"))

    kb = InlineKeyboardMarkup(
        [nav_buttons] +
        ([extra_btns] if extra_btns else []) +
        [[InlineKeyboardButton("◀️ Back", callback_data=f"mem_{mt}_home")]]
    )

    header = f"{label} — {idx+1}/{total}\n📌 *{e['title']}*\n"
    content_text = e["content"] or ""
    full_text = header + (f"\n{content_text}" if content_text else "")

    if e["file_id"]:
        try:
            await query.message.delete()
        except Exception:
            pass
        if e["file_type"] == "photo":
            await query.message.chat.send_photo(
                e["file_id"], caption=full_text, parse_mode="Markdown", reply_markup=kb
            )
        else:
            await query.message.chat.send_document(
                e["file_id"], caption=full_text, parse_mode="Markdown", reply_markup=kb
            )
    else:
        await query.edit_message_text(full_text, parse_mode="Markdown", reply_markup=kb)

    return MEM_VIEW


async def mem_show_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    mem_id = int(query.data.split("_")[-1])

    conn = get_conn()
    e    = conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
    conn.close()

    label = MEM_LABELS[e["mem_type"]][0]
    text  = f"{label} — *{e['title']}*\n\n"

    if e["answer"]:
        text += f"✅ *Answer:*\n{e['answer']}\n\n"
    if e["keypoints"]:
        text += f"🔑 *Key Points:*\n{e['keypoints']}"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Back", callback_data=f"mem_see_{e['mem_type']}_0")
    ]])

    if e["ans_file"]:
        await query.message.delete()
        if e["file_type"] == "photo":
            await query.message.chat.send_photo(
                e["ans_file"], caption=text, parse_mode="Markdown", reply_markup=kb
            )
        else:
            await query.message.chat.send_document(
                e["ans_file"], caption=text, parse_mode="Markdown", reply_markup=kb
            )
    else:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    return MEM_VIEW


# ═══════════════════════════════════════════════════════════════
#  CONVERSATION HANDLER
# ═══════════════════════════════════════════════════════════════
def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(mem_home, pattern="^mem_home$")],
        states={
            MEM_HOME: [
                CallbackQueryHandler(mem_section_home, pattern="^mem_(silly|error|important)_home$"),
                CallbackQueryHandler(mem_add_start,    pattern="^mem_add_"),
                CallbackQueryHandler(mem_see,          pattern="^mem_see_"),
            ],
            MEM_ADD_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, mem_add_got_title)],
            MEM_ADD_CONTENT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, mem_add_got_content),
                MessageHandler(filters.TEXT  & ~filters.COMMAND,     mem_add_got_content),
            ],
            MEM_ADD_ANSWER: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, mem_add_got_answer),
                MessageHandler(filters.TEXT  & ~filters.COMMAND,     mem_add_got_answer),
                CallbackQueryHandler(mem_ans_skip, pattern="^mem_ans_skip$"),
            ],
            MEM_ADD_KEYPOINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mem_add_got_keypoints),
                CallbackQueryHandler(mem_kp_skip, pattern="^mem_kp_skip$"),
            ],
            MEM_VIEW: [
                CallbackQueryHandler(mem_see,         pattern="^mem_see_"),
                CallbackQueryHandler(mem_show_answer, pattern="^mem_ans_"),
                CallbackQueryHandler(mem_section_home,pattern="^mem_(silly|error|important)_home$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(mem_home, pattern="^mem_home$"),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
