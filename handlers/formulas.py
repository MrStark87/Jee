"""
handlers/formulas.py
Shared section — admin uploads, everyone can view.
Chapter buttons auto-create on upload.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn

(FORMULA_HOME, FORMULA_CLASS, FORMULA_CHAPTER) = range(3)


async def formula_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_conn()
    cls11 = conn.execute(
        "SELECT DISTINCT chapter FROM formulas WHERE class_num='11' ORDER BY chapter"
    ).fetchall()
    cls12 = conn.execute(
        "SELECT DISTINCT chapter FROM formulas WHERE class_num='12' ORDER BY chapter"
    ).fetchall()
    conn.close()

    kb_rows = []

    if cls11:
        kb_rows.append([InlineKeyboardButton("── Class 11 ──", callback_data="noop")])
        row = []
        for ch in cls11:
            row.append(InlineKeyboardButton(ch["chapter"], callback_data=f"formula_ch_11_{ch['chapter']}"))
            if len(row) == 2:
                kb_rows.append(row)
                row = []
        if row:
            kb_rows.append(row)

    if cls12:
        kb_rows.append([InlineKeyboardButton("── Class 12 ──", callback_data="noop")])
        row = []
        for ch in cls12:
            row.append(InlineKeyboardButton(ch["chapter"], callback_data=f"formula_ch_12_{ch['chapter']}"))
            if len(row) == 2:
                kb_rows.append(row)
                row = []
        if row:
            kb_rows.append(row)

    if not cls11 and not cls12:
        kb_rows.append([InlineKeyboardButton("📭 Abhi koi formula nahi", callback_data="noop")])

    kb_rows.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await query.edit_message_text(
        "📐 *Formulas*\n\nChapter choose karo — PDF/notes mil jayenge",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )
    return FORMULA_HOME


async def formula_chapter_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    # pattern: formula_ch_11_WaveOptics
    parts   = query.data.split("_", 4)   # ['formula','ch','11','WaveOptics']
    cls_num = parts[2]
    chapter = parts[3]

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM formulas WHERE class_num=? AND chapter=? ORDER BY id",
        (cls_num, chapter)
    ).fetchall()
    conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="formula_home")]])

    await query.edit_message_text(
        f"📐 *{chapter}* — Class {cls_num}\n\nSending {len(entries)} file(s)...",
        parse_mode="Markdown", reply_markup=kb
    )

    chat_id = query.message.chat_id
    bot     = query.get_bot()
    for e in entries:
        caption = f"📐 {chapter} | Class {cls_num}"
        if e["content"]:
            caption += f"\n\n{e['content']}"
        try:
            if e["file_type"] == "photo":
                await bot.send_photo(chat_id, e["file_id"], caption=caption, parse_mode="Markdown")
            elif e["file_type"] in ("document", "pdf"):
                await bot.send_document(chat_id, e["file_id"], caption=caption, parse_mode="Markdown")
            elif e["content"] and not e["file_id"]:
                await bot.send_message(chat_id, caption, parse_mode="Markdown")
        except Exception as ex:
            await bot.send_message(chat_id, f"⚠️ File send nahi hua: {ex}")

    return FORMULA_HOME


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(formula_home, pattern="^formula_home$")],
        states={
            FORMULA_HOME: [
                CallbackQueryHandler(formula_chapter_view, pattern="^formula_ch_"),
            ],
        },
        fallbacks=[CallbackQueryHandler(formula_home, pattern="^formula_home$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
