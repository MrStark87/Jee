"""
handlers/thought.py — Private thoughts (text/image)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn

(THOUGHT_HOME, THOUGHT_ADD, THOUGHT_VIEW) = range(3)


async def thought_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    conn  = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM thoughts WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Thought", callback_data="thought_add"),
         InlineKeyboardButton("👁 See Thoughts", callback_data="thought_see_0")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])
    await query.edit_message_text(
        f"💭 *Thoughts*\n\nApne thoughts yahan capture karo — sirf tumhare liye.\nTotal: *{count}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return THOUGHT_HOME


async def thought_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="thought_home")]])
    await query.edit_message_text(
        "💭 *Kya soch rahe ho?*\nText likho ya image bhejo",
        parse_mode="Markdown", reply_markup=kb
    )
    return THOUGHT_ADD


async def thought_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.photo:
        file_id, ftype, content = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        file_id, ftype, content = update.message.document.file_id, "document", update.message.caption or ""
    else:
        file_id, ftype, content = "", "", update.message.text.strip()

    conn = get_conn()
    conn.execute(
        "INSERT INTO thoughts(user_id, content, file_id, file_type) VALUES(?,?,?,?)",
        (uid, content, file_id, ftype)
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aur add karo", callback_data="thought_add"),
         InlineKeyboardButton("👁 Dekho",        callback_data="thought_see_0")],
        [InlineKeyboardButton("🏠 Home",         callback_data="home")],
    ])
    await update.message.reply_text("✅ Thought save ho gaya! 💭", reply_markup=kb)
    return ConversationHandler.END


async def thought_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx   = int(query.data.split("_")[-1])
    uid   = query.from_user.id

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM thoughts WHERE user_id=? ORDER BY created DESC", (uid,)
    ).fetchall()
    conn.close()

    if not entries:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="thought_home")]])
        await query.edit_message_text("_Abhi koi thought nahi._", parse_mode="Markdown", reply_markup=kb)
        return THOUGHT_HOME

    total = len(entries)
    idx   = max(0, min(idx, total - 1))
    e     = entries[idx]

    nav = []
    if idx > 0:         nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"thought_see_{idx-1}"))
    nav.append(InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1: nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"thought_see_{idx+1}"))

    kb  = InlineKeyboardMarkup([nav, [InlineKeyboardButton("◀️ Back", callback_data="thought_home")]])
    cap = f"💭 *Thought {idx+1}/{total}*\n_{e['created'][:10]}_\n\n{e['content']}"

    if e["file_id"]:
        try: await query.message.delete()
        except: pass
        send = query.message.chat.send_photo if e["file_type"] == "photo" else query.message.chat.send_document
        await send(e["file_id"], caption=cap, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(cap, parse_mode="Markdown", reply_markup=kb)
    return THOUGHT_VIEW


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(thought_home, pattern="^thought_home$")],
        states={
            THOUGHT_HOME: [
                CallbackQueryHandler(thought_add_ask, pattern="^thought_add$"),
                CallbackQueryHandler(thought_see,     pattern="^thought_see_"),
            ],
            THOUGHT_ADD: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, thought_add_save),
                MessageHandler(filters.TEXT  & ~filters.COMMAND,     thought_add_save),
            ],
            THOUGHT_VIEW: [
                CallbackQueryHandler(thought_see, pattern="^thought_see_"),
            ],
        },
        fallbacks=[CallbackQueryHandler(thought_home, pattern="^thought_home$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
