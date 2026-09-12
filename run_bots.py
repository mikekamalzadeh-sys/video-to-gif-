# -*- coding: utf-8 -*-
"""
اجراکننده‌ی هم‌زمان دو بات (price_bot_lite-6.py و video_note_bot-2.py)
----------------------------------------------------------------------
این فایل هر دو بات را به‌صورت دو پروسس جدا (subprocess) اجرا می‌کند و
هر دو خروجی/لاگ‌شان را در همین ترمینال نشان می‌دهد. اگر یکی از بات‌ها
به هر دلیلی کرش کند، این اسکریپت به‌صورت خودکار بعد از چند ثانیه دوباره
همان بات را اجرا می‌کند - بدون این‌که بات دیگر متوقف شود.

هدف: روی Railway، به‌عنوان یک worker واحد اجرا شود و هر دو بات را
هم‌زمان زنده نگه دارد.

مهم: مسیر/اسم فایل هر دو بات باید دقیقاً کنار همین فایل (در ریشه‌ی
پروژه) باشد. اگر تو ساختار پوشه‌بندی جای دیگری گذاشتیشون، مقدار
BOT_SCRIPTS زیر را با مسیر درست اصلاح کن.
"""

import logging
import subprocess
import sys
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("run-bots")

BOT_SCRIPTS = [
    "price_bot_lite-6.py",
    "video_note_bot-2.py",
]

RESTART_DELAY_SECONDS = 5


def run_forever(script_name):
    while True:
        log.info("در حال اجرای %s ...", script_name)
        try:
            # stdout/stderr مستقیم به ترمینال اصلی وصل می‌شود تا لاگ هر دو
            # بات با پیشوند مشخص در یک جا دیده شود.
            process = subprocess.Popen(
                [sys.executable, "-u", script_name],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            exit_code = process.wait()
            log.warning("%s با کد %s متوقف شد.", script_name, exit_code)
        except FileNotFoundError:
            log.error("فایل %s پیدا نشد. مطمئن شو کنار run_bots.py قرار دارد.", script_name)
            return
        except Exception:
            log.exception("خطای غیرمنتظره هنگام اجرای %s", script_name)

        log.info("راه‌اندازی مجدد %s بعد از %s ثانیه...", script_name, RESTART_DELAY_SECONDS)
        time.sleep(RESTART_DELAY_SECONDS)


def main():
    threads = []
    for script in BOT_SCRIPTS:
        t = threading.Thread(target=run_forever, args=(script,), daemon=True)
        t.start()
        threads.append(t)

    log.info("هر دو بات راه‌اندازی شدند: %s", ", ".join(BOT_SCRIPTS))

    # ترد اصلی زنده می‌ماند تا پروسه‌ی worker بسته نشود.
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
