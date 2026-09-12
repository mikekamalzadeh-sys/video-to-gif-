# -*- coding: utf-8 -*-
"""
بات قیمت لحظه‌ای دلار / طلای ۱۸ عیار / طلای تتری (XAUT) / بیت‌کوین /
اتریوم / تتر / ترون برای سروش‌پلاس (نسخه سبک)
--------------------------------------------------------------------------
این نسخه فقط از کتابخانه `requests` استفاده می‌کند و مستقیم با HTTP API
بات سروش‌پلاس صحبت می‌کند (بدون aiosplus/pydantic).

دو منبع قیمت (هرکدام جدا فچ می‌شه تا قطعی یکی، اون یکی رو از کار نندازه):
    - دلار و طلای ۱۸ عیار  -> BrsApi (Gold_Currency.php)
    - بیت‌کوین/اتریوم/تتر/ترون/XAUT -> نوبیتکس (Nobitex) - عمومی، بدون کلید

نصب:
    pip install requests

اجرا:
    python price_bot_lite.py

نکته: چون مستندات عمومیِ کامل و رسمی HTTP API سروش‌پلاس در دسترس من نبود،
BASE_URL زیر بر پایه‌ی متداول‌ترین الگوی APIهای مشابه (شبیه تلگرام) تنظیم
شده: https://api.splus.ir/bot<TOKEN>/<method>
اگر بعد از اجرا با خطای 404 یا connection error مواجه شدی، احتمالاً دامنه
یا مسیر واقعی فرق دارد. در آن صورت مقدار BASE_URL را با توجه به مستندات
رسمی که از پنل ربات‌ساز (mrbot@) یا داکیومنت زیر می‌گیری اصلاح کن:
https://soroushplus.com/p/documents/bot-platform
"""

import json
import logging
import re
import time
from datetime import datetime

import requests

# ============================ تنظیمات ============================

BOT_TOKEN = "69896472:tp2llzJ_BXZqA9QYQUxLpJ7kESw8VayiIkw"

# پایه آدرس API سروش‌پلاس - در صورت نیاز اصلاح کن (توضیحات بالا را بخوان)
BASE_URL = f"https://api.splus.ir/bot{BOT_TOKEN}"

# کلید رایگان BrsApi (برای دلار و طلای ۱۸ عیار)
# ثبت‌نام رایگان: https://brsapi.ir/free-api-gold-currency-webservice/
BRSAPI_KEY = "Bs9BZaDzfZLCakW65QEKKDNFdttG5qZ6"
BRSAPI_URL = "https://Api.BrsApi.ir/Market/Gold_Currency.php"

# API عمومیِ آمار بازار نوبیتکس - نیازی به کلید ندارد
NOBITEX_STATS_URL = "https://apiv2.nobitex.ir/market/stats"

RAW_DEBUG = False  # برای دیباگ اولیه True کن تا خروجی خام هر دو API چاپ شود

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("soroush-price-bot-lite")

# ============================ تعریف دارایی‌ها ============================
#
# دو نوع "source" داریم:
#   "brsapi"  -> قیمت با جست‌وجوی هوشمند در پاسخ BrsApi پیدا می‌شود (تومان)
#   "nobitex" -> قیمت مستقیماً از جفت‌ارز نوبیتکس خوانده می‌شود (ریال)
#
# در نهایت همه‌چیز داخلی به "تومان" تبدیل می‌شود تا محاسبه‌ی معادل دلاری
# و نمایش ریال/تومان برای همه یکسان باشد.

