"""
handlers/thought.py — Private thoughts journal (text/image)
"""
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn
from ui import E, cancel_btn, back_btn, DIVIDER
from handlers.common import check_banned

(S_HOME, S_ADD, S_VIEW) = range(3)


async def thought_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    conn  = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM thoughts WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    kb = Kb([
        [Btn(f"{E['add']} Add thought",       callback_data="thought_add"),
         Btn(f"{E['see']} See thoughts ({count})", callback_data="thought_see_0")],
        back_btn("home")[0],
    ])
    await query.edit_message_text(
        f"{E['thought']} *Thoughts*\n{DIVIDER}\n"
        f"Capture any thought — privately.\nTotal saved: *{count}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return S_HOME


async def thought_add_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['thought']} *What's on your mind?*\nText or image:",
        parse_mode="Markdown", reply_markup=cancel_btn("thought_home")
    )
    return S_ADD


async def thought_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.photo:
        fid, ftype, content = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    elif update.message.document:
        fid, ftype, content = update.message.document.file_id, "document", update.message.caption or ""
    else:
        fid, ftype, content = "", "", update.message.text.strip()
    conn = get_conn()
    conn.execute("INSERT INTO thoughts(user_id,content,file_id,file_type) VALUES(?,?,?,?)", (uid, content, fid, ftype))
    conn.commit()
    conn.close()
    kb = Kb([
        [Btn(f"{E['add']} Add another", callback_data="thought_add"),
         Btn(f"{E['see']} See all",     callback_data="thought_see_0")],
        back_btn("home")[0],
    ])
    await update.message.reply_text(f"{E['done']} Thought saved {E['thought']}", reply_markup=kb)
    return ConversationHandler.END


async def thought_see(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx   = int(query.data.split("_")[-1])
    uid   = query.from_user.id
    conn  = get_conn()
    items = conn.execute("SELECT * FROM thoughts WHERE user_id=? ORDER BY created DESC", (uid,)).fetchall()
    conn.close()

    if not items:
        await query.edit_message_text(
            "_No thoughts yet._", parse_mode="Markdown",
            reply_markup=Kb([[Btn(f"{E['add']} Add first", callback_data="thought_add")], back_btn("thought_home")[0]])
        )
        return S_VIEW

    total = len(items)
    idx   = max(0, min(idx, total-1))
    e     = items[idx]

    nav = []
    if idx > 0:         nav.append(Btn(f"{E['back']} Prev", callback_data=f"thought_see_{idx-1}"))
    nav.append(Btn(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1: nav.append(Btn(f"Next {E['next']}", callback_data=f"thought_see_{idx+1}"))

    kb  = Kb([nav, back_btn("thought_home")[0]])
    cap = f"{E['thought']} *Thought {idx+1}/{total}*\n_{e['created'][:10]}_\n\n{e['content']}"

    if e["file_id"]:
        try: await query.message.delete()
        except: pass
        send = query.message.chat.send_photo if e["file_type"] == "photo" else query.message.chat.send_document
        await send(e["file_id"], caption=cap, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(cap, parse_mode="Markdown", reply_markup=kb)
    return S_VIEW


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(thought_home, pattern="^thought_home$")],
        states={
            S_HOME: [
                CallbackQueryHandler(thought_add_ask, pattern="^thought_add$"),
                CallbackQueryHandler(thought_see,     pattern="^thought_see_"),
            ],
            S_ADD:  [
                MessageHandler(filters.PHOTO | filters.Document.ALL, thought_save),
                MessageHandler(filters.TEXT & ~filters.COMMAND, thought_save),
            ],
            S_VIEW: [CallbackQueryHandler(thought_see, pattern="^thought_see_")],
        },
        fallbacks=[CallbackQueryHandler(thought_home, pattern="^thought_home$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
