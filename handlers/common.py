"""
handlers/common.py — /start, home callback, /ban, /unban, ban middleware
"""

import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import upsert_user, get_user, is_banned
from ui import home_kb, welcome_text, E
from config import ADMIN_ID


async def check_banned(update: Update) -> bool:
    """Returns True if user is banned (and sends notice). Use in every handler."""
    uid = update.effective_user.id if update.effective_user else None
    if uid and is_banned(uid):
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        if msg:
            await msg.reply_text(f"{E['ban']} You are banned from using this bot.")
        return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update):
        return
    user = update.effective_user
    upsert_user(user.id, user.first_name)
    db_user = get_user(user.id)
    streak  = db_user["streak"] if db_user else 0
    await update.message.reply_text(
        welcome_text(user.first_name, streak),
        parse_mode="Markdown",
        reply_markup=home_kb()
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update):
        return
    query = update.callback_query
    await query.answer()
    user    = query.from_user
    db_user = get_user(user.id)
    streak  = db_user["streak"] if db_user else 0
    await query.edit_message_text(
        welcome_text(user.first_name, streak),
        parse_mode="Markdown",
        reply_markup=home_kb()
    )


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


# ── /ban and /unban ────────────────────────────────────────────

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"{E['ban']} Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    from database import get_conn
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned=1 WHERE tg_id=?", (target,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"{E['ban']} User `{target}` banned.", parse_mode="Markdown")
    try:
        await context.bot.send_message(target, f"{E['ban']} You have been banned from JEE Saarthi.")
    except Exception:
        pass


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"{E['ban']} Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/unban <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    from database import get_conn
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned=0 WHERE tg_id=?", (target,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"{E['done']} User `{target}` unbanned.", parse_mode="Markdown")
    try:
        await context.bot.send_message(target, f"{E['done']} You have been unbanned. Welcome back!")
    except Exception:
        pass
