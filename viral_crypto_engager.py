"""
Viral Crypto & Airdrop Engagement Bot - Multi-Account
Mencari postingan viral/ramai seputar airdrop dan crypto:
1. Menyaring ketat tweet (BUKAN giveaway, BUKAN drop address, BUKAN spam bot).
2. Mengeksekusi interaksi sesuai konteks postingan:
   - ❤️ Auto-Like
   - 🔁 Auto-Retweet (Repost)
   - 💬 Auto-Comment Cerdas & Kontekstual (Airdrop guide, market alpha, tech milestone)
   - 👤 FOLLOW DILEWATI (Following akun tetap bersih 0)
   - 👛 Drop Address DILEWATI (100% interaksi organik natural)
3. Berputar sekuensial pada seluruh akun aktif (otomatis melewati akun suspended).
4. Mode Single Run atau Loop Otomatis Terjadwal.
"""

import argparse
import asyncio
import json
import logging
import random
import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, COOKIES_FILE, RESULTS_DIR
from accounts_manager import load_accounts, sync_active_cookies

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

ENGAGEMENT_LOG_FILE = RESULTS_DIR / "viral_crypto_engagement_history.json"

# ==============================================================================
# 🔍 SEARCH QUERIES UNTUK TWEET VIRAL CRYPTO & AIRDROP
# ==============================================================================
VIRAL_SEARCH_QUERIES = [
    '(airdrop OR "testnet" OR "mainnet" OR "crypto alpha") min_faves:60 -giveaway -"drop address" -"drop sol" -"drop your" -"send your" -filter:replies',
    '("solana" OR "ethereum" OR "bitcoin" OR "layer 2") min_faves:80 -giveaway -"drop address" -"drop sol" -"drop your" -filter:replies',
    '("airdrop guide" OR "potential airdrop" OR "tutor airdrop") min_faves:40 -giveaway -"drop address" -"drop sol" -filter:replies',
    '("onchain" OR "defi" OR "crypto market" OR "altseason") min_faves:60 -giveaway -"drop address" -"drop your" -filter:replies'
]

# Kata kunci terlarang (harus dilewati agar tidak salah nimbrung di giveaway drop wallet)
FORBIDDEN_KEYWORDS = [
    "drop your", "drop address", "drop sol", "drop eth", "drop wallet",
    "send your sol", "send address", "airdrop giveaway", "winner in",
    "dropping $", "giving away", "100$ to", "50$ to", "first 100", "retweet & drop"
]

