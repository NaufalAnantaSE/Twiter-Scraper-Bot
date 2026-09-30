import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import COOKIES_FILE, RESULTS_DIR

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

GIVEAWAY_LOG_FILE = RESULTS_DIR / "giveaway_history.json"

def record_posted_giveaway(tweet_id: str, url: str, text: str, network: str = "SOLANA"):
    """Mencatat postingan giveaway ke file riwayat results/giveaway_history.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = {}
    if GIVEAWAY_LOG_FILE.exists():
        try:
            with open(GIVEAWAY_LOG_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    entry_key = tweet_id if tweet_id else f"post_{int(datetime.now().timestamp())}"
    history[entry_key] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "network": network,
        "url": url,
        "text": text
    }

    with open(GIVEAWAY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

async def load_playwright_cookies(context: BrowserContext) -> bool:
    """Memuat cookie sesi Twitter ke context browser Playwright."""
    if not COOKIES_FILE.exists():
        return False
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cdata = json.load(f)

        cookies = []
        for name, val in cdata.items():
            cookies.append({
                "name": name,
                "value": str(val).strip(),
                "domain": ".x.com",
                "path": "/"
            })
        await context.add_cookies(cookies)
        return True
    except Exception as e:
        print(f"{RED}Gagal memuat cookies.json: {e}{RESET}")
        return False

async def post_tweet(tweet_text: str, network: str = "SOLANA", headless: bool = True) -> tuple[bool, str, str]:
    """
    Membuat dan memposting tweet baru ke akun Twitter secara otomatis.
    Return: (success: bool, tweet_url: str, error_msg: str)
    """
    print(f"\n{CYAN}--- Mempersiapkan Postingan Tweet Giveaway ---{RESET}")
    print(f"Preview Teks Tweet:\n{YELLOW}{tweet_text}{RESET}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=headless)
        context = await browser.new_context()

        has_cookies = await load_playwright_cookies(context)
        if not has_cookies:
            await browser.close()
            return False, "", "File cookies.json tidak ditemukan atau tidak valid!"

        page = await context.new_page()

        created_tweet_id = None
        async def on_response(response):
            nonlocal created_tweet_id
            if "CreateTweet" in response.url:
                try:
                    res_json = await response.json()
                    result = res_json.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
                    created_tweet_id = result.get("rest_id")
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            print(f"{YELLOW}Membuka komposer tweet (https://x.com/compose/post)...{RESET}", flush=True)
            await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(4)

            if "login" in page.url:
                await browser.close()
                return False, "", "Sesi cookie kadaluarsa. Twitter mengarahkan ke halaman login."

            # Cari textarea composer
            textarea = page.locator('[data-testid="tweetTextarea_0"]').first
            try:
                await textarea.wait_for(state="visible", timeout=12000)
            except Exception:
                print(f"{YELLOW}Mencoba navigasi via https://x.com/home...{RESET}", flush=True)
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                textarea = page.locator('[data-testid="tweetTextarea_0"]').first
                await textarea.wait_for(state="visible", timeout=10000)

            print(f"{YELLOW}Mengetik konten tweet giveaway...{RESET}", flush=True)
            await textarea.click()
            await asyncio.sleep(0.5)
            await textarea.fill(tweet_text)
            await asyncio.sleep(1.0)

            # Picu perubahan event di editor Twitter (DraftJS / Lexical)
            await textarea.press("End")
            await textarea.type(" ")
            await textarea.press("Backspace")
            await asyncio.sleep(0.5)

            # Tutup dropdown autocomplete hashtag/mention jika muncul agar tidak menghalangi klik
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.8)

            # Cari tombol Post / Kirim
            send_btn = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first
            await send_btn.wait_for(state="visible", timeout=5000)

            if not await send_btn.is_enabled():
                await asyncio.sleep(1.0)

            if not await send_btn.is_enabled():
                await browser.close()
                return False, "", "Tombol kirim (tweetButton) dalam kondisi disabled/non-aktif!"

            print(f"{YELLOW}Mengklik tombol Post/Kirim...{RESET}", flush=True)
            await send_btn.click(force=True)

            # Tunggu respon GraphQL CreateTweet (maksimal 8 detik)
            for _ in range(8):
                if created_tweet_id:
                    break
                await asyncio.sleep(1.0)

            if not created_tweet_id:
                # Fallback periksa toast
                try:
                    toast_link = page.locator('[data-testid="toast"] a[href*="/status/"]').first
                    if await toast_link.count() > 0:
                        href = await toast_link.get_attribute("href")
                        if href and "status" in href:
                            created_tweet_id = href.strip("/").split("/status/")[1].split("?")[0]
                except Exception:
                    pass

            if not created_tweet_id:
                await browser.close()
                return False, "", "Tidak berhasil menangkap konfirmasi pembuatan tweet dari server Twitter."

            tweet_url = f"https://x.com/fannettt/status/{created_tweet_id}"

            # Catat ke riwayat
            record_posted_giveaway(created_tweet_id, tweet_url, tweet_text, network)

            print(f"{GREEN}{BOLD}🎉 Tweet Giveaway Berhasil Diposting!{RESET}", flush=True)
            print(f"🔗 Link Tweet : {CYAN}{tweet_url}{RESET}", flush=True)

            await browser.close()
            return True, tweet_url, ""

        except Exception as e:
            await browser.close()
            return False, "", str(e)

if __name__ == "__main__":
    from giveaway_templates import generate_solana_giveaway
    sample_tweet = generate_solana_giveaway()
    print("Testing post_tweet...")
    # asyncio.run(post_tweet(sample_tweet))