ASSETS = {
    "usd": {
        "title": "دلار آمریکا", "short": "دلار", "emoji": "💵",
        "source": "brsapi",
        "keywords": ["دلار", "usd"],
        "exclude": ["استرالیا", "کانادا", "سنگاپور", "هنگ", "نیوزیلند",
                    "aud", "cad", "تتر", "usdt", "tether"],
    },
    "gold_18k": {
        "title": "طلای ۱۸ عیار (داخلی)", "short": "طلای ۱۸عیار", "emoji": "🟡",
        "source": "brsapi",
        "keywords": ["18 عیار", "18عیار", "طلای 18", "geram18", "gold18"],
        "exclude": ["24 عیار", "24عیار", "طلای 24", "مثقال", "سکه",
                    "geram24", "mesghal"],
    },
    "gold_xaut": {
        "title": "طلای تتری (XAUT)", "short": "طلا (XAUT)", "emoji": "🥇",
        "source": "nobitex",
        "nobitex_symbol": "xaut-rls",
    },
    "btc": {
        "title": "بیت‌کوین", "short": "بیت‌کوین", "emoji": "₿",
        "source": "nobitex",
        "nobitex_symbol": "btc-rls",
    },
    "eth": {
        "title": "اتریوم", "short": "اتریوم", "emoji": "⧫",
        "source": "nobitex",
        "nobitex_symbol": "eth-rls",
    },
    "usdt": {
        "title": "تتر", "short": "تتر", "emoji": "💰",
        "source": "nobitex",
        "nobitex_symbol": "usdt-rls",
    },
    "trx": {
        "title": "ترون", "short": "ترون", "emoji": "🔺",
        "source": "nobitex",
        "nobitex_symbol": "trx-rls",
    },
}

PRICE_KEYS = ["price", "value", "Price", "sell", "sell_price", "close", "rate", "p", "last_trade_price"]
CHANGE_KEYS = ["change_percent", "percent_change", "percent", "change", "change24h", "day_change", "dp", "changePercent"]
DATE_KEYS = ["date", "time", "date_time", "updated_at", "last_update", "date_time_fa"]


# ============================ ابزارهای مشترک BrsApi ============================

def _iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _iter_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_dicts(v)


def _text_of(item):
    parts = []
    for k in ("name", "name_en", "symbol", "title", "label", "unit"):
        v = item.get(k)
        if isinstance(v, str):
            parts.append(v.lower())
    return " ".join(parts)


def _kw_match(kw, text):
    """
    تطابق کلیدواژه با متن. برای کلیدواژه‌های لاتین/عددی (usd, geram18, ...)
    از مرزبندی کلمه (word boundary) استفاده می‌شود تا مثلاً "usd" داخل
    "usdt" به‌اشتباه تطابق پیدا نکند. برای کلیدواژه‌های فارسی همان تطابق
    زیررشته‌ای ساده حفظ شده چون کار می‌کرد.
    """
    kw = kw.lower()
    if re.fullmatch(r"[a-z0-9]+", kw):
        pattern = rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return kw in text


def _find_asset(data, keywords, exclude):
    best = None
    best_has_change = False
    for item in _iter_dicts(data):
        text = _text_of(item)
        if not text:
            continue
        if any(bad.lower() in text for bad in exclude):
            continue
        if any(_kw_match(kw, text) for kw in keywords):
            if any(k in item for k in PRICE_KEYS):
                has_change = any(k in item for k in CHANGE_KEYS)
                # فقط وقتی جایگزین می‌کنیم که یا هنوز چیزی پیدا نکرده‌ایم،
                # یا آیتم جدید کامل‌تر است - تا یک تطابق ضعیف/اشتباه بعدی،
                # مقدار درستِ قبلی را پاک نکند (last-match-wins).
                if best is None or (has_change and not best_has_change):
                    best = item
                    best_has_change = has_change
                    if has_change:
                        break
    return best


def _get_first(item, keys):
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return None


def _to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


# ============================ دریافت قیمت‌ها ============================

def fetch_prices():
    """
    هر منبع جدا و در بلوک try/except خودش فچ می‌شود؛ اگر یکی از دو سرویس
    (BrsApi یا نوبیتکس) موقتاً از دسترس خارج بود، آن یکی دیگر همچنان کار
    می‌کند و فقط پیام «در دسترس نیست» برای همان دارایی نمایش داده می‌شود.
    """
    result = {"brsapi": None, "nobitex": None}

    try:
        resp = requests.get(BRSAPI_URL, params={"key": BRSAPI_KEY}, timeout=10)
        resp.raise_for_status()
        result["brsapi"] = resp.json()
        if RAW_DEBUG:
            log.info("RAW BrsApi response: %s", result["brsapi"])
    except Exception:
        log.exception("خطا در دریافت قیمت از BrsApi (دلار/طلا)")

    try:
        symbols = ",".join(cfg["nobitex_symbol"].split("-")[0]
                            for cfg in ASSETS.values() if cfg.get("source") == "nobitex")
        resp = requests.get(
            NOBITEX_STATS_URL,
            params={"srcCurrency": symbols, "dstCurrency": "rls"},
            timeout=10,
        )
        resp.raise_for_status()
        result["nobitex"] = resp.json()
        if RAW_DEBUG:
            log.info("RAW Nobitex response: %s", result["nobitex"])
    except Exception:
        log.exception("خطا در دریافت قیمت از نوبیتکس")

    return result


