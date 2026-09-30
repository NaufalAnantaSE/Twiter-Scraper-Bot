import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from browser_hunter import run_hunter
from wallet_config import load_wallet_config

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def continuous_loop(category: str = "all", batch_size: int = 5, interval_minutes: int = 3, max_age_hours: float = 12.0, headless: bool = True):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║        CONTINUOUS AIRDROP HUNTER (LOOP 24/7 MODE)             ║
║  Otomatis Berburu, Eksekusi, dan Beristirahat Secara Teratur  ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    wallet_cfg = load_wallet_config()
    print(f"Pengaturan Bot:")
    print(f"  • Target Jaringan    : {MAGENTA}{BOLD}[{category.upper()}]{RESET}")
    print(f"  • Rentang Usia Tweet : {YELLOW}Hingga {max_age_hours} jam terakhir{RESET}")
    print(f"  • Batch per Siklus   : {GREEN}{batch_size} tweet{RESET}")
    print(f"  • Interval Istirahat : {YELLOW}{interval_minutes} menit antar siklus pemindaian{RESET}")
    print(f"  • Format Balasan     : {CYAN}Murni Alamat Wallet Saja (Pure Address){RESET}")
    print(f"  • EVM Wallet         : {CYAN}{wallet_cfg.get('evm_address')}{RESET}")
    print(f"  • Solana Wallet      : {CYAN}{wallet_cfg.get('solana_address')}{RESET}")
    print(f"  • Status Browser     : {'Headless (Latar Belakang)' if headless else 'Visible (Tampak di layar)'}\n", flush=True)

    cycle = 1
    total_lifetime_executed = 0

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}============================================================{RESET}")
        print(f"🔄 {BOLD}[SIKLUS KE-{cycle}] Memulai Pemindaian Tweet ({timestamp}){RESET}")
        print(f"{CYAN}============================================================{RESET}", flush=True)

        try:
            await run_hunter(
                category=category,
                target_count=batch_size,
                max_age_hours=max_age_hours,
                headless=headless
            )
        except Exception as e:
            print(f"{RED}⚠️ Peringatan pada siklus {cycle}: {e}{RESET}", flush=True)

        cycle += 1
        delay_sec = interval_minutes * 60
        next_time = datetime.fromtimestamp(datetime.now().timestamp() + delay_sec).strftime("%H:%M:%S")
        print(f"\n{YELLOW}💤 Siklus selesai. Beristirahat {interval_minutes} menit... Pemindaian berikutnya pukul {next_time}{RESET}", flush=True)

        # Hitung mundur tanpa merusak log (update berkala)
        remaining = delay_sec
        while remaining > 0:
            step = min(30, remaining)
            await asyncio.sleep(step)
            remaining -= step
            if remaining > 0:
                mins = remaining // 60
                secs = remaining % 60
                print(f"   ⏳ Masih istirahat... {mins:02d}:{secs:02d} tersisa", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Twitter Airdrop Continuous Hunter")
    parser.add_argument("-c", "--category", choices=["all", "evm", "solana"], default="all", help="Target jaringan (all, evm, solana)")
    parser.add_argument("-b", "--batch", type=int, default=5, help="Jumlah tweet per siklus (default: 5)")
    parser.add_argument("-i", "--interval", type=int, default=3, help="Jeda antar siklus dalam menit (default: 3)")
    parser.add_argument("--hours", type=float, default=12.0, help="Batas rentang usia tweet dalam jam (default: 12.0)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    try:
        asyncio.run(continuous_loop(
            category=args.category,
            batch_size=args.batch,
            interval_minutes=args.interval,
            max_age_hours=args.hours,
            headless=not args.visible
        ))
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Bot dihentikan oleh pengguna. Sampai jumpa!{RESET}")
        sys.exit(0)