# ==============================================================================
# 🧠 SMART CONTEXTUAL COMMENT GENERATOR (AIRDROP & CRYPTO)
# ==============================================================================
SMART_COMMENTS = {
    "airdrop": {
        "en": [
            "Solid alpha right here! Bookmarked this thread for the weekend grind. Consistency onchain always wins 🔥",
            "Great breakdown! Early active users and real community engagement always get rewarded. Appreciate the guide 👏",
            "Quality airdrop guide, super clear steps. The compounding effect of exploring early protocols is unmatched 💎🙌",
            "Thanks for sharing this alpha! Setting up daily interactions right now. Time to put in the work 🚀",
            "This is the type of actionable Web3 content timeline needs. Straight to the point, thank you! ✨"
        ],
        "id": [
            "Info airdrop berbobot nih! Bookmark dulu buat digarap malam ini. Yang konsisten onchain yang panen nanti 🔥",
            "Thanks tutorial lengkapnya bang! Step-by-step jelas banget, langsung eksekusi mumpung gas fee aman 🚀",
            "Garapan mantap! Selalu suka liat panduan yang to the point tanpa basa-basi gini. Gaspol terus 💎🙌",
            "Alpha berkualitas! Emang bener kunci cuan di Web3 itu rajin interaksi sama ekosistem baru sejak awal ✨",
            "Penjelasan yang rapi dan gampang dipahami. Izin share dan praktek ya bang, mantap! 👏🔥"
        ]
    },
    "market": {
        "en": [
            "Market structure looking very solid here. Macro trend is holding up nicely, patience is key 📈",
            "Spot on observation. The liquidity shift across ecosystems is becoming super obvious now 📊",
            "Clean chart analysis! Shakeouts are normal in crypto, high conviction bags always prevail in the end 🚀",
            "Couldn't agree more. Volume precedes price, and fundamentals will always win the long game 💎🙌",
            "Great market perspective. Keeping emotions out of trading is the ultimate edge in this space ✨"
        ],
        "id": [
            "Struktur chartnya masih rapi banget nahan support. Tinggal nunggu konfirmasi volume berikutnya, bullish! 📈",
            "Setuju banget sama analisa ini. Di tengah volatilitas market gini emang paling bener sabar dan hold conviction 📊",
            "Analisa yang jernih no fomo-fomo club. Selalu menarik dengerin sudut pandang objektif kayak gini 👍",
            "Momentumnya makin kerasa solid. Yang tenang dan disiplin money management yang bakal survive 💎🙌",
            "Insight mantap bang! Market sideways emang waktu terbaik buat riset dan akumulasi pelan-pelan 🚀"
        ]
    },
    "tech": {
        "en": [
            "Huge milestone! Shipping high-quality tech consistently regardless of market noise is what builds longevity 🚀🔥",
            "Super clean execution by the team. The throughput and UX improvement here is genuinely impressive 👏",
            "Incredible development speed. Real builders never stop innovating. Excited for what's coming next! 🌟",
            "Massive leap forward for onchain infrastructure. The ecosystem is maturing at a rapid pace ⚡💎",
            "This is what real Web3 adoption looks like. Huge respect to the entire engineering team 🫡✨"
        ],
        "id": [
            "Milestone yang luar biasa! Tim dev beneran konsisten build tanpa banyak drama. Ekosistem makin solid 🔥🚀",
            "Eksekusi yang sangat rapi. Peningkatan performa dan UX-nya kerasa banget bedanya buat pengguna 👏",
            "Keren banget progressnya, update yang beneran menjawab kebutuhan komunitas. Sukses terus buat timnya! 🌟",
            "Inovasi infrastruktur onchain yang makin matang. Nggak sabar liat adopsi skala besarnya ke depan ⚡💎",
            "Salut sama konsistensi timnya! Ekosistem yang kuat emang dibangun dari fondasi teknologi yang berbobot 🫡✨"
        ]
    },
    "general": {
        "en": [
            "100% agreed with this perspective. High quality insight that adds real clarity to the timeline 💡",
            "Really well-articulated thoughts. Appreciate you sharing this valuable perspective with the community ✨",
            "Spot on! In a space full of hype, grounded takes like this are always refreshing to read 💯",
            "Appreciate the continuous value you bring to CT. Always keeping notifications on for your posts! 🙌🔥",
            "Completely on point. Long-term mindset is the only sustainable strategy in Web3 💎"
        ],
        "id": [
            "Setuju banget sama poin ini! Insight yang berbobot dan ngebuka wawasan baru tentang dinamika Web3 💡",
            "Penyampaiannya jernih dan berbobot. Senang baca opini yang konstruktif dan realistis gini ✨",
            "Valid no debat sih ini. Mindset jangka panjang emang satu-satunya kunci bertahan di crypto 💯",
            "Makasih udah sharing insight dagingnya bang! Konten kayak gini yang bikin timeline tetap bernilai 🙌🔥",
            "Poin penting yang sering dilewatin orang. Sukses terus dan sehat selalu bang! 👍"
        ]
    }
}


def detect_context(text: str) -> str:
    """Mendeteksi apakah tweet tentang airdrop, market, tech/milestone, atau general."""
    t = text.lower()
    if any(k in t for k in ["airdrop", "testnet", "guide", "tutor", "alpha", "grind", "claim", "snapshot", "retroactive", "faucet", "eligib"]):
        return "airdrop"
    elif any(k in t for k in ["btc", "sol", "eth", "price", "chart", "support", "resist", "ath", "bull", "bear", "pump", "dip", "trading", "volume", "market"]):
        return "market"
    elif any(k in t for k in ["mainnet", "launch", "shipped", "update", "upgrade", "milestone", "partnership", "release", "dev", "infrastructure", "l2"]):
        return "tech"
    return "general"


def detect_language(text: str) -> str:
    """Deteksi bahasa tweet (Indonesian atau English)."""
    t = text.lower()
    id_words = {"yang", "ini", "dan", "di", "ke", "dari", "bisa", "untuk", "garap", "cuan", "mantap", "bang", "nih", "udah", "kita", "kalian"}
    words = set(re.findall(r"\b[a-zA-Z]{2,}\b", t))
    return "id" if len(words.intersection(id_words)) >= 2 else "en"


