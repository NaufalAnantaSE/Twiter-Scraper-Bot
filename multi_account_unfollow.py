"""
Multi-Account Mass Unfollow Bot for Twitter / X
Eksekusi pembersihan total daftar Following untuk SEMUA akun yang terdaftar di accounts.json:
1. Membuka 1 akun per sesi secara berurutan (hemat RAM & CPU).
2. Mendeteksi username asli via Playwright secara otomatis.
3. Membuka tab Following dan meng-intercept respon GraphQL Twitter.
4. Menjalankan Unfollow via official API friendships/destroy.json secara instan & aman.
5. Melakukan auto-scroll untuk memuat halaman Following berikutnya sampai tuntas 0 Following.
6. Membersihkan RAM dan beralih ke akun berikutnya.
"""

import argparse
import asyncio
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page

# Memastikan terminal Windows mendukung UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, COOKIES_FILE, RESULTS_DIR
from accounts_manager import load_accounts, save_accounts, sync_active_cookies

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
        print(f"{YELLOW}Peringatan: Gagal membaca file whitelist ({e}){RESET}", flush=True)
    return whitelist


def load_unfollowed_history() -> dict:
    if not UNFOLLOW_HISTORY_FILE.exists():
        return {}
    try:
        with open(UNFOLLOW_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def save_unfollowed_entry(account_name: str, user_id: str, screen_name: str, name: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    hist = load_unfollowed_history()
    hist.setdefault(account_name, {})
    hist[account_name][str(user_id)] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screen_name": screen_name,
        "name": name
    }
    try:
        with open(UNFOLLOW_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def extract_accounts_from_graphql(data: dict) -> list[dict]:
    """Mengekstrak daftar user dari respon GraphQL Following Twitter."""
    accounts = []
    try:
        user_res = data.get("data", {}).get("user", {}).get("result", {})
        tl = (
            user_res.get("timeline", {}).get("timeline", {})
            or user_res.get("timeline_v2", {}).get("timeline", {})
        )
        instructions = tl.get("instructions", [])
        for inst in instructions:
            entries = inst.get("entries", [])
            for entry in entries:
                entry_id = entry.get("entryId", "")
                if entry_id.startswith("user-") or "user" in entry_id.lower():
                    item_content = entry.get("content", {}).get("itemContent", {})
                    user_res_inner = item_content.get("user_results", {}).get("result", {})
                    if not user_res_inner or user_res_inner.get("__typename") == "UserUnavailable":
                        continue

                    legacy = user_res_inner.get("legacy", {})
                    core = user_res_inner.get("core", {})

                    screen_name = (
                        legacy.get("screen_name")
                        or core.get("screen_name")
                        or user_res_inner.get("screen_name")
                    )
                    name = (
                        legacy.get("name")
                        or core.get("name")
                        or user_res_inner.get("name")
                        or screen_name
                    )
                    rest_id = (
                        user_res_inner.get("rest_id")
                        or user_res_inner.get("id")
                        or legacy.get("id_str")
                    )
                    rel = user_res_inner.get("relationship_perspectives", {})
                    followed_by = legacy.get("followed_by", False) or rel.get("followed_by", False)
                    following = legacy.get("following", True) or rel.get("following", True)

                    if screen_name and rest_id:
                        accounts.append({
                            "id": str(rest_id),
                            "screen_name": screen_name,
                            "name": name,
                            "following": following,
                            "followed_by": followed_by
                        })
    except Exception:
        pass
    return accounts


async def unfollow_user_api(page: Page, user_id: str, screen_name: str, ct0: str) -> tuple[bool, str]:
    """Eksekusi unfollow via official API X."""
    headers = {
        "authorization": BEARER_TOKEN,
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "content-type": "application/x-www-form-urlencoded"
    }
    payload = {"user_id": str(user_id)} if user_id else {"screen_name": str(screen_name)}
    try:
        resp = await page.request.post(
            "https://x.com/i/api/1.1/friendships/destroy.json",
            headers=headers,
            form=payload
        )
        if resp.status == 200:
            return True, "OK"
        elif resp.status == 429:
            return False, "RATE_LIMIT_429"
        else:
            txt = await resp.text()
            return False, f"Status {resp.status}: {txt[:80]}"
    except Exception as e:
        return False, str(e)


async def unfollow_account_session(
    account_key: str,
    account_info: dict,
    whitelist: set[str],
    keep_followers: bool = False,
    delay_min: float = 0.3,
    delay_max: float = 0.8,
    dry_run: bool = False,
    headless: bool = True
) -> dict:
    """Memproses unfollow tuntas untuk 1 akun."""
    auth_token = account_info.get("auth_token", "").strip()
    ct0 = account_info.get("ct0", "").strip()
    stored_name = account_info.get("screen_name", account_key).strip()

    stats = {
        "account": stored_name,
        "unfollowed": 0,
        "skipped_whitelist": 0,
        "skipped_followers": 0,
        "status": "SUCCESS"
    }

    if not auth_token or not ct0:
        print(f"  {RED}❌ Token auth_token atau ct0 kosong, dilewati.{RESET}", flush=True)
        stats["status"] = "NO_TOKEN"
        return stats

    # Pastikan cookies.json sinkron
    sync_active_cookies(account_info)

    captured_accounts = []
    known_account_ids = set()
    new_data_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        # Inject cookies
        cookies = [
            {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
        ]
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Intercept respon GraphQL Following
        async def on_response(response):
            if "Following?" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    parsed = extract_accounts_from_graphql(data)
                    if parsed:
                        added = 0
                        for acc in parsed:
                            if acc["id"] not in known_account_ids:
                                captured_accounts.append(acc)
                                known_account_ids.add(acc["id"])
                                added += 1
                        if added > 0:
                            new_data_event.set()
                except Exception:
                    pass

        page.on("response", on_response)

        # 1. Buka Home untuk verifikasi login dan deteksi handle asli
        print(f"  {CYAN}🌐 Memverifikasi sesi & mendeteksi handle asli...{RESET}", flush=True)
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  {YELLOW}Warning navigasi home: {e}{RESET}", flush=True)

        if "login" in page.url or "i/flow/login" in page.url:
            print(f"  {RED}❌ Sesi kedaluwarsa atau token tidak valid!{RESET}", flush=True)
            stats["status"] = "EXPIRED"
            await browser.close()
            return stats

        # Ambil handle asli dari menu profile
        detected_uname = stored_name
        profile_link = await page.query_selector('a[data-testid="AppTabBar_Profile_Link"]')
        if profile_link:
            href = await profile_link.get_attribute("href")
            if href and "/" in href:
                clean_handle = href.strip("/").split("/")[-1]
                if clean_handle and not clean_handle.startswith("i/"):
                    detected_uname = clean_handle
                    if detected_uname.lower() != stored_name.lower():
                        print(f"  {GREEN}💡 Terdeteksi username Twitter resmi: @{detected_uname}{RESET}", flush=True)
                        stats["account"] = detected_uname
                        # Update ke accounts.json jika sebelumnya default/generic
                        acc_data = load_accounts()
                        if account_key in acc_data.get("accounts", {}):
                            acc_data["accounts"][account_key]["screen_name"] = detected_uname
                            save_accounts(acc_data)

        # 2. Buka Halaman Following
        following_url = f"https://x.com/{detected_uname}/following"
        print(f"  {CYAN}📂 Membuka tab Following: {following_url}{RESET}", flush=True)
        try:
            await page.goto(following_url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"  {YELLOW}Warning buka following: {e}{RESET}", flush=True)

        # Cek apakah Following memang sudah 0
        is_zero_following = await page.evaluate('''() => {
            const bodyText = document.body.innerText || "";
            if (bodyText.includes("aren't following anyone yet") || 
                bodyText.includes("Belum mengikuti siapapun") ||
                bodyText.includes("Looking for followers?")) {
                return true;
            }
            // Cek text tabs
            const links = Array.from(document.querySelectorAll('a[href$="/following"]'));
            for (const a of links) {
                const txt = a.innerText.trim();
                if (txt.startsWith("0 ") || txt === "0") return true;
            }
            return false;
        }''')

        if is_zero_following:
            print(f"  {GREEN}✨ Akun @{detected_uname} sudah memiliki 0 Following (Bersih!){RESET}", flush=True)
            stats["status"] = "ALREADY_ZERO"
            await browser.close()
            return stats

        # Loop unfollow berkelanjutan dengan auto-scroll
        round_loop = 1
        no_new_data_count = 0
        max_no_data = 4

        while True:
            # Tunggu data GraphQL masuk jika buffer kosong
            if not captured_accounts:
                try:
                    await asyncio.wait_for(new_data_event.wait(), timeout=8)
                except asyncio.TimeoutError:
                    pass

            if captured_accounts:
                no_new_data_count = 0
                to_process = list(captured_accounts)
                captured_accounts.clear()
                new_data_event.clear()

                for acc in to_process:
                    u_id = acc["id"]
                    s_name = acc["screen_name"]
                    u_name = acc["name"]
                    is_follower = acc["followed_by"]

                    # Cek Whitelist
                    if s_name.lower() in whitelist:
                        print(f"    🛡️  [SKIP] @{s_name} ({u_name}) - Terdaftar di Whitelist", flush=True)
                        stats["skipped_whitelist"] += 1
                        continue

                    # Cek Followback
                    if keep_followers and is_follower:
                        print(f"    👥 [SKIP] @{s_name} ({u_name}) - Akun Follows-Back", flush=True)
                        stats["skipped_followers"] += 1
                        continue

                    # Unfollow execution
                    print(f"    🔄 Unfollowing @{s_name} ({u_name})... ", end="", flush=True)
                    if dry_run:
                        print(f"{YELLOW}[DRY-RUN]{RESET}", flush=True)
                        stats["unfollowed"] += 1
                        continue

                    ok, msg = await unfollow_user_api(page, u_id, s_name, ct0)
                    if ok:
                        stats["unfollowed"] += 1
                        save_unfollowed_entry(detected_uname, u_id, s_name, u_name)
                        print(f"{GREEN}{BOLD}✓ [UNFOLLOWED]{RESET} (Total: {stats['unfollowed']})", flush=True)
                    else:
                        if msg == "RATE_LIMIT_429":
                            print(f"{YELLOW}[RATE LIMIT 429 - Tunggu 10s...]{RESET}", flush=True)
                            await asyncio.sleep(10)
                            # Retry 1x
                            retry_ok, retry_msg = await unfollow_user_api(page, u_id, s_name, ct0)
                            if retry_ok:
                                stats["unfollowed"] += 1
                                save_unfollowed_entry(detected_uname, u_id, s_name, u_name)
                                print(f"    🔄 Retry @{s_name}... {GREEN}✓ [UNFOLLOWED]{RESET}", flush=True)
                            else:
                                print(f"    ❌ Gagal: {retry_msg}", flush=True)
                        else:
                            print(f"{RED}[GAGAL: {msg}]{RESET}", flush=True)

                    # Micro delay
                    sl = random.uniform(delay_min, delay_max)
                    if sl > 0:
                        await asyncio.sleep(sl)

            # Scroll ke bawah untuk memuat batch following berikutnya
            await page.evaluate("window.scrollBy(0, window.innerHeight * 2);")
            await asyncio.sleep(2)

            # Cek jika tidak ada data baru yang masuk
            if not captured_accounts and not new_data_event.is_set():
                no_new_data_count += 1
                if no_new_data_count >= max_no_data:
                    # Cek sekali lagi apakah sudah tuntas 0 following
                    is_done = await page.evaluate('''() => {
                        const body = document.body.innerText || "";
                        return body.includes("aren't following anyone yet") ||
                               body.includes("Belum mengikuti siapapun") ||
                               body.includes("Looking for followers?");
                    }''')
                    if is_done or stats["unfollowed"] > 0:
                        print(f"  {GREEN}✓ Tidak ada lagi akun following tersisa pada @{detected_uname}. Selesai!{RESET}", flush=True)
                    else:
                        print(f"  {YELLOW}ℹ️ Tidak ada data following tambahan yang dimuat.{RESET}", flush=True)
                    break

            round_loop += 1

        print(f"  {GREEN}🏁 Akun @{detected_uname} selesai: {BOLD}{stats['unfollowed']} akun berhasil di-unfollow{RESET}.\n", flush=True)
        await browser.close()
        return stats


async def main_loop(
    target_account: str = "",
    keep_followers: bool = False,
    delay_min: float = 0.3,
    delay_max: float = 0.8,
    whitelist_file: Path = DEFAULT_WHITELIST_FILE,
    dry_run: bool = False,
    headless: bool = True
):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║       ⚡ MASS AUTO UNFOLLOW BOT (SEMUA AKUN / ALL-IN)         ║
║   Unfollow Total Daftar Following untuk 10 Akun Sekaligus     ║
║   Mode: Sequential 1 per 1 (RAM Ringan & Bebas Bug DOM)      ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    acc_data = load_accounts()
    accounts_dict = acc_data.get("accounts", {})
    if not accounts_dict:
        print(f"{RED}❌ File accounts.json kosong atau tidak ditemukan!{RESET}")
        return

    whitelist = load_whitelist(whitelist_file)
    print(f"Konfigurasi:")
    print(f"  • Mode Akun           : {'Semua 10 Akun' if not target_account else f'Hanya @{target_account}'}")
    print(f"  • Simpan Follow-back  : {'Ya' if keep_followers else 'Tidak (Unfollow Semua)'}")
    print(f"  • Whitelist Terpasang : {len(whitelist)} akun")
    print(f"  • Jeda per Unfollow   : {delay_min}s - {delay_max}s (Cepat & Aman)")
    print(f"  • Mode Dry Run        : {'Aktif (Simulasi)' if dry_run else 'Nonaktif (Eksekusi Nyata)'}")
    print(f"  • Mode Browser        : {'Headless' if headless else 'Visible'}\n")

    # Filter target jika dispesifikasikan
    if target_account:
        clean_target = target_account.lstrip("@").lower()
        keys_to_process = [k for k, v in accounts_dict.items() if k.lower() == clean_target or v.get("screen_name", "").lower() == clean_target]
        if not keys_to_process:
            print(f"{RED}❌ Akun @{target_account} tidak ditemukan di accounts.json!{RESET}")
            return
    else:
        keys_to_process = list(accounts_dict.keys())

    total = len(keys_to_process)
    summary_report = []

    start_time = datetime.now()
    for idx, key in enumerate(keys_to_process, 1):
        acc = accounts_dict[key]
        uname = acc.get("screen_name", key)
        dname = acc.get("name", uname)

        print(f"{MAGENTA}{BOLD}================================================================{RESET}")
        print(f"{MAGENTA}{BOLD}▶ [{idx}/{total}] MEMPROSES AKUN: @{uname} ({dname}){RESET}")
        print(f"{MAGENTA}{BOLD}================================================================{RESET}")

        res = await unfollow_account_session(
            account_key=key,
            account_info=acc,
            whitelist=whitelist,
            keep_followers=keep_followers,
            delay_min=delay_min,
            delay_max=delay_max,
            dry_run=dry_run,
            headless=headless
        )
        summary_report.append(res)

    duration = (datetime.now() - start_time).total_seconds()

    # Cetak Rekapitulasi Akhir
    print(f"\n{CYAN}{BOLD}╔═══════════════════════════════════════════════════════════════╗")
    print(f"║                   📊 REKAPITULASI UNFOLLOW                    ║")
    print(f"╚═══════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{BOLD}{'No':<4} {'Username':<18} {'Unfollowed':<12} {'Whitelist':<11} {'Status'}{RESET}")
    print("-" * 63)
    total_unfollowed = 0
    for i, rep in enumerate(summary_report, 1):
        total_unfollowed += rep["unfollowed"]
        print(f"{i:<4} @{rep['account']:<17} {rep['unfollowed']:<12} {rep['skipped_whitelist']:<11} {rep['status']}")
    print("-" * 63)
    print(f"{GREEN}{BOLD}Total Keseluruhan Di-unfollow : {total_unfollowed} Akun{RESET}")
    print(f"Waktu Total Pengerjaan        : {duration:.1f} detik\n")


def main():
    parser = argparse.ArgumentParser(description="Multi-Account Twitter / X Auto Unfollow Bot")
    parser.add_argument("-a", "--account", type=str, default="", help="Jalankan hanya untuk 1 akun tertentu (kosong = semua akun)")
    parser.add_argument("--keep-followers", action="store_true", help="Jangan unfollow akun yang mem-follow kembali")
    parser.add_argument("--delay-min", type=float, default=0.3, help="Delay minimal antar unfollow (default: 0.3s)")
    parser.add_argument("--delay-max", type=float, default=0.8, help="Delay maksimal antar unfollow (default: 0.8s)")
    parser.add_argument("--whitelist", type=str, default="whitelist.txt", help="Path file whitelist")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi saja")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser Chrome")

    args = parser.parse_args()

    try:
        asyncio.run(main_loop(
            target_account=args.account,
            keep_followers=args.keep_followers,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            whitelist_file=Path(args.whitelist),
            dry_run=args.dry_run,
            headless=not args.visible
        ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Bot unfollow dihentikan oleh pengguna.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
