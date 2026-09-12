# -*- coding: utf-8 -*-
"""
بات قیمت لحظه‌ای طلای تتری (XAUT) و رمزارزهای معروف برای سروش‌پلاس
(نسخه سبک)
--------------------------------------------------------------------------
این نسخه فقط از کتابخانه `requests` استفاده می‌کند و مستقیم با HTTP API
بات سروش‌پلاس صحبت می‌کند (بدون aiosplus/pydantic).

همه‌ی قیمت‌ها از یک منبع عمومی و بدون نیاز به کلید گرفته می‌شوند:
API عمومیِ آمار بازار نوبیتکس (Nobitex) - endpoint: /market/stats

نصب:
    pip install requests

اجرا:
    python price_bot_lite.py
"""

import json
import logging
import time
from datetime import datetime

import requests

# ============================ تنظیمات ============================

BOT_TOKEN = "69896472:tp2llzJ_BXZqA9QYQUxLpJ7kESw8VayiIkw"

# پایه آدرس API سروش‌پلاس
BASE_URL = f"https://api.splus.ir/bot{BOT_TOKEN}"

# API عمومیِ آمار بازار نوبیتکس - نیازی به کلید ندارد
NOBITEX_STATS_URL = "https://apiv2.nobitex.ir/market/stats"

RAW_DEBUG = False  # برای دیباگ اولیه True کن تا خروجی خام API چاپ شود

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("soroush-price-bot-lite")

# ============================ تعریف دارایی‌ها ============================
#
# همه از نوبیتکس، جفت‌ارز به ریال (rls) گرفته می‌شوند.

ASSETS = {
    "gold_xaut": {
        "title": "طلای تتری (XAUT)", "short": "طلا (XAUT)", "emoji": "🥇",
        "nobitex_symbol": "xaut-rls",
    },
    "btc": {
        "title": "بیت‌کوین", "short": "بیت‌کوین", "emoji": "₿",
        "nobitex_symbol": "btc-rls",
    },
    "eth": {
        "title": "اتریوم", "short": "اتریوم", "emoji": "⧫",
        "nobitex_symbol": "eth-rls",
    },
    "usdt": {
        "title": "تتر", "short": "تتر", "emoji": "💰",
        "nobitex_symbol": "usdt-rls",
    },
    "trx": {
        "title": "ترون", "short": "ترون", "emoji": "🔺",
        "nobitex_symbol": "trx-rls",
    },
    "bnb": {
        "title": "بایننس کوین", "short": "بایننس کوین", "emoji": "🟡",
        "nobitex_symbol": "bnb-rls",
    },
    "xrp": {
        "title": "ریپل", "short": "ریپل", "emoji": "💧",
        "nobitex_symbol": "xrp-rls",
    },
    "doge": {
        "title": "دوج‌کوین", "short": "دوج‌کوین", "emoji": "🐕",
        "nobitex_symbol": "doge-rls",
    },
    "ada": {
        "title": "کاردانو", "short": "کاردانو", "emoji": "🔷",
        "nobitex_symbol": "ada-rls",
    },
    "ton": {
        "title": "گرام (GRAM)", "short": "گرام", "emoji": "💎",
        "nobitex_symbol": "gram-rls",
    },
    "sol": {
        "title": "سولانا", "short": "سولانا", "emoji": "🟣",
        "nobitex_symbol": "sol-rls",
    },
    "ltc": {
        "title": "لایت‌کوین", "short": "لایت‌کوین", "emoji": "⚪",
        "nobitex_symbol": "ltc-rls",
    },
}


# ============================ ابزارهای قیمت ============================

