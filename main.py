import os
import json
import random
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8715955198:AAFg_ik2I9IwbKBFK1en71e4Hsb7WRMQZEo").strip()
DATA_FILE = "baccarat_data.json"
START_BALANCE = 100000
CHAT_BONUS_CHANCE = 0.05
CHAT_BONUS_AMOUNT = 50000


SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

CARD_VALUES = {
    "A": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 0,
    "J": 0,
    "Q": 0,
    "K": 0,
}


def create_shoe():
    shoe = []
    for _ in range(8):  # 8덱
        for suit in SUITS:
            for rank in RANKS:
                shoe.append({"rank": rank, "suit": suit})
    random.shuffle(shoe)
    return shoe


def load_data():
    if not Path(DATA_FILE).exists():
        return {
            "users": {},
            "bets": {},
            "history": [],
            "shoe": create_shoe(),
        }

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_user(data, user):
    user_id = str(user.id)
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": user.full_name,
            "balance": START_BALANCE,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "chat_bonus_count": 0,
        }
    else:
        data["users"][user_id]["name"] = user.full_name
    return user_id


def draw_card(data):
    if len(data["shoe"]) < 20:
        data["shoe"] = create_shoe()

    return data["shoe"].pop()


def card_to_text(card):
    return f"{card['rank']}{card['suit']}"


def baccarat_value(cards):
    total = sum(CARD_VALUES[c["rank"]] for c in cards) % 10
    return total


def third_card_value(card):
    if not card:
        return None
    return CARD_VALUES[card["rank"]]


def play_baccarat_round(data):
    player = [draw_card(data), draw_card(data)]
    banker = [draw_card(data), draw_card(data)]

    p_total = baccarat_value(player)
    b_total = baccarat_value(banker)

    # 내추럴
    if p_total in [8, 9] or b_total in [8, 9]:
        return finalize_round(player, banker)

    player_third = None

    # 플레이어 3장 규칙
    if p_total <= 5:
        player_third = draw_card(data)
        player.append(player_third)

    p_total = baccarat_value(player)
    b_total = baccarat_value(banker)

    # 뱅커 3장 규칙
    if player_third is None:
        if b_total <= 5:
            banker.append(draw_card(data))
    else:
        ptv = third_card_value(player_third)
        if b_total <= 2:
            banker.append(draw_card(data))
        elif b_total == 3 and ptv != 8:
            banker.append(draw_card(data))
        elif b_total == 4 and ptv in [2, 3, 4, 5, 6, 7]:
            banker.append(draw_card(data))
        elif b_total == 5 and ptv in [4, 5, 6, 7]:
            banker.append(draw_card(data))
        elif b_total == 6 and ptv in [6, 7]:
            banker.append(draw_card(data))

    return finalize_round(player, banker)


def finalize_round(player, banker):
    p_total = baccarat_value(player)
    b_total = baccarat_value(banker)

    if p_total > b_total:
        winner = "p"
        label = "플레이어"
    elif b_total > p_total:
        winner = "b"
        label = "뱅커"
    else:
        winner = "t"
        label = "타이"

    return {
        "player_cards": player,
        "banker_cards": banker,
        "player_total": p_total,
        "banker_total": b_total,
        "winner": winner,
        "winner_label": label,
    }


def payout_amount(side, amount):
    if side == "p":
        return int(amount * 2.0)
    if side == "b":
        return int(amount * 1.95)
    if side == "t":
        return int(amount * 8.0)
    return 0


def side_label(side):
    return {"p": "플레이어", "b": "뱅커", "t": "타이"}.get(side, "알수없음")


