"""
handlers/common.py — /start, home keyboard, shared utilities
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import upsert_user
import datetime


def home_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Today",      callback_data="today_home"),
            InlineKeyboardButton("🧠 Memories",   callback_data="mem_home"),
        ],
        [
            InlineKeyboardButton("📐 Formulas",   callback_data="formula_home"),
            InlineKeyboardButton("💭 Thoughts",   callback_data="thought_home"),
        ],
        [
            InlineKeyboardButton("🔥 Motivation", callback_data="motiv_home"),
            InlineKeyboardButton("⚙️ Admin",      callback_data="admin_home"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.first_name)

    today_str = datetime.date.today().strftime("%A, %d %B %Y")
    text = (
        f"*Jai Shree Ram! 🙏*\n"
        f"Swagat hai JEE Saarthi mein, {user.first_name}!\n\n"
        f"📅 *{today_str}*\n\n"
        f"_Mehnat karo, kamyabi zaroor milegi._\n\n"
        f"Neeche se apna section choose karo 👇"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=home_keyboard()
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today_str = datetime.date.today().strftime("%A, %d %B %Y")
    user = query.from_user
    text = (
        f"*JEE Saarthi 🎯*\n"
        f"📅 {today_str}\n\n"
        f"Kya karna hai aaj, {user.first_name}?"
    )
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=home_keyboard()
    )


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


def back_home_btn():
    return [[InlineKeyboardButton("🏠 Home", callback_data="home")]]


async def send_or_edit(update: Update, text: str, keyboard, parse_mode="Markdown"):
    """Edit existing message if callback, else send new."""
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=parse_mode, reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text, parse_mode=parse_mode, reply_markup=keyboard
        )
