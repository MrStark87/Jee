"""
bot.py — JEE Saarthi Bot entry point
Run: python bot.py
"""
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from config import BOT_TOKEN
from database import init_db
from handlers import common, today, memories, formulas, motivation, thought, admin, search
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Commands ───────────────────────────────────────────────
    app.add_handler(CommandHandler("start",  common.start))
    app.add_handler(CommandHandler("search", search.search_cmd))
    app.add_handler(CommandHandler("ban",    common.ban_user))
    app.add_handler(CommandHandler("unban",  common.unban_user))

    # ── Section conversations ──────────────────────────────────
    app.add_handler(today.get_conversation_handler())
    app.add_handler(memories.get_conversation_handler())
    app.add_handler(formulas.get_conversation_handler())
    app.add_handler(motivation.get_conversation_handler())
    app.add_handler(thought.get_conversation_handler())
    app.add_handler(admin.get_conversation_handler())

    # ── Global fallback callbacks ──────────────────────────────
    app.add_handler(CallbackQueryHandler(common.home_callback, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(common.noop,         pattern="^noop$"))

    # ── Scheduler ─────────────────────────────────────────────
    setup_scheduler(app)

    logger.info("JEE Saarthi Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