def result_text(round_data):
    p_cards = " ".join(card_to_text(c) for c in round_data["player_cards"])
    b_cards = " ".join(card_to_text(c) for c in round_data["banker_cards"])

    return (
        f"🎴 결과 공개\n\n"
        f"플레이어: {p_cards}\n"
        f"합계: {round_data['player_total']}\n\n"
        f"뱅커: {b_cards}\n"
        f"합계: {round_data['banker_total']}\n\n"
        f"승리: {round_data['winner_label']}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    ensure_user(data, update.effective_user)
    save_data(data)

    await update.message.reply_text(
        "🎰 데모 바카라 봇\n\n"
        "기본 포인트: 100000\n"
        "채팅 시 5% 확률로 50000 포인트 지급\n\n"
        "명령어:\n"
        "/balance - 내 포인트\n"
        "/bet p 금액 - 플레이어 베팅\n"
        "/bet b 금액 - 뱅커 베팅\n"
        "/bet t 금액 - 타이 베팅\n"
        "/draw - 결과 공개\n"
        "/history - 최근 결과\n"
        "/shoe - 남은 카드 수\n"
        "/rank - 랭킹\n"
        "/help - 도움말"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = ensure_user(data, update.effective_user)
    save_data(data)

    bal = data["users"][user_id]["balance"]
    await update.message.reply_text(f"💰 현재 포인트: {bal:,}")


async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = ensure_user(data, update.effective_user)

    if len(context.args) != 2:
        await update.message.reply_text("형식: /bet p 10000  또는 /bet b 10000  또는 /bet t 5000")
        return

    side = context.args[0].lower().strip()
    if side not in ["p", "b", "t"]:
        await update.message.reply_text("베팅 방향은 p, b, t 중 하나여야 해.")
        return

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("금액은 숫자로 입력해.")
        return

    if amount <= 0:
        await update.message.reply_text("금액은 1 이상이어야 해.")
        return

    balance_now = data["users"][user_id]["balance"]
    if amount > balance_now:
        await update.message.reply_text(f"포인트 부족. 현재 잔액: {balance_now:,}")
        return

    data["users"][user_id]["balance"] -= amount
    data["bets"][user_id] = {
        "side": side,
        "amount": amount,
        "name": update.effective_user.full_name,
    }
    save_data(data)

    await update.message.reply_text(
        f"✅ 베팅 완료\n"
        f"선택: {side_label(side)}\n"
        f"금액: {amount:,}\n"
        f"남은 포인트: {data['users'][user_id]['balance']:,}"
    )


async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not data["bets"]:
        await update.message.reply_text("현재 베팅이 없어. 먼저 /bet 명령어로 베팅해.")
        return

    round_data = play_baccarat_round(data)
    winner = round_data["winner"]

    lines = [result_text(round_data), "", "📋 정산 결과"]

    for user_id, bet_info in list(data["bets"].items()):
        if user_id not in data["users"]:
            continue

        amount = bet_info["amount"]
        side = bet_info["side"]
        name = bet_info["name"]

        if side == winner:
            reward = payout_amount(side, amount)
            data["users"][user_id]["balance"] += reward
            data["users"][user_id]["wins"] += 1
            profit = reward - amount
            lines.append(f"✅ {name}: 적중 (+{profit:,}) / 현재 {data['users'][user_id]['balance']:,}")
        else:
            data["users"][user_id]["losses"] += 1
            if winner == "t":
                data["users"][user_id]["ties"] += 1
            lines.append(f"❌ {name}: 미적중 (-{amount:,}) / 현재 {data['users'][user_id]['balance']:,}")

    data["history"].append(
        {
            "winner": round_data["winner"],
            "winner_label": round_data["winner_label"],
            "player_total": round_data["player_total"],
            "banker_total": round_data["banker_total"],
        }
    )
    data["history"] = data["history"][-20:]
    data["bets"] = {}
    save_data(data)

    await update.message.reply_text("\n".join(lines)[:4096])


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    hist = data["history"][-10:]

    if not hist:
        await update.message.reply_text("최근 결과가 없어.")
        return

    text = ["🕘 최근 결과"]
    for i, item in enumerate(reversed(hist), start=1):
        text.append(
            f"{i}. {item['winner_label']} "
            f"(플 {item['player_total']} : 뱅 {item['banker_total']})"
        )

    await update.message.reply_text("\n".join(text))


async def shoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    remain = len(data["shoe"])

    counter = Counter(card["rank"] for card in data["shoe"])
    text = [f"🃏 남은 카드 수: {remain}장", ""]
    text.append("남은 랭크 분포:")
    for rank in RANKS:
        text.append(f"{rank}: {counter.get(rank, 0)}")

    await update.message.reply_text("\n".join(text)[:4096])


async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    users = list(data["users"].values())

    if not users:
        await update.message.reply_text("랭킹 데이터가 없어.")
        return

    users.sort(key=lambda x: x["balance"], reverse=True)

    lines = ["🏆 포인트 랭킹"]
    for i, user in enumerate(users[:10], start=1):
        lines.append(f"{i}. {user['name']} - {user['balance']:,}")

    await update.message.reply_text("\n".join(lines))


async def on_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or update.message.text.startswith("/"):
        return

    data = load_data()
    user_id = ensure_user(data, update.effective_user)

    if random.random() < CHAT_BONUS_CHANCE:
        data["users"][user_id]["balance"] += CHAT_BONUS_AMOUNT
        data["users"][user_id]["chat_bonus_count"] += 1
        save_data(data)

        await update.message.reply_text(
            f"🎁 랜덤 보너스!\n"
            f"{CHAT_BONUS_AMOUNT:,} 포인트 지급\n"
            f"현재 포인트: {data['users'][user_id]['balance']:,}"
        )
    else:
        save_data(data)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN이 비어있음")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("bet", bet))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("shoe", shoe))
    app.add_handler(CommandHandler("rank", rank))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_chat))

    app.run_polling()


if __name__ == "__main__":
    main()
