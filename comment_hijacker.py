"""
Twitter / X Comment Hijacking Bot (Growth & Followers Booster)
Mendeteksi tweet baru dari akun-akun crypto / web3 raksasa dan langsung
memberikan komentar cerdas di menit-menit awal untuk mendatangkan impresi dan followers.
"""

import argparse
import asyncio
import json
import logging
import random
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

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

HIJACK_HISTORY_FILE = RESULTS_DIR / "hijack_history.json"
DEFAULT_TARGETS_FILE = Path(__file__).parent / "viral_targets.txt"
TEMPLATES_FILE = Path(__file__).parent / "comments_templates.json"


def load_comment_templates() -> dict:
    """Memuat template komentar multibahasa dari file comments_templates.json."""
    if TEMPLATES_FILE.exists():
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback default jika file tidak ditemukan
    return {
        "indonesian": {
            "general": ["Gokil update-nya! Selalu dukung perkembangannya 🔥🚀", "Makin solid ekosistemnya! LFG 💎🙌"],
            "market": ["Fundamental emang nggak pernah bohong. Tetap bullish! 📈🔥"],
            "announcement": ["Milestone mantap nih. Ekosistemnya makin hari makin solid! 💎"]
        },
        "english": {
            "general": ["Always bullish on this ecosystem! The momentum is undeniable 🚀🔥", "Super clean execution. Exciting times ahead! 🌟🙌"],
            "market": ["Fundamentals always win in the long run. Bullish as always! 📊📈"],
            "announcement": ["Huge milestone! The consistency in building and shipping is what sets this apart 🚀🔥"]
        }
    }


def detect_tweet_language(tweet_text: str) -> str:
    """Mendeteksi apakah tweet dalam bahasa Indonesia atau Inggris."""
    text_lower = tweet_text.lower()
    indonesian_words = {
        "yang", "ini", "dan", "di", "ke", "dari", "bisa", "untuk", "airdrop",
        "garap", "serok", "cuan", "mantap", "gokil", "bang", "nih", "udah",
        "lagi", "sama", "kita", "juga", "ada", "kalian", "mau", "sudah",
        "bocoran", "tutor", "info", "selamat", "hari", "besok", "kapan"
    }
    words = set(re.findall(r"\b[a-zA-Z]{2,}\b", text_lower))
    overlap = words.intersection(indonesian_words)
    return "indonesian" if len(overlap) >= 2 else "english"


def detect_context_category(tweet_text: str) -> str:
    """Mendeteksi topik tweet: announcement, market, atau general."""
    text_lower = tweet_text.lower()

    announcement_keywords = [
        "launch", "announc", "live", "mainnet", "partnership", "collab",
        "update", "release", "shipped", "milestone", "introducing", "feature",
        "rilis", "fitur", "kerjasama", "resmi", "upgrade"
    ]
    market_keywords = [
        "bull", "market", "price", "ath", "volume", "pumping", "pump", "sol",
        "btc", "eth", "rally", "cuan", "serok", "harga", "naik", "high",
        "bear", "dip", "trading"
    ]

    for kw in announcement_keywords:
        if kw in text_lower:
            return "announcement"

    for kw in market_keywords:
        if kw in text_lower:
            return "market"

    return "general"


def generate_hijack_comment(tweet_text: str = "", lang_preference: str = "auto") -> tuple[str, str, str]:
    """
    Menghasilkan komentar yang sesuai konteks dan bahasa tweet.
    Return: (comment_text, language_used, category_used)
    """
    templates = load_comment_templates()

    # Tentukan bahasa
    if lang_preference == "id":
        target_lang = "indonesian"
    elif lang_preference == "en":
        target_lang = "english"
    else:
        target_lang = detect_tweet_language(tweet_text)

    # Tentukan kategori konteks
    category = detect_context_category(tweet_text)

    lang_pool = templates.get(target_lang, templates.get("english", {}))
    comment_list = lang_pool.get(category) or lang_pool.get("general") or []

    if not comment_list:
        comment_list = ["Always bullish on this ecosystem! LFG 🚀🔥"]

    chosen_comment = random.choice(comment_list)
    return chosen_comment, target_lang, category


