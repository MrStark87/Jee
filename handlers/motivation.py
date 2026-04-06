"""
handlers/motivation.py — Khud ke private quotes
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn

(MOTIV_HOME, MOTIV_ADD, MOTIV_VIEW) = range(3)


async def motiv_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM motivation WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Quote", callback_data="motiv_add"),
         InlineKeyboardButton("👁 See Quotes", callback_data="motiv_see_0")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])
    await query.edit_message_text(
        f"🔥 *Motivation*\n\nYe sirf tumhara vault hai — khud ke liye likho!\nTotal quotes: *{count}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return MOTIV_HOME


async def motiv_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="motiv_home")]])
    await query.edit_message_text(
        "🔥 *Apna quote / thought / note likho*\nText ya image — kuch bhi",
        parse_mode="Markdown", reply_markup=kb
    )
    return MOTIV_ADD


async def motiv_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.photo:
        file_id, ftype, content = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        file_id, ftype, content = update.message.document.file_id, "document", update.message.caption or ""
    else:
        file_id, ftype, content = "", "", update.message.text.strip()

    conn = get_conn()
    conn.execute(
        "INSERT INTO motivation(user_id, content, file_id, file_type) VALUES(?,?,?,?)",
        (uid, content, file_id, ftype)
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aur likho", callback_data="motiv_add"),
         InlineKeyboardButton("👁 Dekho",     callback_data="motiv_see_0")],
        [InlineKeyboardButton("🏠 Home",      callback_data="home")],
    ])
    await update.message.reply_text("✅ Save ho gaya! Jab mann kare tab padho 🔥", reply_markup=kb)
    return ConversationHandler.END


async def motiv_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[-1])
    uid = query.from_user.id

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM motivation WHERE user_id=? ORDER BY created DESC", (uid,)
    ).fetchall()
    conn.close()

    if not entries:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="motiv_home")]])
        await query.edit_message_text("_Abhi koi quote nahi — pehla likho!_", parse_mode="Markdown", reply_markup=kb)
        return MOTIV_HOME

    total = len(entries)
    idx   = max(0, min(idx, total - 1))
    e     = entries[idx]

    nav = []
    if idx > 0:         nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"motiv_see_{idx-1}"))
    nav.append(InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1: nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"motiv_see_{idx+1}"))

    kb = InlineKeyboardMarkup([nav, [InlineKeyboardButton("◀️ Back", callback_data="motiv_home")]])

    date_str = e["created"][:10]
    caption  = f"🔥 *Quote {idx+1}/{total}*\n_{date_str}_\n\n{e['content']}"

    if e["file_id"]:
        try: await query.message.delete()
        except: pass
        if e["file_type"] == "photo":
            await query.message.chat.send_photo(e["file_id"], caption=caption, parse_mode="Markdown", reply_markup=kb)
        else:
            await query.message.chat.send_document(e["file_id"], caption=caption, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=kb)
    return MOTIV_VIEW


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(motiv_home, pattern="^motiv_home$")],
        states={
            MOTIV_HOME: [
                CallbackQueryHandler(motiv_add_ask, pattern="^motiv_add$"),
                CallbackQueryHandler(motiv_see,     pattern="^motiv_see_"),
            ],
            MOTIV_ADD: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, motiv_add_save),
                MessageHandler(filters.TEXT  & ~filters.COMMAND,     motiv_add_save),
            ],
            MOTIV_VIEW: [
                CallbackQueryHandler(motiv_see, pattern="^motiv_see_"),
            ],
        },
        fallbacks=[CallbackQueryHandler(motiv_home, pattern="^motiv_home$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