def _to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_prices():
    """
    یک درخواست به نوبیتکس برای همه‌ی نمادهای تعریف‌شده در ASSETS.
    """
    symbols = ",".join(cfg["nobitex_symbol"].split("-")[0] for cfg in ASSETS.values())
    resp = requests.get(
        NOBITEX_STATS_URL,
        params={"srcCurrency": symbols, "dstCurrency": "rls"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if RAW_DEBUG:
        log.info("RAW Nobitex response: %s", data)
    return data


def format_price_message(asset_key, data):
    cfg = ASSETS[asset_key]

    stats = data.get("stats", {}) if isinstance(data, dict) else {}
    item = stats.get(cfg["nobitex_symbol"])

    if not item:
        return f"{cfg['emoji']} متأسفانه قیمت «{cfg['title']}» الان در دسترس نیست.\nچند لحظه دیگر دوباره امتحان کن."

    price_val = _to_float(item.get("latest") or item.get("bestSell") or item.get("bestBuy"))
    change_val = _to_float(item.get("dayChange"))

    lines = [f"{cfg['emoji']} {cfg['title']}", ""]

    if price_val is not None:
        rial, toman = price_val, price_val / 10
        lines.append(f"🔹 قیمت لحظه‌ای: {rial:,.0f} ریال")
        lines.append(f"   ({toman:,.0f} تومان)")

        # معادل دلاری: چون نوبیتکس نرخ رسمی دلار نمی‌ده، از قیمت تتر به
        # ریال (usdt-rls) به‌عنوان نرخ تقریبی دلار استفاده می‌کنیم.
        usdt_item = stats.get("usdt-rls")
        usd_rate = _to_float(usdt_item.get("latest") or usdt_item.get("bestSell")) if usdt_item else None
        if usd_rate and asset_key != "usdt":
            usd_equiv = price_val / usd_rate
            lines.append(f"💲 معادل دلاری: {usd_equiv:,.2f} $")
    else:
        lines.append("🔹 قیمت لحظه‌ای: نامشخص")

    if change_val is not None:
        arrow = "🟢 رشد" if change_val > 0 else ("🔴 افت" if change_val < 0 else "⚪️ بدون تغییر")
        lines.append(f"📊 تغییر ۲۴ ساعت اخیر: {change_val:+.2f}٪ ({arrow})")
    else:
        lines.append("📊 تغییر ۲۴ ساعت اخیر: نامشخص")

    lines.append(f"🕒 به‌روزرسانی: {datetime.now().strftime('%H:%M:%S')}")
    return "\n".join(lines)


# ============================ کیبوردها (JSON خام) ============================

def main_menu_kb():
    row = [{"text": f"{cfg['emoji']} {cfg['short']}", "callback_data": f"price:{key}"}
           for key, cfg in ASSETS.items()]
    rows = [row[i:i + 2] for i in range(0, len(row), 2)]
    return {"inline_keyboard": rows}


def asset_kb(asset_key):
    return {
        "inline_keyboard": [[
            {"text": "🔄 به‌روزرسانی", "callback_data": f"price:{asset_key}"},
            {"text": "🔙 بازگشت به منو", "callback_data": "menu"},
        ]]
    }


# ============================ توابع خام API سروش‌پلاس ============================

def api_call(method, payload=None):
    url = f"{BASE_URL}/{method}"
    resp = requests.post(url, json=payload or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return api_call("sendMessage", payload)


def edit_message_text(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return api_call("editMessageText", payload)


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return api_call("answerCallbackQuery", payload)


def get_updates(offset=None, timeout=30):
    payload = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    return api_call("getUpdates", payload)


# ============================ منطق اصلی بات ============================

def handle_update(update):
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        if text and text.startswith("/start"):
            send_message(
                chat_id,
                "سلام 👋\nیکی از گزینه‌های زیر رو بزن تا قیمت لحظه‌ای‌شو با آمار ۲۴ ساعت اخیر ببینی:",
                reply_markup=main_menu_kb(),
            )
        return

    if "callback_query" in update:
        cq = update["callback_query"]
        cq_id = cq["id"]
        data = cq.get("data", "")
        message = cq["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        if data == "menu":
            answer_callback_query(cq_id)
            edit_message_text(
                chat_id, message_id,
                "یکی از گزینه‌های زیر رو بزن تا قیمت لحظه‌ای‌شو ببینی:",
                reply_markup=main_menu_kb(),
            )
            return

        if data.startswith("price:"):
            asset_key = data.split(":", 1)[1]
            answer_callback_query(cq_id, "در حال دریافت قیمت...")
            try:
                prices = fetch_prices()
                text = format_price_message(asset_key, prices)
            except Exception:
                log.exception("خطا در دریافت قیمت از نوبیتکس")
                text = "⚠️ خطا در دریافت قیمت. لطفاً چند لحظه دیگر دوباره امتحان کن."
            edit_message_text(chat_id, message_id, text, reply_markup=asset_kb(asset_key))
            return


def main():
    log.info("بات (نسخه سبک) در حال اجراست...")
    offset = None
    while True:
        try:
            result = get_updates(offset=offset)
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle_update(update)
                except Exception:
                    log.exception("خطا در پردازش یک آپدیت")
        except requests.exceptions.RequestException:
            log.exception("خطا در اتصال به API؛ ۵ ثانیه دیگر دوباره تلاش می‌شود")
            time.sleep(5)


if __name__ == "__main__":
    main()
