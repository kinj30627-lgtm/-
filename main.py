import os
import sqlite3
from datetime import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {8521145131}  # 네 텔레그램 숫자 ID로 바꿔

DB_PATH = "promo.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            text TEXT NOT NULL,
            button_text TEXT,
            button_url TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "사용 가능 명령어:\n"
        "/addpost 채널아이디 | 내용 | 버튼문구 | 버튼URL\n"
        "/listposts\n"
        "/deletepost 글ID\n"
        "/now 글ID\n"
        "/pause\n"
        "/resume"
    )


async def addpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return

    raw = update.message.text.replace("/addpost", "", 1).strip()
    parts = [x.strip() for x in raw.split("|")]

    if len(parts) < 2:
        await update.message.reply_text(
            "형식:\n/addpost 채널아이디 | 내용 | 버튼문구 | 버튼URL"
        )
        return

    channel_id = parts[0]
    text = parts[1]
    button_text = parts[2] if len(parts) > 2 and parts[2] else None
    button_url = parts[3] if len(parts) > 3 and parts[3] else None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO posts (channel_id, text, button_text, button_url) VALUES (?, ?, ?, ?)",
        (channel_id, text, button_text, button_url),
    )
    conn.commit()
    post_id = cur.lastrowid
    conn.close()

    await update.message.reply_text(f"저장 완료: 글 ID {post_id}")


async def listposts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, channel_id, text FROM posts ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("저장된 홍보글 없음")
        return

    msg = "\n\n".join(
        [f"[{row[0]}] {row[1]}\n{row[2][:80]}" for row in rows]
    )
    await update.message.reply_text(msg[:4000])


async def deletepost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/deletepost 글ID")
        return

    post_id = context.args[0]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted:
        await update.message.reply_text("삭제 완료")
    else:
        await update.message.reply_text("해당 글ID 없음")


async def send_post_by_id(context: ContextTypes.DEFAULT_TYPE, post_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT channel_id, text, button_text, button_url FROM posts WHERE id = ?",
        (post_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return

    channel_id, text, button_text, button_url = row
    reply_markup = None

    if button_text and button_url:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(button_text, url=button_url)]]
        )

    await context.bot.send_message(
        chat_id=channel_id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=False,
    )


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/now 글ID")
        return

    post_id = int(context.args[0])

    try:
        await send_post_by_id(context, post_id)
        await update.message.reply_text("즉시 발송 완료")
    except Exception as e:
        await update.message.reply_text(f"발송 실패: {e}")


async def scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE):
    if context.bot_data.get("paused"):
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM posts ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if not row:
        return

    post_id = row[0]

    try:
        await send_post_by_id(context, post_id)
    except Exception as e:
        print("scheduled_broadcast error:", e)


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    context.bot_data["paused"] = True
    await update.message.reply_text("자동 홍보 일시정지")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    context.bot_data["paused"] = False
    await update.message.reply_text("자동 홍보 재개")


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpost", addpost))
    app.add_handler(CommandHandler("listposts", listposts))
    app.add_handler(CommandHandler("deletepost", deletepost))
    app.add_handler(CommandHandler("now", now))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))

    # 매일 오전 10시 자동 발송 예시
    app.job_queue.run_daily(
        scheduled_broadcast,
        time=time(hour=10, minute=0, second=0),
        name="daily_promo",
    )

    app.run_polling()


if __name__ == "__main__":
    main()
