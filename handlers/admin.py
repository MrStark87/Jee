"""
handlers/admin.py
Password-protected admin panel.
- Popup alert for non-admins
- Formula upload (Class 11/12, chapter, PDF/image/text)
- Broadcast to all active users
- User list with ban/unban
- Stats dashboard
"""
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from database import get_conn, get_all_users
from config import ADMIN_ID, ADMIN_PASS
from ui import E, cancel_btn, back_btn, subject_kb, DIVIDER

(
    S_HOME, S_AUTH,
    S_FCLASS, S_FCHAPTER, S_FSUBJECT, S_FFILE,
    S_BROADCAST,
) = range(7)

_authed: set = set()

def _is_auth(uid: int) -> bool:
    return uid == ADMIN_ID or uid in _authed


def _admin_kb():
    return Kb([
        [Btn(f"{E['formula']} Add Formula",  callback_data="adm_formula"),
         Btn(f"{E['broadcast']} Broadcast",  callback_data="adm_broadcast")],
        [Btn(f"{E['test']} Stats",           callback_data="adm_stats"),
         Btn(f"{E['ban']} Manage Users",     callback_data="adm_users")],
        back_btn("home")[0],
    ])


# ═══════════════════════════════════════════════════════════════
#  ENTRY — with popup for non-admins
# ═══════════════════════════════════════════════════════════════
async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = query.from_user.id

    if not _is_auth(uid):
        # Show popup alert first
        await query.answer(
            "⚠️ Admin only. This section is restricted.",
            show_alert=True
        )
        await query.edit_message_text(
            f"{E['lock']} *Admin Panel*\n\nThis section is for administrators only.\nEnter the password to continue:",
            parse_mode="Markdown",
            reply_markup=cancel_btn("home")
        )
        return S_AUTH

    await query.answer()
    await query.edit_message_text(
        f"{E['admin']} *Admin Panel*\nWelcome back!",
        parse_mode="Markdown", reply_markup=_admin_kb()
    )
    return S_HOME


async def admin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.text.strip() == ADMIN_PASS:
        _authed.add(uid)
        await update.message.reply_text(
            f"{E['done']} *Access granted!*\n\n{E['admin']} Admin Panel",
            parse_mode="Markdown", reply_markup=_admin_kb()
        )
        return S_HOME
    await update.message.reply_text(f"{E['warn']} Wrong password. Try again:")
    return S_AUTH


async def adm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['admin']} *Admin Panel*",
        parse_mode="Markdown", reply_markup=_admin_kb()
    )
    return S_HOME


# ═══════════════════════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════════════════════
async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn  = get_conn()
    users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    banned   = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
    mems     = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    formulas = conn.execute("SELECT COUNT(*) FROM formulas").fetchone()[0]
    tasks    = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    reports  = conn.execute("SELECT COUNT(*) FROM daily_reports").fetchone()[0]
    conn.close()

    await query.edit_message_text(
        f"{E['test']} *Bot Stats*\n{DIVIDER}\n"
        f"👥 Total users: *{users}* ({banned} banned)\n"
        f"🧠 Memory entries: *{mems}*\n"
        f"📐 Formula files: *{formulas}*\n"
        f"📋 Tasks logged: *{tasks}*\n"
        f"📓 Daily reports: *{reports}*",
        parse_mode="Markdown",
        reply_markup=Kb([back_btn("adm_back")[0]])
    )
    return S_HOME


# ═══════════════════════════════════════════════════════════════
#  MANAGE USERS (ban/unban from UI)
# ═══════════════════════════════════════════════════════════════
async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn  = get_conn()
    users = conn.execute("SELECT tg_id, name, is_banned FROM users ORDER BY joined DESC LIMIT 20").fetchall()
    conn.close()

    rows = []
    for u in users:
        action = f"unban_{u['tg_id']}" if u["is_banned"] else f"ban_{u['tg_id']}"
        label  = f"{E['done']} Unban" if u["is_banned"] else f"{E['ban']} Ban"
        rows.append([Btn(f"{u['name'] or u['tg_id']} ({'banned' if u['is_banned'] else 'active'})", callback_data="noop"),
                     Btn(label, callback_data=f"adm_toggle_{action}")])
    rows.append(back_btn("adm_back")[0])
    await query.edit_message_text(
        f"{E['ban']} *Manage Users*\n_Last 20 users_",
        parse_mode="Markdown", reply_markup=Kb(rows)
    )
    return S_HOME


async def adm_toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")   # adm_toggle_ban/unban_userid
    action = parts[2]
    target = int(parts[3])
    conn   = get_conn()
    new_val = 1 if action == "ban" else 0
    conn.execute("UPDATE users SET is_banned=? WHERE tg_id=?", (new_val, target))
    conn.commit()
    conn.close()
    msg = f"{E['ban']} Banned" if new_val else f"{E['done']} Unbanned"
    await query.answer(f"{msg} user {target}", show_alert=True)
    try:
        note = f"{E['ban']} You have been banned." if new_val else f"{E['done']} You have been unbanned!"
        await context.bot.send_message(target, note)
    except Exception:
        pass
    return await adm_users(update, context)


