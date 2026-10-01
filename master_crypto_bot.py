"""
Master Crypto Bot - Autonomous Dual Engine (Yapping & Viral Engagement)
Menggabungkan dua jadwal otomatis sesuai instruksi:
1. ENGINE POSTING MANDIRI:
   - 1x postingan tweet crypto yapping per akun (dengan hashtag & cashtags)
   - Jeda antar siklus postingan: 1 - 2 Jam (60 - 120 menit acak)

2. ENGINE VIRAL ENGAGEMENT:
   - 5x postingan viral per batch per akun
   - Aksi: Like ❤️ + Retweet 🔁 + Komen Kontekstual 💬
   - Tanpa Follow 👤 (0 following tetap terjaga)
   - Bukan Giveaway Drop Wallet 👛 (100% diskusi organik)
   - Jeda antar siklus batch: 30 - 60 Menit acak

3. SISTEM BROWSER LOCK (HEMAT RAM):
   - Menggunakan asyncio.Lock() sehingga tidak ada benturan browser
   - RAM laptop tetap bersih dan ringan
"""

import argparse
import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import RESULTS_DIR
from accounts_manager import load_accounts
from crypto_yapper import run_multi_account_yapping
from viral_crypto_engager import run_multi_account_engagement

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

# Global lock untuk memastikan hanya 1 sesi browser yang aktif dalam satu waktu
browser_lock = asyncio.Lock()


async def engine_original_yapper(
    post_interval_min: int = 60,
    post_interval_max: int = 120,
    headless: bool = True
):
    """
    ENGINE 1: Postingan Yapping Mandiri
    - 1x tweet per akun
    - Delay 1 - 2 Jam (60 - 120 menit)
    """
    cycle = 1
    while True:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{MAGENTA}{BOLD}╔═══════════════════════════════════════════════════════════════╗")
        print(f"║ 📢 [ENGINE 1] MEMULAI SIKLUS POSTINGAN MANDIRI #{cycle:<4}       ║")
        print(f"║ ⏰ Waktu Mulai : {now_str:<44} ║")
        print(f"║ 🎯 Target      : 1x Postingan Tweet Yapping per Akun          ║")
        print(f"╚═══════════════════════════════════════════════════════════════╝{RESET}", flush=True)

        async with browser_lock:
            try:
                await run_multi_account_yapping(
                    tweets_per_account=1,
                    lang="mixed",
                    delay_between_accounts=12.0,
                    headless=headless
                )
            except Exception as e:
                print(f"{RED}❌ Error pada Engine 1 (Posting Yapping): {e}{RESET}", flush=True)

        # Tidur 1 - 2 Jam (60 - 120 menit)
        sleep_minutes = random.randint(post_interval_min, post_interval_max)
        wake_time = (datetime.now() + timedelta(minutes=sleep_minutes)).strftime("%H:%M:%S")
        print(f"\n{MAGENTA}💤 [ENGINE 1] Siklus #{cycle} selesai. Tidur selama {sleep_minutes} menit ({sleep_minutes/60:.1f} jam)...{RESET}")
        print(f"{MAGENTA}⏰ [ENGINE 1] Jadwal posting berikutnya: {wake_time}{RESET}\n", flush=True)

        cycle += 1
        await asyncio.sleep(sleep_minutes * 60)


