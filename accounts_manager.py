"""
Multi-Account Manager for Twitter / X Bots
Memungkinkan penyimpanan beberapa akun Twitter (auth_token & ct0),
berpindah antar akun secara instan, dan sinkronisasi otomatis ke cookies.json.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Terminal utf-8 support for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, COOKIES_FILE

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

logger = logging.getLogger(__name__)


def load_accounts() -> dict:
    """Memuat data akun dari accounts.json."""
    if not ACCOUNTS_FILE.exists():
        # Jika belum ada file accounts.json tapi cookies.json ada, buat entri awal
        default_data = {
            "active_account": "",
            "accounts": {}
        }
        if COOKIES_FILE.exists():
            try:
                with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                    c = json.load(f)
                if c.get("auth_token") and c.get("ct0"):
                    default_data["accounts"]["default"] = {
                        "screen_name": "default",
                        "name": "Default Account",
                        "auth_token": c["auth_token"],
                        "ct0": c["ct0"],
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    default_data["active_account"] = "default"
            except Exception:
                pass
        save_accounts(default_data)
        return default_data

    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal membaca accounts.json: {e}")
        return {"active_account": "", "accounts": {}}


def save_accounts(data: dict):
    """Menyimpan data akun ke accounts.json."""
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Gagal menulis accounts.json: {e}")


def get_active_account() -> dict | None:
    """Mendapatkan akun yang sedang aktif."""
    data = load_accounts()
    active_name = data.get("active_account", "")
    accounts = data.get("accounts", {})

    for key, acc in accounts.items():
        if key.lower() == active_name.lower() or acc.get("screen_name", "").lower() == active_name.lower():
            return acc
    return None


def sync_active_cookies(account: dict) -> bool:
    """Menulis token akun aktif langsung ke cookies.json."""
    try:
        cookie_payload = {
            "auth_token": account.get("auth_token", "").strip(),
            "ct0": account.get("ct0", "").strip()
        }
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookie_payload, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Gagal menyinkronkan cookies.json: {e}")
        return False


def switch_account(screen_name: str) -> bool:
    """Berpindah ke akun yang ditentukan berdasarkan username / screen_name."""
    data = load_accounts()
    accounts = data.get("accounts", {})
    clean_target = screen_name.strip().lstrip("@").lower()

    matched_key = None
    for key, acc in accounts.items():
        if key.lower() == clean_target or acc.get("screen_name", "").lower() == clean_target:
            matched_key = key
            break

    if not matched_key:
        print(f"{RED}❌ Akun '@{screen_name}' tidak ditemukan dalam daftar tersimpan.{RESET}")
        return False

    acc_info = accounts[matched_key]
    data["active_account"] = acc_info.get("screen_name", matched_key)
    save_accounts(data)

    if sync_active_cookies(acc_info):
        print(f"{GREEN}✓ Berhasil beralih ke akun: @{acc_info.get('screen_name')} ({acc_info.get('name', '')}){RESET}")
        print(f"  {CYAN}cookies.json telah diperbarui otomatis untuk semua bot.{RESET}")
        return True
    else:
        print(f"{RED}❌ Gagal menyinkronkan cookies.json.{RESET}")
        return False


def add_account(screen_name: str, name: str, auth_token: str, ct0: str, set_as_active: bool = False) -> bool:
    """Menambahkan atau memperbarui akun Twitter ke accounts.json."""
    data = load_accounts()
    clean_user = screen_name.strip().lstrip("@")
    key = clean_user.lower()

    data.setdefault("accounts", {})[key] = {
        "screen_name": clean_user,
        "name": name.strip() or clean_user,
        "auth_token": auth_token.strip().replace('"', '').replace("'", ""),
        "ct0": ct0.strip().replace('"', '').replace("'", ""),
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Jika baru satu-satunya akun atau diminta aktif
    if set_as_active or not data.get("active_account"):
        data["active_account"] = clean_user
        sync_active_cookies(data["accounts"][key])

    save_accounts(data)
    print(f"{GREEN}✓ Akun @{clean_user} ({name}) berhasil disimpan!{RESET}")
    return True


def remove_account(screen_name: str) -> bool:
    """Menghapus akun dari accounts.json."""
    data = load_accounts()
    clean_target = screen_name.strip().lstrip("@").lower()
    accounts = data.get("accounts", {})

    matched_key = None
    for key, acc in accounts.items():
        if key.lower() == clean_target or acc.get("screen_name", "").lower() == clean_target:
            matched_key = key
            break

    if not matched_key:
        print(f"{RED}❌ Akun '@{screen_name}' tidak ditemukan.{RESET}")
        return False

    removed_acc = accounts.pop(matched_key)
    print(f"{YELLOW}Akun @{removed_acc.get('screen_name')} telah dihapus.{RESET}")

    # Jika akun yang dihapus sedang aktif, pilih akun berikutnya
    if data.get("active_account", "").lower() == clean_target:
        if accounts:
            next_key = next(iter(accounts))
            next_acc = accounts[next_key]
            data["active_account"] = next_acc.get("screen_name", next_key)
            sync_active_cookies(next_acc)
            print(f"{CYAN}Akun aktif dialihkan otomatis ke: @{next_acc.get('screen_name')}{RESET}")
        else:
            data["active_account"] = ""
            if COOKIES_FILE.exists():
                COOKIES_FILE.unlink()
            print(f"{YELLOW}Tidak ada akun tersisa. cookies.json telah dibersihkan.{RESET}")

    save_accounts(data)
    return True


async def verify_tokens_with_browser(auth_token: str, ct0: str) -> tuple[bool, str, str]:
    """
    Memverifikasi token Twitter menggunakan Playwright browser headless.
    Mengembalikan (success, screen_name, display_name).
    """
    from playwright.async_api import async_playwright

    auth_token = auth_token.strip().replace('"', '').replace("'", "")
    ct0 = ct0.strip().replace('"', '').replace("'", "")

    if not auth_token or not ct0:
        return False, "Token tidak boleh kosong", ""

    print(f"   {CYAN}🌐 Memverifikasi token via browser Chrome headless...{RESET}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            cookies = [
                {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
                {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
                {"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"},
                {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
            ]
            await context.add_cookies(cookies)
            page = await context.new_page()

            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Cek redirect ke login / flow
            if "i/flow/login" in page.url or "login" in page.url:
                await browser.close()
                return False, "Token ditolak oleh Twitter (sesi kedaluwarsa atau salah)", ""

            screen_name = ""
            display_name = ""

            # 1. Cari via profile link testid
            profile_link = await page.query_selector('a[data-testid="AppTabBar_Profile_Link"], a[aria-label*="Profile" i], a[aria-label*="Profil" i]')
            if profile_link:
                href = await profile_link.get_attribute("href")
                if href and "/" in href:
                    clean = href.strip("/").split("/")[-1]
                    if clean and not clean.startswith("i/"):
                        screen_name = clean

            # 2. Cari via account switcher button
            account_switcher = await page.query_selector('div[data-testid="SideNav_AccountSwitcher_Button"]')
            if account_switcher:
                badge_text = await account_switcher.inner_text()
                lines = [l.strip() for l in badge_text.splitlines() if l.strip()]
                if lines:
                    display_name = lines[0]
                    if not screen_name:
                        for l in lines:
                            if l.startswith("@"):
                                screen_name = l.lstrip("@")
                                break

            # 3. Fallback: Cari dari link profil di halaman
            if not screen_name:
                links = await page.eval_on_selector_all("a", "els => els.map(e => e.href)")
                ignore_paths = {"home", "explore", "notifications", "messages", "settings", "compose", "i", "search", "tos", "privacy"}
                for l in links:
                    if "x.com/" in l:
                        cand = l.split("x.com/")[-1].strip("/").split("/")[0].split("?")[0]
                        if cand and cand.lower() not in ignore_paths and len(cand) >= 3 and cand.isalnum():
                            screen_name = cand
                            break

            # 4. Ambil display name jika belum didapat
            if screen_name and not display_name:
                try:
                    await page.goto(f"https://x.com/{screen_name}", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    name_el = await page.query_selector('div[data-testid="UserName"]')
                    if name_el:
                        t = await name_el.inner_text()
                        lines = [l.strip() for l in t.splitlines() if l.strip()]
                        if lines:
                            display_name = lines[0]
                except Exception:
                    display_name = screen_name

            await browser.close()

            if screen_name:
                return True, screen_name, display_name or screen_name
            else:
                return False, "Tidak dapat menemukan username akun dari halaman Twitter", ""

    except Exception as e:
        return False, f"Error koneksi browser: {e}", ""


def list_accounts_cli():
    """Menampilkan daftar akun tersimpan ke terminal."""
    data = load_accounts()
    active_name = data.get("active_account", "").lower()
    accounts = data.get("accounts", {})

    print(f"\n{CYAN}{BOLD}╔════════════════════ DAFTAR AKUN TWITTER / X ════════════════════╗{RESET}")
    if not accounts:
        print(f"  {YELLOW}Belum ada akun yang tersimpan.{RESET}")
    else:
        for idx, (key, acc) in enumerate(accounts.items(), 1):
            is_active = (key.lower() == active_name or acc.get("screen_name", "").lower() == active_name)
            status_badge = f"{GREEN}{BOLD}[AKTIF]{RESET}" if is_active else f"{YELLOW}[STANDBY]{RESET}"
            uname = acc.get("screen_name", key)
            dname = acc.get("name", "")
            added = acc.get("added_at", "-")
            print(f"  [{idx}] {status_badge} {BOLD}@{uname}{RESET} ({dname})")
            print(f"      Ditambahkan : {added}")
            token_mask = acc.get("auth_token", "")[:8] + "..." + acc.get("auth_token", "")[-6:] if acc.get("auth_token") else "-"
            print(f"      auth_token  : {token_mask}")
    print(f"{CYAN}╚═════════════════════════════════════════════════════════════════╝{RESET}\n")


async def interactive_account_menu():
    """Menu CLI interaktif untuk manajemen akun."""
    while True:
        list_accounts_cli()
        active = get_active_account()
        active_display = f"@{active['screen_name']}" if active else f"{RED}Belum ada{RESET}"
        print(f"Akun Aktif Saat Ini: {GREEN}{BOLD}{active_display}{RESET}\n")
        print(f"[{GREEN}1{RESET}] 🔄 Beralih Akun Aktif (Switch Account)")
        print(f"[{GREEN}2{RESET}] ➕ Tambah Akun Baru (Input auth_token & ct0)")
        print(f"[{GREEN}3{RESET}] 🗑️  Hapus Akun")
        print(f"[{RED}0{RESET}] 🔙 Kembali ke Menu Utama")

        choice = input("\nPilih opsi [1/2/3/0]: ").strip()

        if choice == "1":
            data = load_accounts()
            accounts = list(data.get("accounts", {}).values())
            if not accounts:
                print(f"{YELLOW}Tidak ada akun tersimpan.{RESET}")
                continue

            print(f"\nPilih akun tujuan:")
            for i, acc in enumerate(accounts, 1):
                print(f"  [{i}] @{acc.get('screen_name')} ({acc.get('name')})")

            sel = input("\nNomor akun: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(accounts):
                target = accounts[int(sel) - 1].get("screen_name")
                switch_account(target)
            else:
                print(f"{RED}Pilihan tidak valid.{RESET}")

        elif choice == "2":
            print(f"\n{CYAN}{BOLD}--- Tambah Akun Twitter Baru ---{RESET}")
            print("Silakan masukkan token dari DevTools browser Anda:")
            print("(F12 -> Application -> Cookies -> https://x.com)")
            
            auth_token = input("Masukkan auth_token: ").strip()
            if not auth_token:
                print(f"{RED}auth_token tidak boleh kosong.{RESET}")
                continue

            ct0 = input("Masukkan ct0: ").strip()
            if not ct0:
                print(f"{RED}ct0 tidak boleh kosong.{RESET}")
                continue

            print(f"\n{YELLOW}Memverifikasi akun via browser... Mohon tunggu sebentar.{RESET}")
            ok, uname, dname = await verify_tokens_with_browser(auth_token, ct0)

            if ok:
                print(f"{GREEN}✓ Akun terverifikasi sebagai: @{uname} ({dname}){RESET}")
                set_active = input(f"Jadikan @{uname} sebagai akun aktif sekarang? [y/n default: y]: ").strip().lower()
                is_active = (set_active != "n")
                add_account(uname, dname, auth_token, ct0, set_as_active=is_active)
            else:
                print(f"{RED}❌ Verifikasi gagal: {uname}{RESET}")
                fallback = input("Tetap simpan manual? [y/n]: ").strip().lower()
                if fallback == "y":
                    manual_uname = input("Username (tanpa @): ").strip().lstrip("@")
                    manual_name = input("Nama Tampilan: ").strip()
                    if manual_uname:
                        add_account(manual_uname, manual_name or manual_uname, auth_token, ct0, set_as_active=False)

        elif choice == "3":
            uname = input("Masukkan username akun yang ingin dihapus (tanpa @): ").strip().lstrip("@")
            if uname:
                confirm = input(f"Yakin ingin menghapus @{uname}? [y/n]: ").strip().lower()
                if confirm == "y":
                    remove_account(uname)

        elif choice == "0":
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Twitter Multi-Account Manager")
    parser.add_argument("--list", "-l", action="store_true", help="Tampilkan daftar semua akun")
    parser.add_argument("--active", "-a", action="store_true", help="Tampilkan akun yang sedang aktif")
    parser.add_argument("--switch", "-s", type=str, help="Beralih ke akun tertentu (berdasarkan username)")
    parser.add_argument("--remove", "-r", type=str, help="Hapus akun tertentu")
    args = parser.parse_args()

    if args.list:
        list_accounts_cli()
    elif args.active:
        acc = get_active_account()
        if acc:
            print(f"Akun aktif: @{acc.get('screen_name')} ({acc.get('name')})")
        else:
            print("Belum ada akun aktif.")
    elif args.switch:
        switch_account(args.switch)
    elif args.remove:
        remove_account(args.remove)
    else:
        asyncio.run(interactive_account_menu())
