import os
import sqlite3
from splusthon import SoroushClient, events
from splusthon.sessions import StringSession

SESSION_STRING = os.environ.get("SESSION_STRING", "")

# راه‌اندازی دیتابیس برای ذخیره متن منشی
def init_db():
    conn = sqlite3.connect('user_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, 
                    value TEXT
                )''')
    # اگر متنی نبود، یک متن پیش‌فرض بگذار
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("auto_text", "سلام، در حال حاضر آنلاین نیستم. به زودی پاسخ خواهم داد.")')
    conn.commit()
    conn.close()

def get_auto_text():
    conn = sqlite3.connect('user_bot.db')
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key="auto_text"')
    res = c.fetchone()
    conn.close()
    return res[0] if res else "سلام، در حال حاضر آنلاین نیستم."

def set_auto_text(new_text):
    conn = sqlite3.connect('user_bot.db')
    c = conn.cursor()
    c.execute('UPDATE settings SET value=? WHERE key="auto_text"', (new_text,))
    conn.commit()
    conn.close()

init_db()

session = StringSession(SESSION_STRING)
client = SoroushClient(session)

@client.on(events.NewMessage(outgoing=False))
async def auto_reply_handler(event):
    # اگر پیام در پی‌وی (چت شخصی) باشد و از طرف خودت نباشد
    if event.is_private and not event.out:
        current_text = get_auto_text()
        await event.respond(current_text)
        print(f"📩 پیام از {event.chat_id} آمد و پاسخ خودکار ارسال شد.")

@client.on(events.NewMessage(outgoing=True))
async def change_text_command(event):
    # برای تغییر متن، کافی است در چت ذخیره شده خودت (Saved Messages) بنویسی: .settext متن جدید
    if event.raw_text and event.raw_text.startswith(".settext "):
        new_text = event.raw_text.replace(".settext ", "", 1).strip()
        set_auto_text(new_text)
        await event.edit(f"✅ متن پاسخ خودکار با موفقیت تغییر کرد به:\n\n{new_text}")
        print(f"🔄 متن منشی بروز شد.")

def main():
    print("🚀 در حال راه‌اندازی یوزربات منشی...")
    client.start()
    
    if not SESSION_STRING:
        print("\n🔑 رشته سشن شما (این را کپی کنید و در متغیرهای محیطی Railway بگذارید):\n")
        print(client.session.save())
        print("\n" + "="*50 + "\n")

    print("✅ یوزربات آماده به کار است!")
    print("💡 نکته: برای تغییر متن منشی، کافی است در چت ذخیره شده خودت دستور زیر را بفرست:")
    print("   .settext متن جدید شما")
    client.run_until_disconnected()

if __name__ == '__main__':
    main()
    
