"""
Twitter / X Auto Unfollow Bot
Metode: Mengambil daftar Following langsung dari tab Following akun Twitter,
menyaring akun whitelist dan follow-back, serta melakukan unfollow secara aman.
"""

import argparse
import asyncio
import json
import logging
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page

# Memastikan output terminal Windows mendukung UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import COOKIES_FILE, RESULTS_DIR
from browser_hunter import load_playwright_cookies

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

BEARER_TOKEN = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
UNFOLLOW_HISTORY_FILE = RESULTS_DIR / "unfollowed_history.json"
DEFAULT_WHITELIST_FILE = Path(__file__).parent / "whitelist.txt"


def load_whitelist(filepath: Path = DEFAULT_WHITELIST_FILE) -> set[str]:
    """Memuat daftar username yang tidak boleh di-unfollow."""
    if not filepath.exists():
        return set()
    whitelist = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                clean = line.lstrip("@").lower()
                if clean:
                    whitelist.add(clean)
    except Exception as e:
        print(f"{YELLOW}Peringatan: Gagal membaca file whitelist ({e}){RESET}")
    return whitelist


def load_unfollowed_history() -> dict:
    """Memuat riwayat akun yang sudah pernah di-unfollow."""
    if not UNFOLLOW_HISTORY_FILE.exists():
        return {}
    try:
        with open(UNFOLLOW_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_unfollowed_entry(user_id: str, screen_name: str, name: str):
    """Mencatat akun yang berhasil di-unfollow ke riwayat."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    hist = load_unfollowed_history()
    hist[str(user_id)] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screen_name": screen_name,
        "name": name
    }
    try:
        with open(UNFOLLOW_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"{YELLOW}Gagal menyimpan riwayat unfollow: {e}{RESET}")


def extract_accounts_from_graphql(data: dict) -> list[dict]:
    """Mengekstrak daftar user dari respon GraphQL Following."""
    accounts = []
    try:
        tl = data.get("data", {}).get("user", {}).get("result", {}).get("timeline", {}).get("timeline", {})
        instructions = tl.get("instructions", [])
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                for entry in inst.get("entries", []):
                    entry_id = entry.get("entryId", "")
                    if entry_id.startswith("user-"):
                        res = entry.get("content", {}).get("itemContent", {}).get("user_results", {}).get("result", {})
                        if not res:
                            continue
                        core = res.get("core", {})
                        screen_name = core.get("screen_name")
                        name = core.get("name")
                        rest_id = res.get("rest_id") or res.get("id")
                        rel = res.get("relationship_perspectives", {})
                        following = rel.get("following", True)
                        followed_by = rel.get("followed_by", False)

                        if screen_name and rest_id:
                            accounts.append({
                                "id": str(rest_id),
                                "screen_name": screen_name,
                                "name": name or screen_name,
                                "following": following,
                                "followed_by": followed_by
                            })
    except Exception as e:
        print(f"{YELLOW}Error parsing GraphQL data: {e}{RESET}")
    return accounts


async def unfollow_user_api(page: Page, user_id: str, ct0: str) -> tuple[bool, str]:
    """
    Melakukan eksekusi unfollow menggunakan API resmi dengan sesi terotentikasi Playwright.
    """
    headers = {
        "authorization": BEARER_TOKEN,
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "content-type": "application/x-www-form-urlencoded"
    }
    try:
        resp = await page.request.post(
            "https://x.com/i/api/1.1/friendships/destroy.json",
            headers=headers,
            form={"user_id": str(user_id)}
        )
        if resp.status == 200:
            return True, "OK"
        else:
            txt = await resp.text()
            return False, f"Status {resp.status}: {txt[:100]}"
    except Exception as e:
        return False, str(e)


async def run_unfollow_bot(
    target_count: int = 20,
    keep_followers: bool = True,
    delay_min: float = 3.0,
    delay_max: float = 6.0,
    whitelist_file: Path = DEFAULT_WHITELIST_FILE,
    dry_run: bool = False,
    headless: bool = True,
    account_name: str = "fannettt"
):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║            TWITTER / X AUTO UNFOLLOW BOT (METODE 2)           ║
║   Unfollow Massal via Following List + Whitelist & Safe Delay  ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    try:
        from accounts_manager import get_active_account, switch_account
        if account_name:
            switch_account(account_name)
        active = get_active_account()
        target_screen_name = active.get("screen_name", "fannettt") if active else "fannettt"
    except Exception:
        target_screen_name = account_name or "fannettt"

    if not COOKIES_FILE.exists():
        print(f"{RED}File cookies.json tidak ditemukan! Silakan setup cookie akun terlebih dahulu.{RESET}")
        return

    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        cookie_data = json.load(f)
    ct0 = cookie_data.get("ct0", "").strip()

    whitelist = load_whitelist(whitelist_file)
    print(f"Konfigurasi:")
    print(f"  • Akun Target         : {GREEN}@{target_screen_name}{RESET}")
    print(f"  • Target Unfollow     : {GREEN}{BOLD}{target_count} akun{RESET}")
    print(f"  • Jaga Follow-Back    : {'Ya (Aman)' if keep_followers else 'Tidak (Unfollow semua)'}")
    print(f"  • Jumlah Whitelist    : {len(whitelist)} akun terlindungi")
    print(f"  • Jeda Acak per Akun  : {delay_min} - {delay_max} detik")
    print(f"  • Mode Dry Run        : {'Aktif (Simulasi saja)' if dry_run else 'Nonaktif (Eksekusi nyata)'}")
    print(f"  • Mode Browser        : {'Headless (Senyap)' if headless else 'Visible (Tampak di layar)'}\n")

    captured_accounts = []
    has_more = True
    new_data_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        await load_playwright_cookies(context)
        page = await context.new_page()

        async def on_response(response):
            if "Following?" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    parsed = extract_accounts_from_graphql(data)
                    if parsed:
                        existing_ids = {a["id"] for a in captured_accounts}
                        added = 0
                        for acc in parsed:
                            if acc["id"] not in existing_ids:
                                captured_accounts.append(acc)
                                existing_ids.add(acc["id"])
                                added += 1
                        if added > 0:
                            new_data_event.set()
                except Exception:
                    pass

        page.on("response", on_response)

        round_num = 1
        unfollowed_count = 0
        skipped_whitelist = 0
        skipped_follower = 0
        already_processed_ids = set()

        while unfollowed_count < target_count:
            captured_accounts = []
            new_data_event.clear()

            print(f"\n{CYAN}--- [PUTARAN {round_num}] Memindai Daftar Following Terbaru... ---{RESET}")
            try:
                await page.goto(f"https://x.com/{target_screen_name}/following", wait_until="domcontentloaded", timeout=40000)
            except Exception as e:
                print(f"{YELLOW}Navigasi retry... ({e}){RESET}")

            print(f"{YELLOW}Menunggu respon data Following dari Twitter API...{RESET}")
            try:
                await asyncio.wait_for(new_data_event.wait(), timeout=35)
            except asyncio.TimeoutError:
                print(f"{YELLOW}Tidak ada data baru yang dimuat dari Twitter API.{RESET}")
                break

            # Filter akun yang belum pernah diproses pada putaran sebelumnya
            new_batch = [acc for acc in captured_accounts if acc["id"] not in already_processed_ids]
            if not new_batch:
                print(f"{GREEN}Semua akun non-follower di daftar following sudah selesai diproses!{RESET}")
                break

            print(f"{GREEN}✓ Berhasil memuat {len(new_batch)} akun pada putaran ini.{RESET}\n")

            unfollowed_in_this_round = 0
            for acc in new_batch:
                if unfollowed_count >= target_count:
                    print(f"\n{GREEN}{BOLD}🎯 Target {target_count} akun unfollow telah tercapai!{RESET}")
                    break

                u_id = acc["id"]
                s_name = acc["screen_name"]
                u_name = acc["name"]
                follows_back = acc["followed_by"]
                already_processed_ids.add(u_id)

                # Cek Whitelist
                if s_name.lower() in whitelist:
                    print(f"  [{unfollowed_count + 1}] @{s_name} ({u_name}) 🛡️  {YELLOW}[SKIP - WHITELIST]{RESET}")
                    skipped_whitelist += 1
                    continue

                # Cek Follow-Back
                if keep_followers and follows_back:
                    print(f"  [{unfollowed_count + 1}] @{s_name} ({u_name}) 👥 {CYAN}[SKIP - FOLLOWS YOU BACK]{RESET}")
                    skipped_follower += 1
                    continue

                # Eksekusi Unfollow
                status_text = "TIDAK Follow-Back"
                print(f"  [{unfollowed_count + 1}] @{s_name} ({u_name}) - {status_text} ... ", end="", flush=True)

                if dry_run:
                    print(f"{YELLOW}[DRY-RUN - WOULD UNFOLLOW]{RESET}")
                    unfollowed_count += 1
                    unfollowed_in_this_round += 1
                    continue

                ok, msg = await unfollow_user_api(page, u_id, ct0)
                if ok:
                    unfollowed_count += 1
                    unfollowed_in_this_round += 1
                    save_unfollowed_entry(u_id, s_name, u_name)
                    print(f"{GREEN}{BOLD}[BERHASIL UNFOLLOW ✓]{RESET} ({unfollowed_count} total)")
                else:
                    print(f"{RED}[GAGAL: {msg}]{RESET}")

                # Jeda alami antar aksi agar akun aman dari limit Twitter
                if unfollowed_count < target_count:
                    sleep_time = random.uniform(delay_min, delay_max)
                    await asyncio.sleep(sleep_time)

            if unfollowed_in_this_round == 0 and not dry_run:
                print(f"\n{GREEN}Tidak ada akun non-follower tersisa yang perlu di-unfollow.{RESET}")
                break

            round_num += 1

        print(f"\n{CYAN}============================================================{RESET}")
        print(f"{GREEN}{BOLD}🎉 PROSES UNFOLLOW SELESAI!{RESET}")
        print(f"  • Total di-unfollow    : {BOLD}{unfollowed_count}{RESET} akun")
        print(f"  • Dilewati (Whitelist) : {skipped_whitelist} akun")
        print(f"  • Dilewati (Followback): {skipped_follower} akun")
        print(f"  • Log Riwayat          : {UNFOLLOW_HISTORY_FILE}\n")

        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Twitter / X Auto Unfollow Bot")
    parser.add_argument("-m", "--max", type=int, default=20, help="Jumlah akun yang ingin di-unfollow (default: 20)")
    parser.add_argument("--unfollow-all", action="store_true", help="Unfollow semua non-followers yang ditemukan")
    parser.add_argument("--include-followers", action="store_true", help="Jangan lewati akun yang follow-back (unfollow semua)")
    parser.add_argument("--delay-min", type=float, default=3.0, help="Delay minimal antar unfollow dalam detik (default: 3.0)")
    parser.add_argument("--delay-max", type=float, default=6.0, help="Delay maksimal antar unfollow dalam detik (default: 6.0)")
    parser.add_argument("--whitelist", type=str, default="whitelist.txt", help="Path ke file whitelist (default: whitelist.txt)")
    parser.add_argument("--all-accounts", action="store_true", help="Jalankan unfollow untuk semua akun yang terdaftar di accounts.json")
    parser.add_argument("-a", "--account", type=str, default="fannettt", help="Username akun target (default: fannettt)")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi saja tanpa melakukan unfollow")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    if args.all_accounts:
        from multi_account_unfollow import main_loop
        try:
            asyncio.run(main_loop(
                target_account="",
                keep_followers=not args.include_followers,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                whitelist_file=Path(args.whitelist),
                dry_run=args.dry_run,
                headless=not args.visible
            ))
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot unfollow dihentikan oleh pengguna.{RESET}")
            sys.exit(0)
        return

    max_target = 9999 if args.unfollow_all else args.max
    keep_followers = not args.include_followers

    try:
        asyncio.run(run_unfollow_bot(
            target_count=max_target,
            keep_followers=keep_followers,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            whitelist_file=Path(args.whitelist),
            dry_run=args.dry_run,
            headless=not args.visible,
            account_name=args.account
        ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Bot unfollow dihentikan oleh pengguna.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