async def reply_to_tweet(page: Page, tweet_el, author: str, reply_text: str) -> bool:
    """Mengirim komentar balasan ke tweet yang dipilih."""
    try:
        # 1. Like tweet terlebih dahulu untuk impresi positif
        like_btn = tweet_el.locator('[data-testid="like"]').first
        if await like_btn.count() > 0 and await like_btn.is_visible():
            await like_btn.click(force=True)
            print(f"   ❤️  Auto-Like tweet @{author}")
            await asyncio.sleep(1.0)

        # 2. Klik tombol reply
        reply_btn = tweet_el.locator('[data-testid="reply"]').first
        if await reply_btn.count() == 0:
            print(f"   {RED}✗ Tombol reply tidak ditemukan di tweet{RESET}")
            return False

        await reply_btn.scroll_into_view_if_needed()
        await reply_btn.click(force=True)
        await asyncio.sleep(1.5)

        # 3. Temukan kotak teks komentar
        textarea = page.locator('[data-testid="tweetTextarea_0"]').first
        await textarea.wait_for(state="visible", timeout=8000)
        await textarea.fill(reply_text)
        await asyncio.sleep(1.0)

        # Picu perubahan teks di editor
        await textarea.press("End")
        await textarea.type(" ")
        await textarea.press("Backspace")
        await asyncio.sleep(0.8)

        # 4. Klik tombol kirim (tweetButton)
        send_btn = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first
        if not await send_btn.is_enabled():
            await asyncio.sleep(1.0)

        if await send_btn.is_enabled():
            await send_btn.click(force=True)
            print(f"   {GREEN}✓ Komentar berhasil dikirim!{RESET}")
            await asyncio.sleep(random.uniform(2.5, 4.0))
            return True
        else:
            print(f"   {RED}✗ Tombol kirim balasan non-aktif{RESET}")
            return False
    except Exception as e:
        print(f"   {RED}✗ Error saat membalas tweet: {e}{RESET}")
        return False
    finally:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass


async def run_comment_hijacker(
    max_replies: int = 5,
    max_age_minutes: float = 120.0,
    targets_file: Path = DEFAULT_TARGETS_FILE,
    lang_preference: str = "auto",
    headless: bool = True
):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║          COMMENT HIJACKING BOT (FOLLOWER & ENGAGEMENT)        ║
║     Nimbrung Cepat di Tweet Akun Crypto / Web3 Raksasa        ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    if not COOKIES_FILE.exists():
        print(f"{RED}File cookies.json tidak ditemukan!{RESET}")
        return

    targets = load_targets(targets_file)
    history = load_hijack_history()

    lang_label = "Otomatis (Sesuai Tweet)" if lang_preference == "auto" else ("Bahasa Indonesia" if lang_preference == "id" else "Bahasa Inggris")

    print(f"Pengaturan Bot:")
    print(f"  • Akun Target        : {GREEN}{len(targets)} akun crypto tier-1{RESET} ({', '.join(targets[:5])}...)")
    print(f"  • Target Komentar    : {BOLD}{max_replies} tweet per sesi{RESET}")
    print(f"  • Maksimal Usia Tweet: {YELLOW}Hingga {max_age_minutes} menit yang lalu{RESET}")
    print(f"  • Preferensi Bahasa  : {MAGENTA}{BOLD}{lang_label}{RESET}")
    print(f"  • Riwayat Selesai    : {len(history)} tweet sebelumnya")
    print(f"  • Mode Browser       : {'Headless (Senyap)' if headless else 'Visible'}\n")

    # Pecah akun target menjadi kelompok query pencarian (max 6 per query agar URL ringkas)
    chunk_size = 6
    target_chunks = [targets[i:i + chunk_size] for i in range(0, len(targets), chunk_size)]

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

        replied_count = 0

        for chunk_idx, chunk in enumerate(target_chunks, 1):
            if replied_count >= max_replies:
                break

            query_parts = [f"from:{t}" for t in chunk]
            raw_query = f"({' OR '.join(query_parts)}) -filter:replies"
            encoded_query = urllib.parse.quote(raw_query)
            search_url = f"https://x.com/search?q={encoded_query}&f=live"

            print(f"\n{CYAN}--- [KELOMPOK {chunk_idx}/{len(target_chunks)}] Memantau Akun: {', '.join(['@' + u for u in chunk])} ---{RESET}")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"{YELLOW}Gagal memuat feed pencarian: {e}{RESET}")
                continue

            # Cari elemen tweet
            articles = page.locator('article[data-testid="tweet"]')
            total_found = await articles.count()
            print(f"Ditemukan {total_found} postingan di feed.")

            for i in range(total_found):
                if replied_count >= max_replies:
                    break

                tweet_el = articles.nth(i)

                # Ambil URL & ID Tweet
                status_link = tweet_el.locator('a[href*="/status/"]').first
                if await status_link.count() == 0:
                    continue

                href = await status_link.get_attribute("href")
                if not href or "/status/" not in href:
                    continue

                parts = href.strip("/").split("/")
                if len(parts) < 3 or parts[1] != "status":
                    continue

                author = parts[0]
                tweet_id = parts[2].split("?")[0]

                # Cek riwayat
                if tweet_id in history:
                    continue

                # Cek usia tweet
                is_fresh = True
                age_str = ""
                time_el = tweet_el.locator("time").first
                if await time_el.count() > 0:
                    dt_str = await time_el.get_attribute("datetime")
                    if dt_str:
                        try:
                            created_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            now_dt = datetime.now(timezone.utc)
                            age_mins = (now_dt - created_dt).total_seconds() / 60.0
                            age_str = f"{age_mins:.0f} menit yang lalu"
                            if age_mins > max_age_minutes:
                                is_fresh = False
                        except Exception:
                            pass

                if not is_fresh:
                    continue

                # Ambil teks tweet
                text_el = tweet_el.locator('[data-testid="tweetText"]').first
                tweet_text = await text_el.inner_text() if await text_el.count() > 0 else ""
                clean_preview = tweet_text.replace("\n", " ")[:90]

                # Buat komentar hijack cerdas sesuai konteks & bahasa
                comment, lang_used, cat_used = generate_hijack_comment(tweet_text, lang_preference=lang_preference)

                print(f"\n{YELLOW}🎯 Menemukan Tweet Segar dari @{author} ({age_str or 'Baru saja'}):{RESET}")
                print(f"   Teks: \"{clean_preview}...\"")
                print(f"   Topik: {MAGENTA}[{cat_used.upper()}]{RESET} | Bahasa: {GREEN}[{lang_used.upper()}]{RESET}")
                print(f"   Drop Komentar: {CYAN}\"{comment}\"{RESET}")

                await tweet_el.scroll_into_view_if_needed()
                await asyncio.sleep(1.0)

                ok = await reply_to_tweet(page, tweet_el, author, comment)
                if ok:
                    replied_count += 1
                    history[str(tweet_id)] = True
                    record_hijack(tweet_id, author, tweet_text, comment)
                    print(f"{GREEN}✓ Berhasil nimbrung ({replied_count}/{max_replies}){RESET}")

                    # Jeda alami antar komentar
                    if replied_count < max_replies:
                        sleep_sec = random.uniform(15.0, 30.0)
                        print(f"   ⏱️  Jeda istirahat {sleep_sec:.0f} detik...")
                        await asyncio.sleep(sleep_sec)

        print(f"\n{CYAN}============================================================{RESET}")
        print(f"{GREEN}{BOLD}🎉 SESI COMMENT HIJACKING SELESAI!{RESET}")
        print(f"  • Komentar Terkirim : {BOLD}{replied_count}{RESET} tweet")
        print(f"  • Riwayat Tersimpan : {HIJACK_HISTORY_FILE}\n")

        await browser.close()


