"""
handlers/search.py
/search <title> — searches across:
  - Silly, Error, Important memories
  - Daily reports (search by date e.g. "2025-04-07")
  - Formula chapters
"""
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
from telegram.ext import ContextTypes
from database import get_conn
from ui import E, DIVIDER

MEM_LABELS = {
    "silly":     f"{E['silly']} Silly",
    "error":     f"{E['error']} Error",
    "important": f"{E['imp']} Important",
}


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            f"{E['search']} *Search*\n\nUsage: `/search <title>`\n\n"
            "Examples:\n"
            "`/search q1` — find memory titled q1\n"
            "`/search 2025-04-07` — find that day's report\n"
            "`/search wave optics` — find any entry",
            parse_mode="Markdown"
        )
        return

    q = " ".join(context.args).strip().lower()

    conn = get_conn()

    # Search memories
    memories = conn.execute("""
        SELECT * FROM memories
        WHERE user_id=? AND LOWER(title) LIKE ?
        ORDER BY created DESC LIMIT 10
    """, (uid, f"%{q}%")).fetchall()

    # Search daily reports
    reports = conn.execute("""
        SELECT * FROM daily_reports
        WHERE user_id=? AND (LOWER(date) LIKE ? OR LOWER(content) LIKE ?)
        ORDER BY date DESC LIMIT 5
    """, (uid, f"%{q}%", f"%{q}%")).fetchall()

    # Search formula chapters (shared)
    formulas = conn.execute("""
        SELECT DISTINCT chapter, class_num FROM formulas
        WHERE LOWER(chapter) LIKE ?
        ORDER BY chapter LIMIT 5
    """, (f"%{q}%",)).fetchall()

    conn.close()

    total = len(memories) + len(reports) + len(formulas)
    if total == 0:
        await update.message.reply_text(
            f"{E['search']} No results for `{q}`.\n\nTip: Title must partially match.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"{E['search']} *{total} result(s)* for `{q}`",
        parse_mode="Markdown"
    )

    # Send memory results
    for e in memories:
        label = MEM_LABELS.get(e["mem_type"], e["mem_type"])
        hdr   = f"{label}\n📌 *{e['title']}*\n_{e['created'][:10]}_"
        body  = f"{hdr}\n\n{e['content']}" if e["content"] else hdr
        btns  = []
        if e["mem_type"] in ("error","important") and (e["answer"] or e["keypoints"]):
            btns = [[Btn("💡 Answer & Key Points", callback_data=f"mem_ans_{e['id']}")]]

        if e["file_id"]:
            send = update.message.reply_photo if e["file_type"] == "photo" else update.message.reply_document
            await send(e["file_id"], caption=body, parse_mode="Markdown",
                       reply_markup=Kb(btns) if btns else None)
        else:
            await update.message.reply_text(body, parse_mode="Markdown",
                                             reply_markup=Kb(btns) if btns else None)

    # Send report results
    for r in reports:
        hdr  = f"{E['report']} *Daily Log — {r['date']}*\n{DIVIDER}"
        body = f"{hdr}\n{r['content']}" if r["content"] else hdr
        if r["file_id"]:
            send = update.message.reply_photo if r["file_type"] == "photo" else update.message.reply_document
            await send(r["file_id"], caption=body, parse_mode="Markdown")
        else:
            await update.message.reply_text(body, parse_mode="Markdown")

    # Send formula results
    for f in formulas:
        kb = Kb([[Btn(f"Open {f['chapter']}", callback_data=f"fch_{f['class_num']}_{f['chapter']}")]])
        await update.message.reply_text(
            f"{E['formula']} *{f['chapter']}* — Class {f['class_num']}",
            parse_mode="Markdown", reply_markup=kb
        )