# ═══════════════════════════════════════════════════════════════
#  FORMULA UPLOAD
# ═══════════════════════════════════════════════════════════════
async def adm_formula_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = Kb([
        [Btn(f"📗 Class 11", callback_data="adm_cls_11"),
         Btn(f"📘 Class 12", callback_data="adm_cls_12")],
        back_btn("adm_back")[0],
    ])
    await query.edit_message_text(
        f"{E['formula']} *Add Formula*\n\nSelect class:",
        parse_mode="Markdown", reply_markup=kb
    )
    return S_FCLASS


async def adm_cls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    cls_num = query.data.split("_")[-1]
    context.user_data["adm_cls"] = cls_num
    await query.edit_message_text(
        f"{E['formula']} Class {cls_num} — *Enter chapter name:*\n_Example: Wave Optics, Integrals_",
        parse_mode="Markdown", reply_markup=cancel_btn("adm_back")
    )
    return S_FCHAPTER


async def adm_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["adm_chapter"] = update.message.text.strip()
    await update.message.reply_text(
        f"Select subject:", reply_markup=subject_kb("adm_sub")
    )
    return S_FSUBJECT


async def adm_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["adm_subject"] = query.data.replace("adm_sub_", "")
    await query.edit_message_text(
        f"{E['up']} *Send the file*\nPDF, image, or text — all supported\n\n"
        f"Chapter: *{context.user_data['adm_chapter']}* | Class *{context.user_data['adm_cls']}*",
        parse_mode="Markdown", reply_markup=cancel_btn("adm_back")
    )
    return S_FFILE


async def adm_formula_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d   = context.user_data
    if update.message.document:
        fid, ftype, content = update.message.document.file_id, "document", update.message.caption or ""
    elif update.message.photo:
        fid, ftype, content = update.message.photo[-1].file_id, "photo", update.message.caption or ""
    else:
        fid, ftype, content = "", "text", update.message.text.strip()

    conn = get_conn()
    conn.execute(
        "INSERT INTO formulas(class_num,chapter,subject,file_id,file_type,content,added_by) VALUES(?,?,?,?,?,?,?)",
        (d["adm_cls"], d["adm_chapter"], d.get("adm_subject",""), fid, ftype, content, uid)
    )
    conn.commit()
    conn.close()

    kb = Kb([
        [Btn(f"{E['add']} Add more", callback_data="adm_formula"),
         Btn(f"{E['admin']} Admin",  callback_data="adm_back")],
    ])
    await update.message.reply_text(
        f"{E['done']} *Formula added!*\n\n"
        f"Chapter: *{d['adm_chapter']}* | Class {d['adm_cls']}\n"
        f"Button will appear automatically in Formulas section for all users!",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════════
async def adm_broadcast_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E['broadcast']} *Broadcast*\n\nType message to send to all users:",
        parse_mode="Markdown", reply_markup=cancel_btn("adm_back")
    )
    return S_BROADCAST


async def adm_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg     = update.message.text.strip()
    bot     = update.message.get_bot()
    users   = get_all_users()
    ok = fail = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"{E['broadcast']} *Announcement*\n\n{msg}", parse_mode="Markdown")
            ok += 1
        except Exception:
            fail += 1
    kb = Kb([[Btn(f"{E['admin']} Admin", callback_data="adm_back")]])
    await update.message.reply_text(
        f"{E['done']} Broadcast done!\nSent: {ok} | Failed: {fail}",
        reply_markup=kb
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  CONVERSATION HANDLER
# ═══════════════════════════════════════════════════════════════
def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_entry, pattern="^admin_home$")],
        states={
            S_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_auth)],
            S_HOME: [
                CallbackQueryHandler(adm_formula_start, pattern="^adm_formula$"),
                CallbackQueryHandler(adm_broadcast_ask, pattern="^adm_broadcast$"),
                CallbackQueryHandler(adm_stats,         pattern="^adm_stats$"),
                CallbackQueryHandler(adm_users,         pattern="^adm_users$"),
                CallbackQueryHandler(adm_toggle_ban,    pattern="^adm_toggle_"),
                CallbackQueryHandler(adm_back,          pattern="^adm_back$"),
            ],
            S_FCLASS:   [CallbackQueryHandler(adm_cls,     pattern="^adm_cls_")],
            S_FCHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_chapter)],
            S_FSUBJECT: [CallbackQueryHandler(adm_subject, pattern="^adm_sub_")],
            S_FFILE: [
                MessageHandler(filters.Document.ALL,            adm_formula_file),
                MessageHandler(filters.PHOTO,                   adm_formula_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, adm_formula_file),
            ],
            S_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_send)],
        },
        fallbacks=[CallbackQueryHandler(adm_back, pattern="^adm_back$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
