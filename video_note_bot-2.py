import os
import json
import time
import subprocess
import tempfile

import requests

# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------
TOKEN = os.getenv("BOT_TOKEN", "69892862:S7jB10nAszRLwE_y2YL2KIqBUDuQ4RvL2yc")
BASE_URL = "https://api.splus.ir/bot" + TOKEN
FILE_BASE_URL = "https://api.splus.ir/file/bot" + TOKEN

MAX_DOWNLOAD_MB = 20  # محدودیت سروش‌پلاس برای دانلود فایل
MAX_DURATION = 60     # حداکثر مدت مجاز برای ویدیو مسیج (ثانیه)
OUTPUT_SIZE = 384      # ابعاد مربع خروجی ویدیو مسیج (px)
GIF_MAX_WIDTH = 480    # حداکثر عرض خروجی گیف (px)
GIF_MAX_DURATION = 30  # حداکثر مدت گیف (ثانیه) — گیف‌های طولانی حجم خیلی بالا می‌رن

BTN_VIDEO_NOTE = '🎥 ویدیو مسیج'
BTN_GIF = '🎞 گیف'

# ویدیوهایی که منتظر انتخاب کاربر (ویدیو مسیج/گیف) هستن: chat_id -> video dict
pending_videos = {}

SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
SESSION.mount('https://', _adapter)
SESSION.mount('http://', _adapter)


# ---------------------------------------------------------------------------
# توابع کمکی API
# ---------------------------------------------------------------------------

def get_updates(offset=None):
    params = {'timeout': 25}
    if offset:
        params['offset'] = offset
    try:
        res = SESSION.get(BASE_URL + '/getUpdates', params=params, timeout=30)
        data = res.json()
        if not data.get('ok'):
            print('⚠️ خطای getUpdates:', data)
        return data
    except Exception as e:
        print('⚠️ استثنا در getUpdates:', e)
        return {'ok': False, 'result': []}


def send_message(chat_id, text, reply_markup=None):
    payload = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        SESSION.post(BASE_URL + '/sendMessage', json=payload, timeout=15)
    except Exception as e:
        print('⚠️ خطا در sendMessage:', e)


def ask_conversion_type(chat_id):
    keyboard = {
        'keyboard': [[{'text': BTN_VIDEO_NOTE}, {'text': BTN_GIF}]],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }
    send_message(chat_id, '🎬 این ویدیو رو به چه شکلی تبدیل کنم؟', reply_markup=keyboard)


def remove_keyboard(chat_id, text):
    send_message(chat_id, text, reply_markup={'remove_keyboard': True})


def get_file_path(file_id):
    """گرفتن file_path از API برای ساخت لینک دانلود."""
    try:
        res = SESSION.get(BASE_URL + '/getFile', params={'file_id': file_id}, timeout=15)
        data = res.json()
        if data.get('ok'):
            return data['result']['file_path']
        print('⚠️ خطای getFile:', data)
        return None
    except Exception as e:
        print('⚠️ استثنا در getFile:', e)
        return None


def download_file(file_path, dest_path, expected_size=None, max_retries=3):
    """
    این تابع عمداً از SESSION مشترک استفاده نمی‌کنه و هر بار یه اتصال تازه باز می‌کنه.
    وقتی HTTP 200 برمی‌گرده ولی بدنه خالیه (۰ بایت)، معمولاً یعنی یه اتصال
    keep-alive قدیمی/نیمه‌بسته از pool دوباره استفاده شده — با یه اتصال کاملاً
    تازه (و چند تلاش مجدد) این مشکل معمولاً حل می‌شه.
    """
    url = FILE_BASE_URL + '/' + file_path
    print('⬇️ دانلود از:', url)

    for attempt in range(1, max_retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60, headers={'Connection': 'close'}) as r:
                print(f'   تلاش {attempt} | وضعیت HTTP: {r.status_code} | Content-Type: {r.headers.get("Content-Type")} | Content-Length: {r.headers.get("Content-Length")}')
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            actual_size = os.path.getsize(dest_path)
            print(f'   حجم دانلود شده: {actual_size} بایت' + (f' (انتظار: {expected_size} بایت)' if expected_size else ''))

            if actual_size == 0:
                print(f'⚠️ فایل دانلودشده خالیه (تلاش {attempt}/{max_retries}).')
                time.sleep(1.5)
                continue

            if expected_size and abs(actual_size - expected_size) > 1024:
                print(f'⚠️ حجم دانلودشده با حجم مورد انتظار همخوانی نداره (تلاش {attempt}/{max_retries}).')
                time.sleep(1.5)
                continue

            return True

        except Exception as e:
            print(f'⚠️ خطا در دانلود فایل (تلاش {attempt}/{max_retries}):', e)
            time.sleep(1.5)

    return False


