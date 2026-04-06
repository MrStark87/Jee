"""
handlers/admin.py
Password protected admin panel.
- Formula upload (Class 11/12, chapter, PDF/image/text)
- Broadcast to all users
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn, get_all_users
from config import ADMIN_ID, ADMIN_PASS

(
    ADMIN_HOME,
    ADMIN_AUTH,
    FORMULA_CLASS,
    FORMULA_CHAPTER_ASK,
    FORMULA_SUBJECT_ASK,
    FORMULA_FILE,
    BROADCAST_MSG,
) = range(7)

AUTHED_USERS = set()   # In-memory auth (session-based)


def is_authed(uid: int) -> bool:
    return uid == ADMIN_ID or uid in AUTHED_USERS


def admin_home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 Add Formula",   callback_data="adm_formula"),
         InlineKeyboardButton("📢 Broadcast",     callback_data="adm_broadcast")],
        [InlineKeyboardButton("📊 Stats",         callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Home",          callback_data="home")],
    ])


async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if is_authed(uid):
        await query.edit_message_text(
            "⚙️ *Admin Panel*\nWelcome back!", parse_mode="Markdown",
            reply_markup=admin_home_kb()
        )
        return ADMIN_HOME

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]])
    await query.edit_message_text(
        "🔐 *Admin Password daalo*",
        parse_mode="Markdown", reply_markup=kb
    )
    return ADMIN_AUTH


async def admin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.text.strip() == ADMIN_PASS:
        AUTHED_USERS.add(uid)
        kb = admin_home_kb()
        await update.message.reply_text(
            "✅ *Admin Panel*\nAccess granted!", parse_mode="Markdown", reply_markup=kb
        )
        return ADMIN_HOME
    await update.message.reply_text("❌ Wrong password!")
    return ADMIN_AUTH


# ── Stats ──────────────────────────────────────────────────────
async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_conn()
    users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    mems     = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    formulas = conn.execute("SELECT COUNT(*) FROM formulas").fetchone()[0]
    tasks    = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="adm_back")]])
    await query.edit_message_text(
        f"📊 *Stats*\n\nUsers: {users}\nMemory entries: {mems}\nFormulas: {formulas}\nTotal tasks: {tasks}",
        parse_mode="Markdown", reply_markup=kb
    )
    return ADMIN_HOME


# ── Formula Upload ─────────────────────────────────────────────
async def adm_formula_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_authed(query.from_user.id):
        await query.answer("Access denied!", show_alert=True)
        return ADMIN_HOME
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📗 Class 11", callback_data="adm_class_11"),
         InlineKeyboardButton("📘 Class 12", callback_data="adm_class_12")],
        [InlineKeyboardButton("◀️ Back",     callback_data="adm_back")],
    ])
    await query.edit_message_text("📐 *Kis class ke liye?*", parse_mode="Markdown", reply_markup=kb)
    return FORMULA_CLASS


async def adm_class_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    cls_num  = query.data.split("_")[-1]   # 11 or 12
    context.user_data["adm_class"] = cls_num
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]])
    await query.edit_message_text(
        f"📐 Class {cls_num} — *Chapter ka naam type karo*\n_Example: Wave Optics, Limits, Organic Chemistry_",
        parse_mode="Markdown", reply_markup=kb
    )
    return FORMULA_CHAPTER_ASK


async def adm_chapter_got(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["adm_chapter"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("PHY", callback_data="adm_sub_PHY"),
         InlineKeyboardButton("CHEM", callback_data="adm_sub_CHEM"),
         InlineKeyboardButton("MATH", callback_data="adm_sub_MATH")],
        [InlineKeyboardButton("BIO", callback_data="adm_sub_BIO"),
         InlineKeyboardButton("Other", callback_data="adm_sub_OTHER")],
    ])
    await update.message.reply_text("📖 *Subject?*", parse_mode="Markdown", reply_markup=kb)
    return FORMULA_SUBJECT_ASK


async def adm_subject_got(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["adm_subject"] = query.data.replace("adm_sub_", "")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]])
    await query.edit_message_text(
        f"📤 *Ab file bhejo*\nPDF, image, ya text — teeno chalega\n\n"
        f"Chapter: *{context.user_data['adm_chapter']}* | Class: *{context.user_data['adm_class']}*",
        parse_mode="Markdown", reply_markup=kb
    )
    return FORMULA_FILE


async def adm_formula_file_got(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d   = context.user_data

    if update.message.document:
        file_id, ftype = update.message.document.file_id, "document"
        content = update.message.caption or ""
    elif update.message.photo:
        file_id, ftype = update.message.photo[-1].file_id, "photo"
        content = update.message.caption or ""
    else:
        file_id, ftype = "", "text"
        content = update.message.text.strip()

    conn = get_conn()
    conn.execute("""
        INSERT INTO formulas(class_num, chapter, subject, file_id, file_type, content, added_by)
        VALUES(?,?,?,?,?,?,?)
    """, (d["adm_class"], d["adm_chapter"], d.get("adm_subject",""), file_id, ftype, content, uid))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aur add karo", callback_data="adm_formula"),
         InlineKeyboardButton("⚙️ Admin Home",   callback_data="adm_back")],
    ])
    await update.message.reply_text(
        f"✅ *Formula add ho gaya!*\n\n"
        f"Chapter: *{d['adm_chapter']}* | Class {d['adm_class']}\n"
        f"Ab sab log is chapter ka button dekh payenge Formulas section mein!",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


# ── Broadcast ──────────────────────────────────────────────────
async def adm_broadcast_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_authed(query.from_user.id):
        await query.answer("Access denied!", show_alert=True)
        return ADMIN_HOME
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]])
    await query.edit_message_text(
        "📢 *Broadcast message type karo*\nSabke paas jayega",
        parse_mode="Markdown", reply_markup=kb
    )
    return BROADCAST_MSG


async def adm_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg     = update.message.text.strip()
    bot     = update.message.get_bot()
    users   = get_all_users()
    success = 0
    fail    = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 *Announcement*\n\n{msg}", parse_mode="Markdown")
            success += 1
        except Exception:
            fail += 1

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin", callback_data="adm_back")]])
    await update.message.reply_text(
        f"✅ Broadcast complete!\n\nSent: {success}\nFailed: {fail}",
        reply_markup=kb
    )
    return ConversationHandler.END


async def adm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_home_kb()
    )
    return ADMIN_HOME


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_entry, pattern="^admin_home$")],
        states={
            ADMIN_HOME: [
                CallbackQueryHandler(adm_formula_start, pattern="^adm_formula$"),
                CallbackQueryHandler(adm_broadcast_ask, pattern="^adm_broadcast$"),
                CallbackQueryHandler(adm_stats,         pattern="^adm_stats$"),
                CallbackQueryHandler(adm_back,          pattern="^adm_back$"),
            ],
            ADMIN_AUTH:            [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_auth)],
            FORMULA_CLASS:         [CallbackQueryHandler(adm_class_chosen,    pattern="^adm_class_")],
            FORMULA_CHAPTER_ASK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_chapter_got)],
            FORMULA_SUBJECT_ASK:   [CallbackQueryHandler(adm_subject_got,     pattern="^adm_sub_")],
            FORMULA_FILE: [
                MessageHandler(filters.Document.ALL, adm_formula_file_got),
                MessageHandler(filters.PHOTO,        adm_formula_file_got),
                MessageHandler(filters.TEXT & ~filters.COMMAND, adm_formula_file_got),
            ],
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_send)],
        },
        fallbacks=[
            CallbackQueryHandler(adm_back, pattern="^adm_back$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
