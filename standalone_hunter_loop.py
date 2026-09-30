"""
Standalone Sequential Multi-Account Giveaway Hunter Loop
Menjalankan scraping giveaway secara mandiri, berurutan per-akun (hemat RAM & CPU laptop):
1. Menjalankan 1 akun pada satu waktu (membuka 1 browser, menyelesaikan target, lalu menutup browser secara tuntas agar RAM 100% bersih).
2. Menjalankan semua 4 aksi wajib:
   ❤️ Like
   🔁 Retweet
   👤 Follow Author
   👛 Drop Address (EVM / Solana sesuai tweet)
3. Berpindah otomatis antar 8 akun dengan jeda alami.
4. Looping tanpa henti siklus demi siklus dengan jeda antar ronde 10 - 20 menit.
"""

import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, RESULTS_DIR
from accounts_manager import load_accounts
from browser_hunter import run_hunter

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def sequential_giveaway_loop(
    category: str = "ALL",
    tweets_per_account: int = 5,
    max_age_hours: float = 12.0,
    round_delay_min_minutes: int = 10,
    round_delay_max_minutes: int = 20,
    headless: bool = True
):
    cycle = 1

    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║   🤖 STANDALONE MULTI-ACCOUNT GIVEAWAY HUNTER (SEQUENTIAL)   ║
║   Like ❤️  ➔ Retweet 🔁 ➔ Follow 👤 ➔ Drop Wallet 👛        ║
║   Mode: Berurutan 1 per 1 (Sangat Hemat RAM & CPU Laptop)    ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    while True:
        acc_data = load_accounts()
        accounts_dict = acc_data.get("accounts", {})

        if not accounts_dict:
            print(f"{RED}❌ Tidak ada akun di accounts.json!{RESET}")
            await asyncio.sleep(30)
            continue

        account_keys = list(accounts_dict.keys())
        total_accounts = len(account_keys)

        print(f"\n{MAGENTA}{BOLD}================================================================{RESET}")
        print(f"{MAGENTA}{BOLD}🚀 MEMULAI RONDE SIKLUS #{cycle} ({total_accounts} AKUN TERDAFTAR){RESET}")
        print(f"⏰ Waktu Mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target per Akun: {tweets_per_account} Tweet [{category}] (Maks usia: {max_age_hours} jam)")
        print(f"{MAGENTA}{BOLD}================================================================{RESET}\n")

        round_successful_tweets = 0

        for idx, acc_key in enumerate(account_keys, 1):
            acc_info = accounts_dict[acc_key]
            uname = acc_info.get("screen_name", acc_key)
            dname = acc_info.get("name", uname)
            evm = acc_info.get("evm_address", "")
            sol = acc_info.get("solana_address", "")

            print(f"\n{CYAN}┌─────────────────────────────────────────────────────────────┐{RESET}")
            print(f"{CYAN}│ 👤 [{idx}/{total_accounts}] Menjalankan Akun: {BOLD}@{uname}{RESET}{CYAN} ({dname}){' ' * max(0, 31 - len(uname) - len(dname))}│{RESET}")
            print(f"{CYAN}│ 👛 EVM: {evm[:10]}...{evm[-6:] if evm else 'KOSONG'} | SOL: {sol[:8]}...{sol[-4:] if sol else 'KOSONG'}{' ' * max(0, 18 - (16 if evm else 6) - (12 if sol else 6))}│{RESET}")
            print(f"{CYAN}└─────────────────────────────────────────────────────────────┘{RESET}")

            if not evm and not sol:
                print(f"{YELLOW}⚠️ Akun @{uname} belum memiliki wallet EVM/Solana, dilewati.{RESET}")
                continue

            try:
                # Menjalankan 1 perburuan untuk akun ini
                # Setelah selesai, browser otomatis ditutup tuntas di dalam run_hunter
                await run_hunter(
                    category=category,
                    target_count=tweets_per_account,
                    max_age_hours=max_age_hours,
                    headless=headless,
                    account_info=acc_info
                )
                print(f"{GREEN}✓ Selesai memproses giveaway untuk @{uname}! (Browser ditutup & RAM dibersihkan){RESET}")
            except Exception as e:
                print(f"{RED}❌ Kendala pada akun @{uname}: {e}{RESET}")

            # Langsung beralih ke akun berikutnya tanpa jeda
            pass

        # Hitung total entri di airdrop_history.json
        total_entries = 0
        hist_file = RESULTS_DIR / "airdrop_history.json"
        if hist_file.exists():
            try:
                with open(hist_file, "r", encoding="utf-8") as f:
                    total_entries = len(json.load(f))
            except Exception:
                pass

        # Selesai satu ronde untuk semua akun
        round_sleep_sec = random.randint(round_delay_min_minutes * 60, round_delay_max_minutes * 60)
        rem_m = round_sleep_sec // 60
        rem_s = round_sleep_sec % 60

        print(f"\n{GREEN}{BOLD}════════════════════════════════════════════════════════════════{RESET}")
        print(f"{GREEN}{BOLD}🎉 RONDE SIKLUS #{cycle} SELESAI UNTUK SEMUA AKUN!{RESET}")
        print(f"📊 Total Keseluruhan Giveaway Terdaftar di Sistem: {BOLD}{total_entries}{RESET}")
        print(f"⏱️ Istirahat antar ronde: {rem_m} menit {rem_s} detik sebelum Siklus #{cycle + 1}...")
        print(f"{GREEN}{BOLD}════════════════════════════════════════════════════════════════{RESET}\n")

        await asyncio.sleep(round_sleep_sec)
        cycle += 1

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Standalone Multi-Account Giveaway Hunter Loop")
    parser.add_argument("-c", "--category", choices=["ALL", "EVM", "SOLANA", "all", "evm", "solana"], default="ALL", help="Kategori (ALL, EVM, SOLANA)")
    parser.add_argument("-m", "--max", type=int, default=5, help="Jumlah tweet target per akun per ronde (default: 5)")
    parser.add_argument("--hours", type=float, default=12.0, help="Batas usia tweet maksimal dalam jam (default: 12.0)")
    parser.add_argument("--min-delay", type=int, default=10, help="Jeda minimal antar ronde dalam menit (default: 10)")
    parser.add_argument("--max-delay", type=int, default=20, help="Jeda maksimal antar ronde dalam menit (default: 20)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    try:
        asyncio.run(sequential_giveaway_loop(
            category=args.category.upper(),
            tweets_per_account=args.max,
            max_age_hours=args.hours,
            round_delay_min_minutes=args.min_delay,
            round_delay_max_minutes=args.max_delay,
            headless=not args.visible
        ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Program dihentikan oleh pengguna.{RESET}")
        sys.exit(0)
