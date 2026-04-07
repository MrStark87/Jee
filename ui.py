"""
ui.py — Centralized keyboards, emojis, and message builders.
All UI strings are in English (bot official language).
"""

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb
import datetime

# ── Emoji constants ────────────────────────────────────────────
E = {
    "home":      "🏠",
    "back":      "◀️",
    "next":      "▶️",
    "add":       "➕",
    "see":       "👁",
    "edit":      "✏️",
    "delete":    "🗑",
    "done":      "✅",
    "undone":    "⬜",
    "cancel":    "✖️",
    "confirm":   "⚠️",
    "task":      "📋",
    "lecture":   "📚",
    "timer":     "⏱",
    "memory":    "🧠",
    "silly":     "🤦",
    "error":     "❌",
    "imp":       "⭐",
    "report":    "📓",
    "formula":   "📐",
    "motiv":     "🔥",
    "thought":   "💭",
    "admin":     "⚙️",
    "streak":    "🔥",
    "search":    "🔍",
    "doubt":     "❓",
    "test":      "📊",
    "syllabus":  "📑",
    "revision":  "🔁",
    "broadcast": "📢",
    "ban":       "🚫",
    "star":      "✨",
    "lock":      "🔐",
    "calendar":  "📅",
    "check":     "☑️",
    "warn":      "⚠️",
    "link":      "🔗",
    "up":        "⬆️",
    "clock":     "🕐",
}


# ── Shared small keyboards ─────────────────────────────────────

def back_home():
    return Kb([[Btn(f"{E['home']} Home", callback_data="home")]])

def back_btn(cb: str):
    return [[Btn(f"{E['back']} Back", callback_data=cb)]]

def cancel_btn(cb: str):
    return Kb([[Btn(f"{E['cancel']} Cancel", callback_data=cb)]])

def confirm_delete_kb(yes_cb: str, no_cb: str):
    return Kb([[
        Btn("Yes, delete", callback_data=yes_cb),
        Btn(f"{E['cancel']} No, keep it", callback_data=no_cb),
    ]])

def nav_kb(section: str, idx: int, total: int, extra_rows=None):
    """Navigation row: Prev | N/Total | Next"""
    nav = []
    if idx > 0:
        nav.append(Btn(f"{E['back']} Prev", callback_data=f"{section}_{idx-1}"))
    nav.append(Btn(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav.append(Btn(f"Next {E['next']}", callback_data=f"{section}_{idx+1}"))
    rows = [nav]
    if extra_rows:
        rows.extend(extra_rows)
    return Kb(rows)


# ── Home keyboard ──────────────────────────────────────────────

def home_kb():
    return Kb([
        [Btn(f"{E['task']} Today",      callback_data="today_home"),
         Btn(f"{E['memory']} Memories", callback_data="mem_home")],
        [Btn(f"{E['formula']} Formulas",callback_data="formula_home"),
         Btn(f"{E['thought']} Thoughts",callback_data="thought_home")],
        [Btn(f"{E['motiv']} Motivation",callback_data="motiv_home"),
         Btn(f"{E['admin']} Admin",     callback_data="admin_home")],
    ])


# ── Welcome message ────────────────────────────────────────────

def welcome_text(name: str, streak: int) -> str:
    today = datetime.date.today().strftime("%A, %d %B %Y")
    streak_line = f"{E['streak']} Streak: *{streak} day{'s' if streak != 1 else ''}*" if streak > 0 else f"{E['streak']} Start your streak today!"
    return (
        f"{E['star']} *JEE Saarthi*\n"
        f"Welcome back, *{name}*!\n\n"
        f"{E['calendar']} {today}\n"
        f"{streak_line}\n\n"
        f"_Consistency beats intensity. Keep going._\n\n"
        f"Choose a section below {E['down'] if 'down' in E else '👇'}"
    )


# ── Today section ──────────────────────────────────────────────

def today_home_kb():
    return Kb([
        [Btn(f"{E['add']} Add Task",     callback_data="task_add"),
         Btn(f"{E['check']} My Tasks",   callback_data="task_list")],
        [Btn(f"{E['add']} Add Lecture",  callback_data="lec_add"),
         Btn(f"{E['lecture']} Lectures", callback_data="lec_list")],
        [Btn(f"{E['timer']} Focus Timer",callback_data="timer_menu"),
         Btn(f"{E['test']} Test Scores", callback_data="scores_home")],
        [Btn(f"{E['doubt']} Doubts",     callback_data="doubts_home"),
         Btn(f"{E['revision']} Revisions",callback_data="revision_home")],
        back_btn("home")[0],
    ])


# ── Memory section ─────────────────────────────────────────────

def mem_home_kb():
    return Kb([
        [Btn(f"{E['silly']} Silly",     callback_data="mem_silly_home"),
         Btn(f"{E['error']} Error",     callback_data="mem_error_home")],
        [Btn(f"{E['imp']} Important",   callback_data="mem_imp_home"),
         Btn(f"{E['report']} Daily Log",callback_data="mem_report_home")],
        back_btn("home")[0],
    ])


# ── Subject picker ─────────────────────────────────────────────

def subject_kb(prefix: str):
    return Kb([
        [Btn("PHY",   callback_data=f"{prefix}_PHY"),
         Btn("CHEM",  callback_data=f"{prefix}_CHEM"),
         Btn("MATH",  callback_data=f"{prefix}_MATH")],
        [Btn("BIO",   callback_data=f"{prefix}_BIO"),
         Btn("OTHER", callback_data=f"{prefix}_OTHER")],
    ])


# ── Timer keyboard ─────────────────────────────────────────────

def timer_kb():
    return Kb([
        [Btn("25 min — Pomodoro", callback_data="timer_25"),
         Btn("50 min — Deep Work", callback_data="timer_50")],
        [Btn("15 min — Quick",    callback_data="timer_15"),
         Btn(f"{E['edit']} Custom",callback_data="timer_custom")],
        back_btn("today_home")[0],
    ])


# ── Divider text ───────────────────────────────────────────────

DIVIDER = "─" * 20
