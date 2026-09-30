import asyncio
import argparse
import random
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from giveaway_templates import generate_solana_giveaway, generate_evm_giveaway
from tweet_poster import post_tweet, RESULTS_DIR

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def run_giveaway_cycle(network: str = "solana", custom_amount: str = None, headless: bool = True) -> bool:
    """Menghasilkan tweet giveaway baru yang unik dan mempostingnya ke Twitter."""
    net = network.upper()
    if net == "EVM":
        tweet_content = generate_evm_giveaway(username="fannettt", custom_amount=custom_amount)
    else:
        tweet_content = generate_solana_giveaway(username="fannettt", custom_amount=custom_amount)

    ok, tweet_url, err = await post_tweet(tweet_text=tweet_content, network=net, headless=headless)
    if not ok:
        print(f"{RED}❌ Gagal memposting giveaway: {err}{RESET}", flush=True)
        return False
    return True

async def giveaway_scheduler_loop(
    min_minutes: int = 30,
    max_minutes: int = 60,
    network: str = "solana",
    custom_amount: str = None,
    headless: bool = True
):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         AUTO TWEET GIVEAWAY (SCHEDULED 24/7 BOT)              ║
║    Otomatis Membuat & Memposting Tweet Giveaway Berkala       ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    print(f"Konfigurasi Scheduler:")
    print(f"  • Target Jaringan    : {MAGENTA}{BOLD}[{network.upper()}]{RESET}")
    print(f"  • Rentang Jeda Acak  : {GREEN}{min_minutes} s/d {max_minutes} Menit (Random Range){RESET}")
    print(f"  • Nominal Hadiah     : {YELLOW}{custom_amount or 'Otomatis / Bervariasi ($50 - $500)'}{RESET}")
    print(f"  • Variasi Template   : {CYAN}Anti-Duplicate (Kata, emoji, rules diacak otomatis){RESET}")
    print(f"  • Status Browser     : {'Headless (Latar Belakang)' if headless else 'Visible'}\n", flush=True)

    post_count = 1

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}============================================================{RESET}")
        print(f"🚀 {BOLD}[POSTINGAN KE-{post_count}] Memulai Pembuatan Tweet Giveaway ({timestamp}){RESET}")
        print(f"{CYAN}============================================================{RESET}", flush=True)

        try:
            success = await run_giveaway_cycle(
                network=network,
                custom_amount=custom_amount,
                headless=headless
            )
            if success:
                print(f"{GREEN}✓ Selesai posting giveaway ke-{post_count}!{RESET}", flush=True)
            else:
                print(f"{YELLOW}⚠️ Postingan ke-{post_count} mengalami kendala.{RESET}", flush=True)
        except Exception as e:
            print(f"{RED}⚠️ Error tidak terduga pada scheduler: {e}{RESET}", flush=True)

        post_count += 1
        
        # Tentukan jeda acak antara min_minutes dan max_minutes (contoh 30 - 60 menit)
        delay_minutes = random.randint(min_minutes, max_minutes)
        delay_sec = delay_minutes * 60
        next_time = datetime.fromtimestamp(datetime.now().timestamp() + delay_sec).strftime("%H:%M:%S")
        print(f"\n{YELLOW}💤 Jeda acak aktif ({min_minutes}-{max_minutes} menit)... Postingan berikutnya pukul {next_time} ({delay_minutes} menit lagi){RESET}", flush=True)

        remaining = delay_sec
        while remaining > 0:
            step = min(30, remaining)
            await asyncio.sleep(step)
            remaining -= step
            if remaining > 0 and remaining % 300 == 0:  # Update setiap 5 menit
                mins = remaining // 60
                secs = remaining % 60
                print(f"   ⏳ Masih dalam jeda acak... {mins:02d} menit {secs:02d} detik tersisa menuju tweet berikutnya", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Tweet Giveaway Scheduler")
    parser.add_argument("-n", "--network", choices=["solana", "evm"], default="solana", help="Pilihan jaringan (default: solana)")
    parser.add_argument("--min-delay", type=int, default=30, help="Jeda minimal dalam menit (default: 30)")
    parser.add_argument("--max-delay", type=int, default=60, help="Jeda maksimal dalam menit (default: 60)")
    parser.add_argument("-i", "--interval", type=float, default=None, help="Jeda tetap dalam jam (opsional)")
    parser.add_argument("-a", "--amount", type=str, default=None, help="Nominal kustom (contoh: '$100')")
    parser.add_argument("--once", action="store_true", help="Hanya posting 1 kali lalu selesai (tanpa jadwal loop)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    if args.once:
        print(f"{CYAN}Menjalankan mode posting tunggal (1x post)...{RESET}")
        asyncio.run(run_giveaway_cycle(
            network=args.network,
            custom_amount=args.amount,
            headless=not args.visible
        ))
    else:
        # Jika user memasukkan --interval secara spesifik, jadikan rentang di sekitar angka itu
        if args.interval is not None:
            min_m = int(args.interval * 60)
            max_m = int(args.interval * 60)
        else:
            min_m = args.min_delay
            max_m = args.max_delay

        try:
            asyncio.run(giveaway_scheduler_loop(
                min_minutes=min_m,
                max_minutes=max_m,
                network=args.network,
                custom_amount=args.amount,
                headless=not args.visible
            ))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}Scheduler dihentikan oleh pengguna.{RESET}")
            sys.exit(0)
