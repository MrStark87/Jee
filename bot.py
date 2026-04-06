"""
JEE Saarthi Bot — Complete Bot
================================
Run: python bot.py
Requires: pip install python-telegram-bot apscheduler
"""

import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram import Update

from config import BOT_TOKEN, ADMIN_ID
from database import init_db
from handlers import today, memories, formulas, motivation, thought, admin, search, common

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Core commands ──────────────────────────────────────────
    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("search", search.search_cmd))

    # ── Today section conversation ─────────────────────────────
    app.add_handler(today.get_conversation_handler())

    # ── Memories section conversation ──────────────────────────
    app.add_handler(memories.get_conversation_handler())

    # ── Formulas section conversation ──────────────────────────
    app.add_handler(formulas.get_conversation_handler())

    # ── Motivation section conversation ────────────────────────
    app.add_handler(motivation.get_conversation_handler())

    # ── Thought section conversation ───────────────────────────
    app.add_handler(thought.get_conversation_handler())

    # ── Admin section conversation ─────────────────────────────
    app.add_handler(admin.get_conversation_handler())

    # ── Fallback callback handler (home buttons etc.) ──────────
    app.add_handler(CallbackQueryHandler(common.home_callback, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(common.noop, pattern="^noop$"))

    # ── Scheduler for daily reminders & lecture alerts ─────────
    from scheduler import setup_scheduler
    setup_scheduler(app)

    logger.info("JEE Saarthi Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