def generate_contextual_comment(tweet_text: str) -> str:
    """Menghasilkan komentar yang sangat pas dengan isi tweet viral."""
    ctx = detect_context(tweet_text)
    lang = detect_language(tweet_text)

    pool = SMART_COMMENTS.get(ctx, SMART_COMMENTS["general"]).get(lang, SMART_COMMENTS["general"]["en"])
    return random.choice(pool)


def load_history() -> set:
    if not ENGAGEMENT_LOG_FILE.exists():
        return set()
    try:
        with open(ENGAGEMENT_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.keys())
    except Exception:
        return set()


def record_engagement(tweet_id: str, author: str, tweet_url: str, actions: list[str], comment: str, account: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = {}
    if ENGAGEMENT_LOG_FILE.exists():
        try:
            with open(ENGAGEMENT_LOG_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    history[tweet_id] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": account,
        "author": author,
        "url": tweet_url,
        "actions": actions,
        "comment": comment
    }

    try:
        with open(ENGAGEMENT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


async def engage_with_tweet(
    page: Page,
    tweet_url: str,
    tweet_id: str,
    author: str,
    tweet_text: str,
    do_like: bool = True,
    do_retweet: bool = True,
    do_comment: bool = True,
    account_name: str = ""
) -> tuple[bool, list[str]]:
    """
    Mengeksekusi aksi Like, Retweet, dan Komen kontekstual di halaman tweet.
    TIDAK melakukan Follow (sesuai permintaan user).
    """
    actions_done = []
    try:
        print(f"  {CYAN}📂 Membuka tweet: {tweet_url} ...{RESET}", flush=True)
        await page.goto(tweet_url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(3)

        main_tweet = page.locator('article[data-testid="tweet"]').first
        if await main_tweet.count() == 0:
            print(f"  {YELLOW}⚠️ Tweet tidak dapat dimuat atau sudah dihapus.{RESET}", flush=True)
            return False, []

        # 1. LIKE ❤️
        if do_like:
            like_btn = main_tweet.locator('[data-testid="like"]').first
            unlike_btn = main_tweet.locator('[data-testid="unlike"]').first
            if await unlike_btn.count() > 0 and await unlike_btn.is_visible():
                actions_done.append("Liked (already)")
                print(f"    ❤️  Like    : {YELLOW}✓ Sudah di-like sebelumnya{RESET}", flush=True)
            elif await like_btn.count() > 0 and await like_btn.is_visible():
                await like_btn.click(force=True)
                actions_done.append("Like ❤️")
                print(f"    ❤️  Like    : {GREEN}✓ Berhasil Like{RESET}", flush=True)
                await asyncio.sleep(0.8)

        # 2. RETWEET 🔁
        if do_retweet:
            rt_btn = main_tweet.locator('[data-testid="retweet"]').first
            unrt_btn = main_tweet.locator('[data-testid="unretweet"]').first
            if await unrt_btn.count() > 0 and await unrt_btn.is_visible():
                actions_done.append("RT (already)")
                print(f"    🔁 Retweet : {YELLOW}✓ Sudah di-RT sebelumnya{RESET}", flush=True)
            elif await rt_btn.count() > 0 and await rt_btn.is_visible():
                await rt_btn.click(force=True)
                await asyncio.sleep(0.8)
                confirm_btn = page.locator('[data-testid="retweetConfirm"], [role="menuitem"]:has-text("Repost"), [role="menuitem"]:has-text("Posting ulang")').first
                try:
                    await confirm_btn.wait_for(state="visible", timeout=3500)
                    await confirm_btn.click(force=True)
                    actions_done.append("Retweet 🔁")
                    print(f"    🔁 Retweet : {GREEN}✓ Berhasil Retweet / Repost{RESET}", flush=True)
                    await asyncio.sleep(0.8)
                except Exception:
                    pass
                await page.keyboard.press("Escape")

        # 3. COMMENT 💬 (KONTEKSTUAL, BUKAN DROP WALLET)
        chosen_comment = ""
        if do_comment:
            chosen_comment = generate_contextual_comment(tweet_text)
            reply_textarea = page.locator('[data-testid="tweetTextarea_0"]').first

            # Jika textarea inline belum tampak, klik tombol reply di tweet
            if await reply_textarea.count() == 0 or not await reply_textarea.is_visible():
                reply_btn = main_tweet.locator('[data-testid="reply"]').first
                if await reply_btn.count() > 0 and await reply_btn.is_visible():
                    await reply_btn.click(force=True)
                    await asyncio.sleep(1.0)

            try:
                await reply_textarea.wait_for(state="visible", timeout=8000)
                await reply_textarea.click()
                await asyncio.sleep(0.4)
                await reply_textarea.fill(chosen_comment)
                await asyncio.sleep(0.8)

                # Trigger lexical change
                await reply_textarea.press("End")
                await reply_textarea.type(" ")
                await reply_textarea.press("Backspace")
                await asyncio.sleep(0.5)

                send_btn = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first
                if await send_btn.is_enabled():
                    await send_btn.click(force=True)
                    actions_done.append("Comment 💬")
                    print(f"    💬 Comment : {GREEN}✓ Berhasil Komen!{RESET}", flush=True)
                    print(f"       {MAGENTA}\"{chosen_comment}\"{RESET}", flush=True)
                    await asyncio.sleep(2.0)
                else:
                    print(f"    💬 Comment : {RED}✗ Tombol kirim non-aktif{RESET}", flush=True)
            except Exception as ce:
                print(f"    💬 Comment : {YELLOW}✗ Tidak dapat berkomentar ({ce}){RESET}", flush=True)

        record_engagement(tweet_id, author, tweet_url, actions_done, chosen_comment, account_name)
        return True, actions_done

    except Exception as e:
        print(f"  {RED}❌ Error interaksi tweet: {e}{RESET}", flush=True)
        return False, []


async def scrape_viral_candidates(page: Page, query: str, limit: int = 5) -> list[dict]:
    """Scrape tweet viral seputar airdrop dan crypto dari Twitter Search."""
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&f=top"

    print(f"  {CYAN}🔍 Mencari postingan viral crypto: {query[:60]}...{RESET}", flush=True)
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(4)
    except Exception as e:
        print(f"  {YELLOW}Notice navigasi pencarian: {e}{RESET}", flush=True)

    history = load_history()
    candidates = []

    for _ in range(4):
        articles = await page.locator('article[data-testid="tweet"]').all()
        for art in articles:
            try:
                # Ambil link tweet
                link_el = art.locator('a[href*="/status/"]').first
                if await link_el.count() == 0:
                    continue
                href = await link_el.get_attribute("href")
                if not href or "/status/" not in href:
                    continue

                parts = href.strip("/").split("/status/")
                author = parts[0].split("/")[-1]
                tweet_id = parts[1].split("?")[0].split("/")[0]

                if tweet_id in history or any(c["id"] == tweet_id for c in candidates):
                    continue

                # Ambil teks tweet
                text_el = art.locator('[data-testid="tweetText"]').first
                text = await text_el.inner_text() if await text_el.count() > 0 else ""
                text_lower = text.lower()

                # Filter ketat: Jangan ambil postingan giveaway drop wallet
                if any(forb in text_lower for forb in FORBIDDEN_KEYWORDS):
                    continue

                full_url = f"https://x.com/{author}/status/{tweet_id}"
                candidates.append({
                    "id": tweet_id,
                    "author": author,
                    "url": full_url,
                    "text": text
                })

                if len(candidates) >= limit:
                    break
            except Exception:
                continue

        if len(candidates) >= limit:
            break

        await page.evaluate("window.scrollBy(0, 1500);")
        await asyncio.sleep(2)

    return candidates


async def run_account_engagement(
    account_key: str,
    account_info: dict,
    tweets_per_account: int = 2,
    do_like: bool = True,
    do_retweet: bool = True,
    do_comment: bool = True,
    headless: bool = True
) -> dict:
    """Menjalankan interaksi viral untuk 1 akun."""
    uname = account_info.get("screen_name", account_key)
    dname = account_info.get("name", uname)
    auth_token = account_info.get("auth_token", "").strip()
    ct0 = account_info.get("ct0", "").strip()

    stats = {"account": uname, "engaged": 0, "status": "SUCCESS"}

    if not auth_token or not ct0 or account_info.get("suspended"):
        stats["status"] = "SKIPPED"
        return stats

    sync_active_cookies(account_info)

    print(f"\n{CYAN}┌─────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│ 🚀 Memproses Engagement untuk: {BOLD}@{uname}{RESET}{CYAN} ({dname}){' ' * max(0, 31 - len(uname) - len(dname))}│{RESET}")
    print(f"{CYAN}│ 🎯 Target: {tweets_per_account} Tweet Viral (Like ❤️, Retweet 🔁, Komen 💬){' ' * max(0, 10)}│{RESET}")
    print(f"{CYAN}└─────────────────────────────────────────────────────────────┘{RESET}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        await context.add_cookies([
            {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
        ])
        page = await context.new_page()

        # 1. Cari kandidat tweet viral
        selected_query = random.choice(VIRAL_SEARCH_QUERIES)
        candidates = await scrape_viral_candidates(page, selected_query, limit=tweets_per_account + 2)

        if not candidates:
            # Fallback ke query lain
            for alt_q in VIRAL_SEARCH_QUERIES:
                if alt_q != selected_query:
                    candidates = await scrape_viral_candidates(page, alt_q, limit=tweets_per_account + 2)
                    if candidates:
                        break

        print(f"  {GREEN}✓ Ditemukan {len(candidates)} tweet viral crypto yang cocok (bebas giveaway drop).{RESET}", flush=True)

        for c in candidates[:tweets_per_account]:
            print(f"\n  ▶ Membalas postingan viral @{c['author']} (ID: {c['id']}):")
            snippet = c['text'].replace('\n', ' ')[:80]
            print(f"    Preview: \"{snippet}...\"", flush=True)

            ok, acts = await engage_with_tweet(
                page=page,
                tweet_url=c["url"],
                tweet_id=c["id"],
                author=c["author"],
                tweet_text=c["text"],
                do_like=do_like,
                do_retweet=do_retweet,
                do_comment=do_comment,
                account_name=uname
            )
            if ok and acts:
                stats["engaged"] += 1
                await asyncio.sleep(random.uniform(4.0, 7.0))

        await browser.close()

    print(f"  {GREEN}🏁 Selesai untuk @{uname}: Berhasil interaksi di {stats['engaged']} postingan viral!{RESET}\n", flush=True)
    return stats


async def run_multi_account_engagement(
    tweets_per_account: int = 2,
    do_like: bool = True,
    do_retweet: bool = True,
    do_comment: bool = True,
    delay_between_accounts: float = 12.0,
    target_account: str = "",
    headless: bool = True
):
    """Menjalankan engagement viral pada seluruh akun aktif."""
    data = load_accounts()
    accounts = data.get("accounts", {})
    if not accounts:
        print(f"{RED}Tidak ada akun di accounts.json!{RESET}")
        return

    if target_account:
        clean_target = target_account.lstrip("@").lower()
        active_keys = [
            k for k, v in accounts.items()
            if (k.lower() == clean_target or v.get("screen_name", "").lower() == clean_target)
            and not v.get("suspended")
        ]
    else:
        active_keys = [k for k, v in accounts.items() if not v.get("suspended")]

    total = len(active_keys)
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║     🔥 VIRAL CRYPTO & AIRDROP ENGAGEMENT BOT                  ║
║   Like ❤️  ➔ Retweet 🔁  ➔ Smart Contextual Comment 💬       ║
║   🚫 TANPA Follow (0 Following Tetap Terjaga)                 ║
║   🚫 BUKAN Giveaway Drop Address (Murni Diskusi Organik)      ║
║   Jumlah Akun Aktif: {total} Akun (Akun Suspended Dilewati)      ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    total_engaged = 0
    for idx, key in enumerate(active_keys, 1):
        acc = accounts[key]
        uname = acc.get("screen_name", key)

        print(f"{MAGENTA}{BOLD}================================================================{RESET}")
        print(f"{MAGENTA}{BOLD}▶ [{idx}/{total}] MEMULAI AKUN: @{uname}{RESET}")
        print(f"{MAGENTA}{BOLD}================================================================{RESET}")

        res = await run_account_engagement(
            account_key=key,
            account_info=acc,
            tweets_per_account=tweets_per_account,
            do_like=do_like,
            do_retweet=do_retweet,
            do_comment=do_comment,
            headless=headless
        )
        total_engaged += res["engaged"]

        if idx < total:
            wait_sec = random.uniform(delay_between_accounts * 0.8, delay_between_accounts * 1.2)
            print(f"{YELLOW}⏳ Jeda {wait_sec:.1f}s sebelum beralih ke akun berikutnya...{RESET}\n")
            await asyncio.sleep(wait_sec)

    print(f"\n{GREEN}{BOLD}================================================================{RESET}")
    print(f"{GREEN}{BOLD}🎉 SEMUA AKUN SELESAI MELAKUKAN ENGAGEMENT VIRAL!{RESET}")
    print(f"  • Total Tweet Di-engage : {BOLD}{total_engaged} Postingan Viral{RESET}")
    print(f"  • Akun Terlibat         : {total} Akun")
    print(f"  • Log Riwayat           : {ENGAGEMENT_LOG_FILE}")
    print(f"{GREEN}{BOLD}================================================================{RESET}\n")


async def run_engagement_loop(
    tweets_per_account: int = 2,
    interval_minutes_min: int = 40,
    interval_minutes_max: int = 80,
    do_like: bool = True,
    do_retweet: bool = True,
    do_comment: bool = True,
    headless: bool = True
):
    """Loop terjadwal terus menerus untuk engagement viral."""
    cycle = 1
    while True:
        print(f"\n{CYAN}{BOLD}================================================================{RESET}")
        print(f"{CYAN}{BOLD}🔄 MEMULAI SIKLUS VIRAL ENGAGEMENT #{cycle} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}){RESET}")
        print(f"{CYAN}{BOLD}================================================================{RESET}")

        await run_multi_account_engagement(
            tweets_per_account=tweets_per_account,
            do_like=do_like,
            do_retweet=do_retweet,
            do_comment=do_comment,
            delay_between_accounts=12.0,
            headless=headless
        )

        sleep_min = random.randint(interval_minutes_min, interval_minutes_max)
        wake_time = datetime.fromtimestamp(datetime.now().timestamp() + (sleep_min * 60)).strftime("%H:%M:%S")
        print(f"{MAGENTA}💤 Siklus #{cycle} selesai. Tidur selama {sleep_min} menit...{RESET}")
        print(f"{MAGENTA}⏰ Bangun berikutnya pada: {wake_time}{RESET}\n")

        cycle += 1
        await asyncio.sleep(sleep_min * 60)


def main():
    parser = argparse.ArgumentParser(description="Viral Crypto & Airdrop Engagement Bot")
    parser.add_argument("-a", "--account", type=str, default="", help="Jalankan hanya untuk 1 akun tertentu")
    parser.add_argument("-n", "--count", type=int, default=2, help="Jumlah tweet viral per akun (default: 2)")
    parser.add_argument("--no-retweet", action="store_true", help="Jangan lakukan retweet (hanya like & komen)")
    parser.add_argument("--no-like", action="store_true", help="Jangan lakukan like")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus menerus dalam siklus terjadwal")
    parser.add_argument("--interval-min", type=int, default=40, help="Interval tidur minimal dalam menit jika --loop")
    parser.add_argument("--interval-max", type=int, default=80, help="Interval tidur maksimal dalam menit jika --loop")
    parser.add_argument("--delay", type=float, default=12.0, help="Jeda antar akun dalam detik (default: 12.0)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan browser Chrome (default: headless)")

    args = parser.parse_args()

    do_like = not args.no_like
    do_retweet = not args.no_retweet

    if args.loop:
        try:
            asyncio.run(run_engagement_loop(
                tweets_per_account=args.count,
                interval_minutes_min=args.interval_min,
                interval_minutes_max=args.interval_max,
                do_like=do_like,
                do_retweet=do_retweet,
                do_comment=True,
                headless=not args.visible
            ))
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot dihentikan oleh pengguna.{RESET}")
            sys.exit(0)
    else:
        try:
            asyncio.run(run_multi_account_engagement(
                tweets_per_account=args.count,
                do_like=do_like,
                do_retweet=do_retweet,
                do_comment=True,
                delay_between_accounts=args.delay,
                target_account=args.account,
                headless=not args.visible
            ))
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot dihentikan oleh pengguna.{RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