def _extract_brsapi_toman(cfg, brsapi_data):
    """قیمت و درصد تغییر را از BrsApi برمی‌گرداند (واحد: تومان)."""
    if not brsapi_data:
        return None, None
    item = _find_asset(brsapi_data, cfg["keywords"], cfg["exclude"])
    if not item:
        return None, None
    price_val = _to_float(_get_first(item, PRICE_KEYS))
    change_val = _to_float(_get_first(item, CHANGE_KEYS))
    return price_val, change_val


def _extract_nobitex_toman(cfg, nobitex_data):
    """قیمت و درصد تغییر را از نوبیتکس برمی‌گرداند (تبدیل‌شده به تومان)."""
    if not nobitex_data:
        return None, None
    stats = nobitex_data.get("stats", {}) if isinstance(nobitex_data, dict) else {}
    item = stats.get(cfg["nobitex_symbol"])
    if not item:
        return None, None
    price_rial = _to_float(item.get("latest") or item.get("bestSell") or item.get("bestBuy"))
    change_val = _to_float(item.get("dayChange"))
    price_toman = price_rial / 10 if price_rial is not None else None
    return price_toman, change_val


def _extract_toman(asset_key, data):
    cfg = ASSETS[asset_key]
    if cfg["source"] == "brsapi":
        return _extract_brsapi_toman(cfg, data.get("brsapi"))
    return _extract_nobitex_toman(cfg, data.get("nobitex"))


def _usd_rate_toman(data):
    """
    نرخ دلار به تومان برای محاسبه‌ی معادل دلاری بقیه‌ی دارایی‌ها.
    اول از قیمت واقعی دلار (BrsApi) استفاده می‌شود؛ اگر در دسترس نبود،
    قیمت تتر از نوبیتکس (که تقریباً معادل ۱ دلار است) به‌عنوان جایگزین
    استفاده می‌شود.
    """
    price_toman, _ = _extract_brsapi_toman(ASSETS["usd"], data.get("brsapi"))
    if price_toman:
        return price_toman
    price_toman, _ = _extract_nobitex_toman(ASSETS["usdt"], data.get("nobitex"))
    return price_toman


def format_price_message(asset_key, data):
    cfg = ASSETS[asset_key]
    price_toman, change_val = _extract_toman(asset_key, data)

    if price_toman is None:
        return f"{cfg['emoji']} متأسفانه قیمت «{cfg['title']}» الان در دسترس نیست.\nچند لحظه دیگر دوباره امتحان کن."

    lines = [f"{cfg['emoji']} {cfg['title']}", ""]

    rial = price_toman * 10
    lines.append(f"🔹 قیمت لحظه‌ای: {rial:,.0f} ریال")
    lines.append(f"   ({price_toman:,.0f} تومان)")

    if asset_key != "usd":
        usd_rate = _usd_rate_toman(data)
        if usd_rate:
            usd_equiv = price_toman / usd_rate
            lines.append(f"💲 معادل دلاری: {usd_equiv:,.2f} $")

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
    # به‌صورت شبکه ۲ در ۲
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
# این‌ها ساده‌ترین شکل ممکن هستند (مشابه Telegram Bot API). اگر متد یا مسیر
# دقیق سروش‌پلاس فرق داشت، فقط کافیست این چند تابع را با توجه به مستندات
# رسمی که از پنل mrbot@ می‌گیری اصلاح کنی؛ بقیه‌ی کد دست‌نخورده می‌ماند.

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
                log.exception("خطا در دریافت قیمت")
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
