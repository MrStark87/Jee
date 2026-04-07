"""
handlers/formulas.py — Shared formula library (admin uploads, everyone views)
Chapter buttons auto-created on admin upload.
"""
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from database import get_conn
from ui import E, back_btn, DIVIDER
from handlers.common import check_banned

(S_HOME,) = range(1)


async def formula_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return ConversationHandler.END
    query = update.callback_query
    await query.answer()

    conn  = get_conn()
    c11   = conn.execute("SELECT DISTINCT chapter FROM formulas WHERE class_num='11' ORDER BY chapter").fetchall()
    c12   = conn.execute("SELECT DISTINCT chapter FROM formulas WHERE class_num='12' ORDER BY chapter").fetchall()
    conn.close()

    rows = []
    if c11:
        rows.append([Btn("── Class 11 ──", callback_data="noop")])
        row = []
        for ch in c11:
            row.append(Btn(ch["chapter"], callback_data=f"fch_11_{ch['chapter']}"))
            if len(row) == 2:
                rows.append(row); row = []
        if row: rows.append(row)

    if c12:
        rows.append([Btn("── Class 12 ──", callback_data="noop")])
        row = []
        for ch in c12:
            row.append(Btn(ch["chapter"], callback_data=f"fch_12_{ch['chapter']}"))
            if len(row) == 2:
                rows.append(row); row = []
        if row: rows.append(row)

    if not c11 and not c12:
        rows.append([Btn(f"No formulas uploaded yet", callback_data="noop")])

    rows.append(back_btn("home")[0])
    await query.edit_message_text(
        f"{E['formula']} *Formulas*\n{DIVIDER}\nSelect a chapter:",
        parse_mode="Markdown",
        reply_markup=Kb(rows)
    )
    return S_HOME


async def formula_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    parts   = query.data.split("_", 2)   # fch_11_WaveOptics
    cls_num = parts[1]
    chapter = parts[2]

    conn    = get_conn()
    entries = conn.execute(
        "SELECT * FROM formulas WHERE class_num=? AND chapter=? ORDER BY id",
        (cls_num, chapter)
    ).fetchall()
    conn.close()

    kb = Kb([[Btn(f"{E['back']} Back to Formulas", callback_data="formula_home")]])
    await query.edit_message_text(
        f"{E['formula']} *{chapter}* — Class {cls_num}\nSending {len(entries)} file(s)...",
        parse_mode="Markdown", reply_markup=kb
    )

    chat_id = query.message.chat_id
    bot     = query.get_bot()
    for e in entries:
        cap = f"{E['formula']} *{chapter}* | Class {cls_num}" + (f"\n\n{e['content']}" if e["content"] else "")
        try:
            if e["file_type"] == "photo":
                await bot.send_photo(chat_id, e["file_id"], caption=cap, parse_mode="Markdown")
            elif e["file_type"] in ("document", "pdf"):
                await bot.send_document(chat_id, e["file_id"], caption=cap, parse_mode="Markdown")
            elif e["content"] and not e["file_id"]:
                await bot.send_message(chat_id, cap, parse_mode="Markdown")
        except Exception as ex:
            await bot.send_message(chat_id, f"Could not send file: {ex}")

    return S_HOME


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(formula_home, pattern="^formula_home$")],
        states={
            S_HOME: [CallbackQueryHandler(formula_chapter, pattern="^fch_")],
        },
        fallbacks=[CallbackQueryHandler(formula_home, pattern="^formula_home$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
