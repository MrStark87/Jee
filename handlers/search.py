"""
handlers/search.py
/search {title} — searches across silly, error, important memories
Returns inline Answer & Key Points button where applicable.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_conn

MEM_LABELS = {
    "silly":     "🤦 Silly",
    "error":     "❌ Error",
    "important": "⭐ Important",
}


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "ℹ️ Usage: `/search <title>`\nExample: `/search q1` ya `/search optics mistake`",
            parse_mode="Markdown"
        )
        return

    query_str = " ".join(context.args).strip().lower()

    conn    = get_conn()
    results = conn.execute("""
        SELECT * FROM memories
        WHERE user_id=? AND LOWER(title) LIKE ?
        ORDER BY created DESC
        LIMIT 10
    """, (uid, f"%{query_str}%")).fetchall()
    conn.close()

    if not results:
        await update.message.reply_text(
            f"🔍 *\"{query_str}\"* — koi result nahi mila.\n\nTitle exact match hona chahiye.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"🔍 *{len(results)} result(s)* for `{query_str}`",
        parse_mode="Markdown"
    )

    for e in results:
        label = MEM_LABELS.get(e["mem_type"], e["mem_type"])
        header = f"{label} — *{e['title']}*\n_{e['created'][:10]}_"

        content_text = e["content"] or ""
        body = f"{header}\n\n{content_text}" if content_text else header

        btns = []
        if e["mem_type"] in ("error", "important") and (e["answer"] or e["ans_file"] or e["keypoints"]):
            btns.append(InlineKeyboardButton("💡 Answer & Key Points", callback_data=f"mem_ans_{e['id']}"))

        kb = InlineKeyboardMarkup([btns]) if btns else None

        if e["file_id"]:
            if e["file_type"] == "photo":
                await update.message.reply_photo(
                    e["file_id"], caption=body, parse_mode="Markdown", reply_markup=kb
                )
            else:
                await update.message.reply_document(
                    e["file_id"], caption=body, parse_mode="Markdown", reply_markup=kb
                )
        else:
            await update.message.reply_text(body, parse_mode="Markdown", reply_markup=kb)
