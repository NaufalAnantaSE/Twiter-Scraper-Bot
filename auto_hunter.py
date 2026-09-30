import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from browser_hunter import run_hunter
from wallet_config import load_wallet_config, is_valid_evm_address, is_valid_solana_address
from config import COOKIES_FILE

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def main():
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         DIRECT AUTO-EXECUTE: AIRDROP & DROP ADDRESS           ║
║   Scrape ➔ Like ➔ Retweet ➔ Follow ➔ Drop EVM / Solana Wallet ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    # 1. Cek Cookie
    if not COOKIES_FILE.exists():
        print(f"{RED}❌ File cookies.json tidak ditemukan!{RESET}")
        print("Silakan masukkan cookie terlebih dahulu di main.py.")
        sys.exit(1)

    # 2. Cek Konfigurasi Wallet
    wallet_cfg = load_wallet_config()
    evm = wallet_cfg.get("evm_address", "")
    sol = wallet_cfg.get("solana_address", "")

    print(f"Status Konfigurasi Wallet:")
    print(f"  • EVM Address    : {GREEN if is_valid_evm_address(evm) else RED}{evm or '[KOSONG]'}{RESET}")
    print(f"  • Solana Address : {GREEN if is_valid_solana_address(sol) else RED}{sol or '[KOSONG]'}{RESET}")
    print(f"  • Tag Teman      : {YELLOW}{', '.join(wallet_cfg.get('tag_friends', [])) if wallet_cfg.get('tag_friends') else '[None]'}{RESET}")

    # 3. Parameter Eksekusi
    print(f"\n{BOLD}Pilih Target Jaringan yang Ingin Dikerjakan Langsung:{RESET}")
    print(f"[{GREEN}1{RESET}] Otomatis (EVM + Solana sesuai tweet) ⭐")
    print(f"[{GREEN}2{RESET}] Khusus EVM (0x / Ethereum / BSC / Base)")
    print(f"[{GREEN}3{RESET}] Khusus Solana (SOL / Phantom)")

    net_choice = input("Pilihan [1/2/3, default: 1]: ").strip()
    category = "solana" if net_choice == "3" else ("evm" if net_choice == "2" else "all")

    max_input = input("Berapa tweet giveaway yang ingin dieksekusi sekarang? [default: 10]: ").strip()
    target_count = int(max_input) if max_input.isdigit() and int(max_input) > 0 else 10

    show_browser = input("Tampilkan jendela browser Chrome saat bot bekerja? [y/N, default: N (Latar belakang)]: ").strip().lower()
    headless = show_browser != "y"

    print(f"\n{MAGENTA}🚀 Memulai perburuan airdrop... Menjalankan browser Chrome...{RESET}\n")

    await run_hunter(
        category=category,
        target_count=target_count,
        headless=headless
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Program dihentikan oleh pengguna.{RESET}")
        sys.exit(0)