def send_video_note(chat_id, video_path, duration=None):
    url = BASE_URL + '/sendVideoNote'
    data = {'chat_id': chat_id, 'length': OUTPUT_SIZE}
    if duration:
        data['duration'] = int(duration)
    try:
        with open(video_path, 'rb') as f:
            files = {'video_note': f}
            res = SESSION.post(url, data=data, files=files, timeout=60)
        result = res.json()
        if not result.get('ok'):
            print('⚠️ خطای sendVideoNote:', result)
        return result
    except Exception as e:
        print('⚠️ استثنا در sendVideoNote:', e)
        return {'ok': False}


def send_animation(chat_id, path, width=None, height=None, duration=None):
    url = BASE_URL + '/sendAnimation'
    data = {'chat_id': chat_id}
    if width:
        data['width'] = int(width)
    if height:
        data['height'] = int(height)
    if duration:
        data['duration'] = int(duration)

    filename = os.path.basename(path)
    mime_type = 'image/gif' if filename.lower().endswith('.gif') else 'video/mp4'

    try:
        with open(path, 'rb') as f:
            files = {'animation': (filename, f, mime_type)}
            res = SESSION.post(url, data=data, files=files, timeout=90)
        result = res.json()
        if not result.get('ok'):
            print('⚠️ خطای sendAnimation:', result)
        return result
    except Exception as e:
        print('⚠️ استثنا در sendAnimation:', e)
        return {'ok': False}


# ---------------------------------------------------------------------------
# پردازش ویدیو با ffmpeg
# ---------------------------------------------------------------------------

def get_video_duration(path):
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', path],
            capture_output=True, text=True, timeout=20
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def get_video_dimensions(path):
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=20
        )
        w, h = out.stdout.strip().split(',')
        return int(w), int(h)
    except Exception:
        return None, None


def convert_to_video_note(input_path, output_path):
    """
    کراپ به مربع (از وسط) + ریسایز به OUTPUT_SIZE + محدود کردن مدت به MAX_DURATION
    + انکود به mp4/h264 که برای video_note لازمه.
    """
    duration = get_video_duration(input_path)
    trim_args = []
    if duration and duration > MAX_DURATION:
        trim_args = ['-t', str(MAX_DURATION)]

    vf = f"crop='min(iw,ih)':'min(iw,ih)',scale={OUTPUT_SIZE}:{OUTPUT_SIZE}"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        *trim_args,
        '-vf', vf,
        '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.0',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '96k',
        '-movflags', '+faststart',
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print('⚠️ خطای ffmpeg:', result.stderr[-2000:])
            return False
        return True
    except Exception as e:
        print('⚠️ استثنا در ffmpeg:', e)
        return False


def convert_to_gif(input_path, output_path):
    """
    برخلاف mp4 بی‌صدا، خروجی این تابع یه فایل .gif واقعیه — چون کلاینت
    سروش‌پلاس فقط وقتی فایل واقعاً از نوع gif باشه، لیبل «گیف» رو نشون می‌ده.
    از روش دوپاس (palette) استفاده می‌شه تا کیفیت رنگ گیف قابل قبول بمونه.
    """
    duration = get_video_duration(input_path)
    trim_args = []
    if duration and duration > GIF_MAX_DURATION:
        trim_args = ['-t', str(GIF_MAX_DURATION)]

    tmp_dir = os.path.dirname(output_path)
    palette_path = os.path.join(tmp_dir, 'palette.png')

    fps = 12
    scale = f"'min({GIF_MAX_WIDTH},iw)':-2:flags=lanczos"

    # پاس اول: ساخت پالت رنگی بهینه
    palette_cmd = [
        'ffmpeg', '-y', '-i', input_path,
        *trim_args,
        '-vf', f'fps={fps},scale={scale},palettegen',
        palette_path
    ]
    # پاس دوم: ساخت گیف نهایی با استفاده از پالت
    gif_cmd = [
        'ffmpeg', '-y', '-i', input_path, '-i', palette_path,
        *trim_args,
        '-filter_complex', f'fps={fps},scale={scale}[x];[x][1:v]paletteuse',
        '-loop', '0',
        output_path
    ]
    try:
        r1 = subprocess.run(palette_cmd, capture_output=True, text=True, timeout=120)
        if r1.returncode != 0:
            print('⚠️ خطای ffmpeg (ساخت پالت گیف):', r1.stderr[-2000:])
            return False

        r2 = subprocess.run(gif_cmd, capture_output=True, text=True, timeout=120)
        if r2.returncode != 0:
            print('⚠️ خطای ffmpeg (ساخت گیف):', r2.stderr[-2000:])
            return False

        return True
    except Exception as e:
        print('⚠️ استثنا در ffmpeg (گیف):', e)
        return False


