import requests
import sqlite3
import time

TOKEN = "70122752:B-Jm-iWBnuMfehi4Z25zXLnhpPw4cnvCNds"
URL = f"https://splus.ir/bot{TOKEN}/"

# اتصال به دیتابیس SQLite برای مدیریت کاربران و داده‌ها
conn = sqlite3.connect('shop_data.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        step TEXT
    )
''')
conn.commit()

def get_updates(offset=None):
    url = URL + "getUpdates"
    params = {"timeout": 100, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=110)
        return response.json()
    except Exception as e:
        print(f"خطا در دریافت آپدیت‌ها: {e}")
        return {}

def send_message(chat_id, text):
    url = URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")

def main():
    print("ربات سروش‌پلاس با موفقیت روشن شد و در حال گوش دادن به پیام‌هاست...")
    offset = None
    while True:
        updates = get_updates(offset)
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                
                # بررسی وجود پیام در به‌روزرسانی
                if "message" in update:
                    chat_id = update["message"]["chat"]["chat_id"]
                    text = update["message"].get("text", "")
                    
                    print(f"پیام جدید از {chat_id}: {text}")
                    
                    # پاسخ به دستور start/
                    if text == "/start":
                        send_message(chat_id, "سلام! ربات شما با موفقیت روی سروش‌پلاس فعال شد.")
                    else:
                        send_message(chat_id, f"پیام شما دریافت شد: {text}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()
    