async def engine_viral_engager(
    viral_count: int = 5,
    viral_interval_min: int = 30,
    viral_interval_max: int = 60,
    headless: bool = True
):
    """
    ENGINE 2: Viral Engagement
    - 5x postingan viral per batch per akun
    - Like ❤️, Retweet 🔁, Komen Kontekstual 💬 (Tanpa Follow & Tanpa Wallet Drop)
    - Delay 30 - 60 Menit
    """
    cycle = 1
    # Tunggu 30 detik saat awal agar tidak rebutan lock dengan Engine 1
    await asyncio.sleep(15)

    while True:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}{BOLD}╔═══════════════════════════════════════════════════════════════╗")
        print(f"║ 🔥 [ENGINE 2] MEMULAI SIKLUS VIRAL ENGAGEMENT #{cycle:<4}         ║")
        print(f"║ ⏰ Waktu Mulai : {now_str:<44} ║")
        print(f"║ 🎯 Target      : {viral_count}x Tweet Viral per Akun (Like+RT+Komen)       ║")
        print(f"╚═══════════════════════════════════════════════════════════════╝{RESET}", flush=True)

        async with browser_lock:
            try:
                await run_multi_account_engagement(
                    tweets_per_account=viral_count,
                    do_like=True,
                    do_retweet=True,
                    do_comment=True,
                    delay_between_accounts=10.0,
                    headless=headless
                )
            except Exception as e:
                print(f"{RED}❌ Error pada Engine 2 (Viral Engager): {e}{RESET}", flush=True)

        # Tidur 30 - 60 Menit
        sleep_minutes = random.randint(viral_interval_min, viral_interval_max)
        wake_time = (datetime.now() + timedelta(minutes=sleep_minutes)).strftime("%H:%M:%S")
        print(f"\n{CYAN}💤 [ENGINE 2] Siklus #{cycle} selesai. Tidur selama {sleep_minutes} menit...{RESET}")
        print(f"{CYAN}⏰ [ENGINE 2] Jadwal engagement batch berikutnya: {wake_time}{RESET}\n", flush=True)

        cycle += 1
        await asyncio.sleep(sleep_minutes * 60)


async def main_master(
    post_interval_min: int = 60,
    post_interval_max: int = 120,
    viral_count: int = 5,
    viral_interval_min: int = 30,
    viral_interval_max: int = 60,
    headless: bool = True
):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         🚀 MASTER CRYPTO AUTONOMOUS BOT SYSTEM                ║
║   Dual Engine: Postingan Mandiri + Viral Crypto Engagement    ║
╚═══════════════════════════════════════════════════════════════╝{RESET}
{BOLD}Konfigurasi Jadwal Otomatis:{RESET}
  • {MAGENTA}{BOLD}Engine 1 (Postingan Yapping Mandiri){RESET} : 1x Tweet / Akun
    - Jeda antar postingan               : {GREEN}{post_interval_min} - {post_interval_max} Menit (1 - 2 Jam){RESET}
  • {CYAN}{BOLD}Engine 2 (Engagement Tweet Viral){RESET}    : {GREEN}{viral_count}x Tweet Viral / Batch / Akun{RESET}
    - Aksi Interaksi                     : Like ❤️ + Retweet 🔁 + Komen Cerdas 💬
    - Aturan Khusus                      : 🚫 Tanpa Follow | 🚫 Bukan Giveaway
    - Jeda antar batch                   : {GREEN}{viral_interval_min} - {viral_interval_max} Menit{RESET}
  • {YELLOW}Proteksi Hardware{RESET}                    : Browser Lock Aktif (RAM Laptop Ringan)
  • Mode Browser                         : {'Headless (Senyap)' if headless else 'Visible'}
""")

    # Jalankan kedua engine secara bersamaan (concurrent) dengan orkestrasi browser_lock
    await asyncio.gather(
        engine_original_yapper(
            post_interval_min=post_interval_min,
            post_interval_max=post_interval_max,
            headless=headless
        ),
        engine_viral_engager(
            viral_count=viral_count,
            viral_interval_min=viral_interval_min,
            viral_interval_max=viral_interval_max,
            headless=headless
        )
    )


def main():
    parser = argparse.ArgumentParser(description="Master Autonomous Crypto Bot System")
    parser.add_argument("--post-min", type=int, default=60, help="Delay minimal postingan mandiri dalam menit (default: 60 = 1 jam)")
    parser.add_argument("--post-max", type=int, default=120, help="Delay maksimal postingan mandiri dalam menit (default: 120 = 2 jam)")
    parser.add_argument("--viral-count", type=int, default=5, help="Jumlah tweet viral per batch (default: 5)")
    parser.add_argument("--viral-min", type=int, default=30, help="Delay minimal batch viral dalam menit (default: 30)")
    parser.add_argument("--viral-max", type=int, default=60, help="Delay maksimal batch viral dalam menit (default: 60)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan browser Chrome")

    args = parser.parse_args()

    try:
        asyncio.run(main_master(
            post_interval_min=args.post_min,
            post_interval_max=args.post_max,
            viral_count=args.viral_count,
            viral_interval_min=args.viral_min,
            viral_interval_max=args.viral_max,
            headless=not args.visible
        ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Master bot dihentikan oleh pengguna.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
