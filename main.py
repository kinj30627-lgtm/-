import os
import sqlite3

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8715955198:AAFg_ik2I9IwbKBFK1en71e4Hsb7WRMQZEo").strip()
DB_PATH = "promo.db"

raw_admin_ids = os.getenv("ADMIN_IDS", "8521145131")
ADMIN_IDS = {
    int(x.strip()) for x in raw_admin_ids.split(",")
    if x.strip().isdigit()
}


def is_admin(user_id: int | None) -> bool:
    return user_id in ADMIN_IDS if user_id is not None else False


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS target_chats (
            chat_id TEXT PRIMARY KEY,
            title TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_post(text: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (text) VALUES (?)", (text,))
    conn.commit()
    post_id = cur.lastrowid
    conn.close()
    return post_id


def get_posts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM posts ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_post(post_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM posts WHERE id = ?", (post_id,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_post(post_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def add_target_chat(chat_id: str, title: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO target_chats (chat_id, title) VALUES (?, ?)",
        (chat_id, title)
    )
    conn.commit()
    conn.close()


def remove_target_chat(chat_id: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM target_chats WHERE chat_id = ?", (chat_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def get_target_chats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id, title FROM target_chats ORDER BY title ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_first_post():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM posts ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row


async def send_post_to_chat(context: ContextTypes.DEFAULT_TYPE, post_id: int, chat_id: str):
    row = get_post(post_id)
    if not row:
        raise ValueError("존재하지 않는 글ID")

    _, text = row
    await context.bot.send_message(chat_id=chat_id, text=text)


async def scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE):
    if context.bot_data.get("paused"):
        return

    post = get_first_post()
    if not post:
        return

    post_id, text = post
    targets = get_target_chats()

    for chat_id, _title in targets:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            print(f"[scheduled_broadcast] send fail {chat_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    await update.message.reply_text(
        "사용 가능 명령어:\n"
        "/addpost 내용\n"
        "/listposts\n"
        "/deletepost 글ID\n"
        "/now 글ID\n"
        "/enablepromo\n"
        "/disablepromo\n"
        "/listtargets\n"
        "/pause\n"
        "/resume\n"
        "/help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def addpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    text = update.message.text.replace("/addpost", "", 1).strip()

    if not text:
        await update.message.reply_text("형식:\n/addpost 홍보할내용")
        return

    post_id = save_post(text)
    await update.message.reply_text(f"저장 완료: 글 ID {post_id}")


async def listposts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    rows = get_posts()
    if not rows:
        await update.message.reply_text("저장된 홍보글 없음")
        return

    chunks = []
    for post_id, text in rows:
        preview = text[:120]
        chunks.append(f"[{post_id}]\n{preview}")

    msg = "\n\n".join(chunks)
    await update.message.reply_text(msg[:4000])


async def deletepost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    if not context.args:
        await update.message.reply_text("/deletepost 글ID")
        return

    try:
        post_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("글ID는 숫자여야 함")
        return

    deleted = delete_post(post_id)
    if deleted:
        await update.message.reply_text("삭제 완료")
    else:
        await update.message.reply_text("해당 글ID 없음")


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    if not context.args:
        await update.message.reply_text("/now 글ID")
        return

    try:
        post_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("글ID는 숫자여야 함")
        return

    chat_id = str(update.effective_chat.id)

    try:
        await send_post_to_chat(context, post_id, chat_id)
        await update.message.reply_text("즉시 발송 완료")
    except Exception as e:
        await update.message.reply_text(f"발송 실패: {e}")


async def enablepromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    chat = update.effective_chat
    title = chat.title or update.effective_user.full_name or "private_chat"
    add_target_chat(str(chat.id), title)

    await update.message.reply_text("이 방을 1시간 자동홍보 대상에 등록했어요.")


async def disablepromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    chat_id = str(update.effective_chat.id)
    deleted = remove_target_chat(chat_id)

    if deleted:
        await update.message.reply_text("이 방 자동홍보 해제 완료")
    else:
        await update.message.reply_text("이 방은 등록되어 있지 않아요.")


async def listtargets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    rows = get_target_chats()
    if not rows:
        await update.message.reply_text("등록된 자동홍보 대상 방 없음")
        return

    msg = "\n\n".join([f"{title}\n{chat_id}" for chat_id, title in rows])
    await update.message.reply_text(msg[:4000])


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    context.bot_data["paused"] = True
    await update.message.reply_text("자동홍보 일시정지")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id if update.effective_user else None):
        return

    context.bot_data["paused"] = False
    await update.message.reply_text("자동홍보 재개")


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN이 비어있음")

    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addpost", addpost))
    app.add_handler(CommandHandler("listposts", listposts))
    app.add_handler(CommandHandler("deletepost", deletepost_command))
    app.add_handler(CommandHandler("now", now))
    app.add_handler(CommandHandler("enablepromo", enablepromo))
    app.add_handler(CommandHandler("disablepromo", disablepromo))
    app.add_handler(CommandHandler("listtargets", listtargets))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))

    app.job_queue.run_repeating(
        scheduled_broadcast,
        interval=3600,
        first=10,
        name="promo_repeat",
    )

    app.run_polling()


if __name__ == "__main__":
    main()