# ---------------------------------------------------------------------------
# حلقه اصلی
# ---------------------------------------------------------------------------

def handle_incoming_video(chat_id, video):
    file_size = video.get('file_size') or 0
    if file_size and file_size > MAX_DOWNLOAD_MB * 1024 * 1024:
        send_message(chat_id, f'⚠️ حجم ویدیو بیشتر از {MAX_DOWNLOAD_MB} مگابایت است و قابل پردازش نیست.')
        return

    pending_videos[chat_id] = video
    ask_conversion_type(chat_id)


def process_pending_video(chat_id, mode):
    video = pending_videos.pop(chat_id, None)
    if not video:
        remove_keyboard(chat_id, '⚠️ ویدیویی برای تبدیل پیدا نشد. یه ویدیوی جدید بفرست.')
        return

    label = 'ویدیو مسیج' if mode == 'video_note' else 'گیف'
    remove_keyboard(chat_id, f'⏳ در حال تبدیل ویدیو به {label}...')

    file_size = video.get('file_size') or 0
    file_path = get_file_path(video['file_id'])
    if not file_path:
        send_message(chat_id, '⚠️ خطا در دریافت فایل ویدیو.')
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, 'input.mp4')

        if not download_file(file_path, input_path, expected_size=file_size):
            send_message(chat_id, '⚠️ دانلود ویدیو ناموفق بود.')
            return

        if mode == 'video_note':
            output_path = os.path.join(tmp_dir, 'output.mp4')
            if not convert_to_video_note(input_path, output_path):
                send_message(chat_id, '⚠️ تبدیل ویدیو ناموفق بود.')
                return
            duration = get_video_duration(output_path)
            result = send_video_note(chat_id, output_path, duration)
            if not result.get('ok'):
                send_message(chat_id, '⚠️ ارسال ویدیو مسیج ناموفق بود.')

        else:  # gif
            output_path = os.path.join(tmp_dir, 'output.gif')
            if not convert_to_gif(input_path, output_path):
                send_message(chat_id, '⚠️ تبدیل ویدیو به گیف ناموفق بود.')
                return
            width, height = get_video_dimensions(output_path)
            result = send_animation(chat_id, output_path, width, height)
            if not result.get('ok'):
                send_message(chat_id, '⚠️ ارسال گیف ناموفق بود.')


def main():
    print('✅ بات تبدیل ویدیو به ویدیو مسیج اجرا شد.')
    last_update_id = 0

    while True:
        try:
            updates = get_updates(last_update_id + 1)

            if updates.get('ok') and updates.get('result'):
                for update in updates['result']:
                    last_update_id = update['update_id']

                    message = update.get('message')
                    if not message:
                        continue

                    chat_id = message['chat']['id']

                    if 'video' in message:
                        handle_incoming_video(chat_id, message['video'])
                    elif 'text' in message and message['text'] == BTN_VIDEO_NOTE:
                        process_pending_video(chat_id, 'video_note')
                    elif 'text' in message and message['text'] == BTN_GIF:
                        process_pending_video(chat_id, 'gif')
                    elif 'text' in message and message['text'] in ('/start', 'شروع'):
                        send_message(chat_id, '🎥 یه ویدیو برام بفرست تا به ویدیو مسیج (پیام گرد) یا گیف تبدیلش کنم.\nحداکثر حجم قابل قبول: ' + str(MAX_DOWNLOAD_MB) + ' مگابایت.')
            else:
                time.sleep(1)

        except Exception as loop_error:
            print('⚠️ خطای غیرمنتظره در حلقه اصلی:', loop_error)
            time.sleep(2)


if __name__ == '__main__':
    main()
