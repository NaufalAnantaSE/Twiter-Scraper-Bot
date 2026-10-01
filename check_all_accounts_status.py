"""
Twitter / X Account Health & Suspension Checker
Memeriksa status riil seluruh akun di accounts.json:
- ACTIVE (Sehat & Aktif)
- SUSPENDED (Ditangguhkan)
- LOCKED / ACCESS_RESTRICTED (Perlu verifikasi captcha / nomor hp)
- EXPIRED_COOKIES (Cookie/Token kedaluwarsa)
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, RESULTS_DIR
from accounts_manager import load_accounts, save_accounts

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


async def check_single_account(p, key: str, acc: dict) -> dict:
    uname = acc.get("screen_name", key)
    dname = acc.get("name", uname)
    auth = acc.get("auth_token", "").strip()
    ct0 = acc.get("ct0", "").strip()

    result = {
        "key": key,
        "screen_name": uname,
        "name": dname,
        "status": "UNKNOWN",
        "detail": "",
        "following_count": "-",
        "followers_count": "-",
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if not auth or not ct0:
        result["status"] = "NO_COOKIES"
        result["detail"] = "auth_token atau ct0 kosong"
        return result

    browser = await p.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    await context.add_cookies([
        {"name": "auth_token", "value": auth, "domain": ".x.com", "path": "/"},
        {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
        {"name": "auth_token", "value": auth, "domain": ".twitter.com", "path": "/"},
        {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
    ])

    page = await context.new_page()

    try:
        # Buka Home
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        curr_url = page.url.lower()

        # 1. Cek Redirect ke Login
        if "login" in curr_url or "i/flow/login" in curr_url:
            result["status"] = "EXPIRED"
            result["detail"] = "Sesi login kedaluwarsa atau token salah"
            await browser.close()
            return result

        # 2. Cek Redirect ke Suspended
        if "account/suspended" in curr_url or "suspended" in curr_url:
            result["status"] = "SUSPENDED"
            result["detail"] = "URL dialihkan ke account/suspended"
            await browser.close()
            return result

        # 3. Cek Redirect ke Access / Locked
        if "account/access" in curr_url:
            result["status"] = "LOCKED"
            result["detail"] = "Akun terkunci / butuh verifikasi (Arkose / Phone)"
            await browser.close()
            return result

        # 4. Cek teks di dalam DOM (Modal / Alert suspend / lock)
        body_text = await page.evaluate("() => document.body.innerText || ''")
        body_lower = body_text.lower()

        if "account suspended" in body_lower or "akun ditangguhkan" in body_lower or "your account has been suspended" in body_lower:
            result["status"] = "SUSPENDED"
            result["detail"] = "Terdeteksi teks 'Account Suspended' pada halaman"
            await browser.close()
            return result

        if "unusual activity" in body_lower or "temporarily locked" in body_lower or "terkunci sementara" in body_lower:
            result["status"] = "LOCKED"
            result["detail"] = "Terdeteksi teks 'Temporarily Locked'"
            await browser.close()
            return result

        # 5. Cari Handle asli
        detected_uname = uname
        profile_link = await page.query_selector('a[data-testid="AppTabBar_Profile_Link"]')
        if profile_link:
            href = await profile_link.get_attribute("href")
            if href and "/" in href:
                clean_handle = href.strip("/").split("/")[-1]
                if clean_handle and not clean_handle.startswith("i/"):
                    detected_uname = clean_handle
                    result["screen_name"] = detected_uname

        # 6. Buka Profil untuk cek Following / Followers
        try:
            await page.goto(f"https://x.com/{detected_uname}", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2)

            prof_body = await page.evaluate("() => document.body.innerText || ''")
            prof_lower = prof_body.lower()
            if "account suspended" in prof_lower or "akun ditangguhkan" in prof_lower:
                result["status"] = "SUSPENDED"
                result["detail"] = f"Halaman profil @{detected_uname} berstatus Ditangguhkan (Suspended)"
                await browser.close()
                return result

            # Ambil following & followers count
            counts = await page.evaluate('''() => {
                let following = "-";
                let followers = "-";
                const links = Array.from(document.querySelectorAll('a[href*="/following"], a[href*="/verified_followers"], a[href*="/followers"]'));
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const text = a.innerText.trim();
                    if (href.endsWith('/following')) {
                        const m = text.match(/([\\d.,KMkm]+)/);
                        if (m) following = m[1];
                    } else if (href.endsWith('/followers') || href.endsWith('/verified_followers')) {
                        const m = text.match(/([\\d.,KMkm]+)/);
                        if (m) followers = m[1];
                    }
                }
                return { following, followers };
            }''')

            result["following_count"] = counts.get("following", "-")
            result["followers_count"] = counts.get("followers", "-")

        except Exception as pe:
            result["detail"] = f"Profil check notice: {pe}"

        result["status"] = "ACTIVE"
        if not result["detail"]:
            result["detail"] = "Akun aktif, normal, dan sesi valid"

    except Exception as e:
        result["status"] = "ERROR"
        result["detail"] = str(e)
    finally:
        await browser.close()

    return result


async def main():
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         🔍 TWITTER / X ACCOUNT HEALTH & STATUS CHECKER        ║
║   Pengecekan Komprehensif Status Suspend, Lock, & Sesi Token  ║
╚═══════════════════════════════════════════════════════════════╝{RESET}\n""")

    data = load_accounts()
    accounts = data.get("accounts", {})
    if not accounts:
        print(f"{RED}Tidak ada akun di accounts.json!{RESET}")
        return

    print(f"Ditemukan {len(accounts)} akun. Memulai pemeriksaan satu per satu...\n")

    results = []
    async with async_playwright() as p:
        for idx, (key, acc) in enumerate(accounts.items(), 1):
            uname = acc.get("screen_name", key)
            print(f"[{idx}/{len(accounts)}] Memeriksa @{uname} ... ", end="", flush=True)
            res = await check_single_account(p, key, acc)
            st = res["status"]
            if st == "ACTIVE":
                print(f"{GREEN}{BOLD}AKTIF / SEHAT ✓{RESET} (Following: {res['following_count']} | Followers: {res['followers_count']})")
            elif st == "SUSPENDED":
                print(f"{RED}{BOLD}🚨 SUSPENDED (DITANGGUHKAN){RESET} ({res['detail']})")
            elif st == "LOCKED":
                print(f"{YELLOW}{BOLD}⚠️ LOCKED / VERIFIKASI{RESET} ({res['detail']})")
            elif st == "EXPIRED":
                print(f"{MAGENTA}{BOLD}❌ TOKEN KEDALUWARSA{RESET} ({res['detail']})")
            else:
                print(f"{YELLOW}{st}{RESET} ({res['detail']})")
            results.append(res)

    # Simpan hasil ke JSON
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = RESULTS_DIR / "accounts_status_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Tabel Ringkasan
    print(f"\n{CYAN}{BOLD}╔═════════════════════════════════════════════════════════════════════════════════════╗")
    print(f"║                             📊 REKAPITULASI STATUS AKUN                             ║")
    print(f"╚═════════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{BOLD}{'No':<4} {'Username':<18} {'Status':<16} {'Following':<11} {'Followers':<11} {'Keterangan'}{RESET}")
    print("-" * 85)
    for i, r in enumerate(results, 1):
        color = GREEN if r["status"] == "ACTIVE" else (RED if r["status"] == "SUSPENDED" else YELLOW)
        print(f"{i:<4} @{r['screen_name']:<17} {color}{r['status']:<16}{RESET} {r['following_count']:<11} {r['followers_count']:<11} {r['detail'][:30]}")
    print("-" * 85)
    print(f"Laporan lengkap tersimpan di: {report_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
