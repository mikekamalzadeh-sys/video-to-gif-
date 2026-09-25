import requests
import time
import json
import sqlite3
import os

# توکن جدید ربات سروش‌پلاس
TOKEN = "70122752:MfH36TGtbSxM18rL7EApd4jUKicb_D5bUrk"
BASE_URL = "https://api.splus.ir/bot" + TOKEN
user_steps = {}

def init_db():
    conn = sqlite3.connect('splus_manager.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, 
                    phone TEXT, 
                    session_key TEXT, 
                    auto_reply_text TEXT DEFAULT "سلام، در حال حاضر آنلاین نیستم. به زودی پاسخ خواهم داد.", 
                    is_active INTEGER DEFAULT 1
                )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('splus_manager.db')
    c = conn.cursor()
    c.execute('SELECT phone, session_key, auto_reply_text, is_active FROM users WHERE user_id=?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res

def save_user_phone(user_id, phone):
    conn = sqlite3.connect('splus_manager.db')
    c = conn.cursor()
    # اگر کاربر از قبل بود شماره‌اش آپدیت میشه، وگرنه اضافه میشه
    c.execute('''INSERT INTO users (user_id, phone, session_key, auto_reply_text, is_active) 
                 VALUES (?, ?, NULL, "سلام، در حال حاضر آنلاین نیستم. به زودی پاسخ خواهم داد.", 1)
                 ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone''', (user_id, phone))
    conn.commit()
    conn.close()

def save_user_text(user_id, text):
    conn = sqlite3.connect('splus_manager.db')
    c = conn.cursor()
    c.execute('UPDATE users SET auto_reply_text=? WHERE user_id=?', (text, user_id))
    conn.commit()
    conn.close()

init_db()

def get_updates(offset=None):
    url = BASE_URL + '/getUpdates'
    params = {'timeout': 3}
    if offset:
        params['offset'] = offset
    try:
        res = requests.get(url, params=params, timeout=5)
        return res.json()
    except:
        return {'ok': False, 'result': []}

def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    url = BASE_URL + '/sendMessage'
    params = {'chat_id': chat_id, 'text': text}
    if parse_mode:
        params['parse_mode'] = parse_mode
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    try:
        res = requests.get(url, params=params, timeout=15)
        return res.json()
    except:
        return {'ok': False}

def main_menu(chat_id):
    keyboard = {
        'keyboard': [
            [{'text': '⚙️ تنظیم متن پاسخ خودکار 📝'}],
            [{'text': '🔄 وضعیت منشی: روشن/خاموش 🟢'}],
            [{'text': '👤 اطلاعات اکانت من 📊'}]
        ],
        'resize_keyboard': True
    }
    text = '🤖✨ به ربات منشی خودکار سروش‌پلاس خوش آمدید!\n\nوقتی شما آفلاین باشید، این ربات به صورت اتوماتیک به پیام‌های دریافتی پاسخ می‌دهد.\n\n👇 لطفاً یک گزینه را انتخاب کنید:'
    send_message(chat_id, text, parse_mode='Markdown', reply_markup=keyboard)

print('🚀🤖 ربات منشی عمومی سروش‌پلاس روشن شد و آماده کاره...')
last_update_id = 0

while True:
    updates = get_updates(last_update_id + 1)
    if updates.get('ok') and updates.get('result'):
        for update in updates['result']:
            last_update_id = update['update_id']
            
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                step = user_steps.get(str(chat_id), {})
                
                # بررسی اینکه کاربر شماره تلفن خود را شیر کرده است
                if 'contact' in message:
                    phone = message['contact'].get('phone_number', '')
                    save_user_phone(chat_id, phone)
                    user_steps[str(chat_id)] = {'step': 'waiting_for_code'}
                    send_message(chat_id, '✅ شماره شما با موفقیت ثبت شد!\n\n🔑 اکنون کد ورود ارسال شده به اکانت سروش‌پلاس خود را وارد کنید:', reply_markup={'remove_keyboard': True})
                
                elif text == '/start':
                    user_data = get_user(chat_id)
                    if not user_data or not user_data[0]:
                        contact_keyboard = {
                            'keyboard': [
                                [{'text': '📱 اشتراک‌گذاری شماره تلفن من 📞', 'request_contact': True}]
                            ],
                            'resize_keyboard': True,
                            'one_time_keyboard': True
                        }
                        send_message(chat_id, '👋 سلام!\nبرای راه‌اندازی منشی خودکار، لطفاً روی دکمه زیر کلیک کنید تا شماره تلفن شما ثبت شود:', reply_markup=contact_keyboard)
                    else:
                        main_menu(chat_id)
                        user_steps[str(chat_id)] = {}
                
                elif step.get('step') == 'waiting_for_code':
                    code = text.strip()
                    user_steps[str(chat_id)] = {}
                    send_message(chat_id, '✅ کد تایید (' + code + ') با موفقیت دریافت شد! 🎉\nمنشی شما آماده به کار است.')
                    main_menu(chat_id)
                
                elif text == '⚙️ تنظیم متن پاسخ خودکار 📝':
                    user_steps[str(chat_id)] = {'step': 'set_auto_text'}
                    send_message(chat_id, '✍️ لطفاً متن جدید پاسخ خودکار را ارسال کنید (این متن وقتی آفلاین باشید به مخاطبان فرستاده می‌شود):')
                
                elif step.get('step') == 'set_auto_text':
                    save_user_text(chat_id, text)
                    user_steps[str(chat_id)] = {}
                    send_message(chat_id, '✅ متن پاسخ خودکار با موفقیت ذخیره شد! 👍')
                    main_menu(chat_id)
                
                elif text == '🔄 وضعیت منشی: روشن/خاموش 🟢':
                    conn = sqlite3.connect('splus_manager.db')
                    c = conn.cursor()
                    c.execute('SELECT is_active FROM users WHERE user_id=?', (chat_id,))
                    res = c.fetchone()
                    current_status = res[0] if res else 1
                    new_status = 0 if current_status == 1 else 1
                    c.execute('UPDATE users SET is_active=? WHERE user_id=?', (new_status, chat_id))
                    conn.commit()
                    conn.close()
                    status_str = 'روشن 🟢' if new_status == 1 else 'خاموش 🔴'
                    send_message(chat_id, '⚙️ وضعیت منشی خودکار تغییر کرد به: ' + status_str)
                
                elif text == '👤 اطلاعات اکانت من 📊':
                    u = get_user(chat_id)
                    if u:
                        phone = u[0] or 'ثبت نشده'
                        auto_txt = u[2]
                        status = 'روشن 🟢' if u[3] == 1 else 'خاموش 🔴'
                        info = '📊👤 اطلاعات اکانت شما:\n\n📱 شماره: ' + phone + '\n🔄 وضعیت منشی: ' + status + '\n\n📝 متن پاسخ خودکار فعلی:\n"' + auto_txt + '"'
                        send_message(chat_id, info, parse_mode='Markdown')
                    else:
                        send_message(chat_id, '⚠️ ابتدا دستور /start را بزنید.')

    time.sleep(1)
    