async def hijack_continuous_loop(
    interval_minutes: int = 15,
    max_per_cycle: int = 3,
    max_age_minutes: float = 60.0,
    lang_preference: str = "auto",
    headless: bool = True
):
    """Loop otomatis memantau tweet baru setiap interval_minutes."""
    print(f"{CYAN}{BOLD}Memulai Mode Loop Pemantauan Tweet Viral 24/7 (Interval {interval_minutes} Menit)...{RESET}")
    cycle = 1
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}============================================================{RESET}")
        print(f"🔄 [SIKLUS HIJACK #{cycle}] Memantau Tweet Baru ({timestamp})")
        print(f"{CYAN}============================================================{RESET}")

        try:
            await run_comment_hijacker(
                max_replies=max_per_cycle,
                max_age_minutes=max_age_minutes,
                lang_preference=lang_preference,
                headless=headless
            )
        except Exception as e:
            print(f"{RED}Error pada siklus: {e}{RESET}")

        cycle += 1
        print(f"\n{YELLOW}💤 Istirahat {interval_minutes} menit menunggu tweet baru dari akun target...{RESET}")
        await asyncio.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description="Twitter / X Comment Hijacking Bot")
    parser.add_argument("-m", "--max", type=int, default=5, help="Jumlah tweet yang ingin dikomentari per sesi (default: 5)")
    parser.add_argument("--age", type=float, default=120.0, help="Maksimal usia tweet dalam menit (default: 120)")
    parser.add_argument("--targets", type=str, default="viral_targets.txt", help="Path ke file daftar target akun")
    parser.add_argument("--lang", type=str, choices=["auto", "id", "en"], default="auto", help="Preferensi bahasa komentar: auto (default), id (Indonesia), en (Inggris)")
    parser.add_argument("--loop", action="store_true", help="Jalankan otomatis berulang terus-menerus (24/7 loop)")
    parser.add_argument("--interval", type=int, default=15, help="Jeda antar pemantauan dalam menit untuk mode loop (default: 15)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    try:
        if args.loop:
            asyncio.run(hijack_continuous_loop(
                interval_minutes=args.interval,
                max_per_cycle=args.max,
                max_age_minutes=args.age,
                lang_preference=args.lang,
                headless=not args.visible
            ))
        else:
            asyncio.run(run_comment_hijacker(
                max_replies=args.max,
                max_age_minutes=args.age,
                targets_file=Path(args.targets),
                lang_preference=args.lang,
                headless=not args.visible
            ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Bot dihentikan oleh pengguna.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
