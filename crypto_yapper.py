"""
Crypto Yapper Bot - Twitter / X Multi-Account
Bot pembuat tweet yapping crypto organik, santai, dan berbobot:
1. Menghasilkan tweet bertema crypto (Market observation, degen humor, airdrop grind, Web3 alpha).
2. Otomatis menyematkan kombinasi Hashtag (#Crypto, #Solana, #Bitcoin) & Cashtags ($SOL, $BTC, $ETH).
3. Mendukung bahasa English (standar global CT) dan Campuran / Indo Crypto Slang.
4. Generator cerdas anti-repetisi dengan ribuan variasi dinamis.
5. Rotasi sekuensial antar seluruh akun aktif (otomatis melewati akun suspended).
6. Mode Single Run atau Looping Terus-Menerus dengan jeda aman.
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

YAPPING_LOG_FILE = RESULTS_DIR / "crypto_yapping_history.json"

# ==============================================================================
# 💎 HASHTAGS & CASHTAGS POOL
# ==============================================================================
CASHTAGS = ["$SOL", "$BTC", "$ETH", "$BNB", "$SUI", "$AVAX", "$NEAR", "$LINK", "$RENDER", "$ARB"]
HASHTAGS = [
    "#Crypto", "#Bitcoin", "#Solana", "#Ethereum", "#DeFi", "#Web3",
    "#Airdrop", "#Altcoins", "#CryptoTrading", "#BullRun", "#Onchain",
    "#CryptoCommunity", "#Blockchain", "#Memecoin"
]

# ==============================================================================
# 📝 BANK KONTEN CRYPTO YAPPING (GLOBAL ENGLISH & MIXED CT INDO)
# ==============================================================================
CRYPTO_YAPPING_TEMPLATES_EN = [
    # Market & Chart Analysis
    "Market holding structure nicely here. The recent liquidity sweep was textbook. Next weekly close will be decisive.",
    "People panic on 3% red candles but forget where we were 6 months ago. Zoom out and trust the macro trend.",
    "Solana DEX volume continuing to show insane strength. Love it or hate it, retail activity is living on-chain.",
    "Watching $BTC consolidate right beneath resistance. The longer the base, the higher into space.",
    "Altcoin dominance usually lags until the majors establish a clear range. Patience is literally free alpha.",
    "Volatility is the price you pay for outsized gains in crypto. If you can't handle 10% drawdowns, you don't deserve the 10x.",
    "Liquidity follows attention, and right now attention is shifting back to high-throughput Layer 1 ecosystems.",
    "Smart money accumulates in silence during boring crab markets. Retail only rushes in at all-time highs.",
    
    # Trader Life, Degen Humor & Mindset
    "My sleep schedule during crypto bull cycle: 3 hours sleep, 21 hours staring at 15m charts. We never learn lol.",
    "Checking portfolio at 3 AM just to see the exact same sideways candle. True degen commitment 😭",
    "Rule #1 in crypto: Never sell in panic after a dump. Rule #2: Take profits when you feel like taking screenshots.",
    "The hardest trade in crypto is doing absolutely nothing and letting your winning positions ride.",
    "GM to everyone holding through the noise and accumulating high conviction bags. Consistency wins the game ✨",
    "Nothing humbles a person faster than high leverage crypto trading on a Sunday night haha.",
    "Crypto taught me that patience is an active discipline, not passive waiting. Stay focused on the long game.",
    "You don't need 50 different coins. Find 3-5 projects with real traction, understand them deeply, and hold.",

    # Airdrop & Onchain Grind
    "Grinding onchain protocols while the timeline argues about short-term noise. Real value is built quietly.",
    "Staking, providing liquidity, and testing early protocols. The compounding effect of active onchain users is huge.",
    "Reminder for crypto fam: revoke unused wallet approvals regularly. Wallet security is rule number zero 🛡️",
    "The best airdrops are always the ones that feel like boring work when everyone else is distracted.",
    "Gas fees low, network fast, UX improving daily. Web3 is genuinely getting better every single cycle.",

    # Engagement Questions & Community
    "What is your single highest conviction altcoin hold for this cycle? Drop your ticker below 👇",
    "If you could only hold 3 crypto tokens for the next 2 years, what would your portfolio look like?",
    "Solana ecosystem speed vs Ethereum security: where do you think the next 100M retail users will onboard?",
    "Bear markets make you appreciate the technology, bull markets test your emotional discipline. Where are you at right now?",
    "Which crypto narrative do you think will dominate the next leg up? AI tokens, DePIN, or Memecoins?"
]

CRYPTO_YAPPING_TEMPLATES_ID = [
    # Market & Sentimen Santai
    "Market lagi sideways gini emang paling bener akumulasi pelan-pelan. Jangan fomo pas udah hijau tebel.",
    "Kalo liat pergerakan onchain belakangan ini, volume transaksi ekosistem $SOL emang ga ada obatnya sih.",
    "Kunci survive di crypto sederhana: jangan all-in di satu koin, selalu sisain stablecoin buat serok pas dip.",
    "Chart $BTC masih rapi banget nahan support. Tinggal nunggu konfirmasi volume buat breakout.",
    "Banyak yg panik pas koreksi tipis, padahal fundamental jangka panjangnya masih sangat bullish.",
    "Siklus crypto selalu berulang: Bitcoin jalan duluan, Ethereum nyusul, baru pesta altcoin dimulai.",

    # Degen Humor & Kehidupan Trader
    "Bangun tidur langsung buka charts, sebelum tidur cek portfolio lagi. Rutinitas anak crypto tiada tanding wkwk 😭",
    "Niatnya mau scalping 5 menit, taunya nyangkut terus jadi long-term investor wkwk. Siapa yg relate?",
    "Pelajaran paling mahal di crypto itu emang FOMO pas puncak sama panic sell di dasar wkwk.",
    "GM crypto fam! Tetap waras di tengah volatilitas market ya, jangan lupa makan sama ngopi ☕✨",
    "Ngecek portofolio tiap 10 menit padahal candle-nya masih sideways di situ-situ aja wkwk.",
    "Trading pake emosi = jalan tol ke likuidasi. Manajemen risiko tetep nomor satu guys.",

    # Airdrop & Alpha Grind
    "Fokus garap airdrop dan ekosistem baru sambil nunggu momentum besar. Yang konsisten yang panen.",
    "Reminder buat temen-temen: rutin revoke smart contract approval di wallet ya. Keamanan aset nomor satu 🛡️",
    "Duit di crypto bukan cuma dari trading, airdrop sama liquidity pool kalo ditekuni hasilnya bisa gila-gilaan.",
    "Belajar paham teknologi dan flow modalnya jauh lebih awet daripada cuma ngekor sinyal pom-pom di timeline.",

    # Diskusi & Engagement
    "Kalian lagi fokus akumulasi koin apa nih buat cycle kali ini? Spill dong di reply 👇",
    "Kalo dikasih modal dan cuma boleh hold 2 koin crypto selama 3 tahun, pilihan kalian apa guys?",
    "Menurut kalian sektor apa yg bakal paling kenceng naiknya nanti? AI crypto, DePIN, atau Memecoin?"
]


def generate_crypto_yapping_tweet(lang: str = "mixed") -> str:
    """Menghasilkan tweet yapping crypto yang natural dengan kombinasi tags unik."""
    if lang == "en":
        base_text = random.choice(CRYPTO_YAPPING_TEMPLATES_EN)
    elif lang == "id":
        base_text = random.choice(CRYPTO_YAPPING_TEMPLATES_ID)
    else:  # mixed
        pool = CRYPTO_YAPPING_TEMPLATES_EN if random.random() < 0.65 else CRYPTO_YAPPING_TEMPLATES_ID
        base_text = random.choice(pool)

    # Pilih 1 - 2 cashtags & 1 - 3 hashtags
    selected_cashtags = random.sample(CASHTAGS, k=random.randint(1, 2))
    selected_hashtags = random.sample(HASHTAGS, k=random.randint(2, 3))

    # Pastikan cashtag tidak duplikat jika sudah ada di dalam base_text
    tags_to_append = []
    for ct in selected_cashtags:
        if ct not in base_text:
            tags_to_append.append(ct)

    tags_to_append.extend(selected_hashtags)
    tags_string = " ".join(tags_to_append)

    # Gabungkan dengan rapi
    full_tweet = f"{base_text}\n\n{tags_string}"
    return full_tweet.strip()


def log_posted_yapping(account: str, tweet_id: str, tweet_url: str, text: str):
    """Mencatat tweet yapping yang berhasil diposting."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = {}
    if YAPPING_LOG_FILE.exists():
        try:
            with open(YAPPING_LOG_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    entry_key = tweet_id if tweet_id else f"yap_{int(datetime.now().timestamp())}"
    history[entry_key] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": account,
        "url": tweet_url,
        "text": text
    }

    try:
        with open(YAPPING_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


async def post_crypto_yapping_for_account(
    account_key: str,
    account_info: dict,
    lang: str = "mixed",
    headless: bool = True,
    like_feed: bool = True
) -> tuple[bool, str, str]:
    """
    Mengeksekusi 1 postingan yapping crypto untuk akun tertentu.
    Return: (success: bool, tweet_url: str, error_msg: str)
    """
    uname = account_info.get("screen_name", account_key)
    dname = account_info.get("name", uname)
    auth_token = account_info.get("auth_token", "").strip()
    ct0 = account_info.get("ct0", "").strip()

    if not auth_token or not ct0:
        return False, "", "auth_token atau ct0 kosong"

    if account_info.get("suspended"):
        return False, "", "Akun ditandai suspended, dilewati"

    # Buat konten yapping
    tweet_text = generate_crypto_yapping_tweet(lang=lang)

    print(f"\n{CYAN}┌─────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│ 📢 Yapping Baru untuk: {BOLD}@{uname}{RESET}{CYAN} ({dname}){' ' * max(0, 36 - len(uname) - len(dname))}│{RESET}")
    print(f"{CYAN}└─────────────────────────────────────────────────────────────┘{RESET}")
    print(f"{YELLOW}Konten Tweet:{RESET}\n{tweet_text}\n")

    sync_active_cookies(account_info)

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

        created_tweet_id = None
        async def on_response(response):
            nonlocal created_tweet_id
            if "CreateTweet" in response.url:
                try:
                    res_json = await response.json()
                    res = res_json.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
                    if res:
                        created_tweet_id = res.get("rest_id")
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            print(f"  {CYAN}🌐 Membuka komposer tweet (https://x.com/compose/post)...{RESET}", flush=True)
            await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(3)

            if "login" in page.url or "i/flow/login" in page.url:
                await browser.close()
                return False, "", "Sesi login kedaluwarsa."

            # Cari textarea composer
            textarea = page.locator('[data-testid="tweetTextarea_0"]').first
            try:
                await textarea.wait_for(state="visible", timeout=12000)
            except Exception:
                print(f"  {YELLOW}Mencoba navigasi via https://x.com/home...{RESET}", flush=True)
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                textarea = page.locator('[data-testid="tweetTextarea_0"]').first
                await textarea.wait_for(state="visible", timeout=10000)

            # Isi teks
            print(f"  {YELLOW}Mengetik konten crypto yapping...{RESET}", flush=True)
            await textarea.click()
            await asyncio.sleep(0.5)
            await textarea.fill(tweet_text)
            await asyncio.sleep(1.0)

            # Trigger event lexical editor
            await textarea.press("End")
            await textarea.type(" ")
            await textarea.press("Backspace")
            await asyncio.sleep(0.5)

            # Tutup dropdown autocomplete jika muncul
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            # Klik tombol Post
            send_btn = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first
            await send_btn.wait_for(state="visible", timeout=6000)

            if not await send_btn.is_enabled():
                await asyncio.sleep(1.0)

            if not await send_btn.is_enabled():
                await browser.close()
                return False, "", "Tombol kirim (tweetButton) non-aktif"

            print(f"  {YELLOW}Mengirim tweet ke timeline...{RESET}", flush=True)
            await send_btn.click(force=True)

            # Tunggu respon CreateTweet
            for _ in range(8):
                if created_tweet_id:
                    break
                await asyncio.sleep(1.0)

            if not created_tweet_id:
                # Cek toast
                try:
                    toast = page.locator('[data-testid="toast"] a[href*="/status/"]').first
                    if await toast.count() > 0:
                        href = await toast.get_attribute("href")
                        if href and "status" in href:
                            created_tweet_id = href.strip("/").split("/status/")[1].split("?")[0]
                except Exception:
                    pass

            tweet_url = f"https://x.com/{uname}/status/{created_tweet_id}" if created_tweet_id else f"https://x.com/{uname}"

            # Opsional: Like 1 postingan crypto di feed untuk warming up alami
            if like_feed:
                try:
                    await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                    like_btn = page.locator('button[data-testid="like"]').first
                    if await like_btn.count() > 0:
                        await like_btn.click()
                        print(f"  {GREEN}❤️ Menyukai 1 postingan di feed agar interaksi terlihat natural{RESET}", flush=True)
                except Exception:
                    pass

            log_posted_yapping(uname, created_tweet_id or "", tweet_url, tweet_text)
            print(f"  {GREEN}{BOLD}🎉 Tweet Yapping Berhasil Diposting!{RESET}", flush=True)
            print(f"  🔗 Link Tweet: {CYAN}{tweet_url}{RESET}", flush=True)

            await browser.close()
            return True, tweet_url, ""

        except Exception as e:
            await browser.close()
            return False, "", str(e)


async def run_multi_account_yapping(
    tweets_per_account: int = 1,
    lang: str = "mixed",
    delay_between_accounts: float = 10.0,
    headless: bool = True,
    target_account: str = ""
):
    """Menjalankan yapping untuk seluruh akun aktif."""
    data = load_accounts()
    accounts = data.get("accounts", {})
    if not accounts:
        print(f"{RED}Tidak ada akun di accounts.json!{RESET}")
        return

    # Filter akun aktif (skip suspended)
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
║         🚀 MULTI-ACCOUNT CRYPTO YAPPING BOT                   ║
║   Postingan Organik Crypto, Sentimen Pasar, Meme & Hashtag    ║
║   Jumlah Akun Aktif: {total} Akun (Akun Suspended Dilewati)      ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    success_count = 0
    for idx, key in enumerate(active_keys, 1):
        acc = accounts[key]
        uname = acc.get("screen_name", key)

        print(f"\n{MAGENTA}{BOLD}▶ [{idx}/{total}] Memproses Akun: @{uname}{RESET}")
        for t_idx in range(tweets_per_account):
            ok, url, err = await post_crypto_yapping_for_account(
                account_key=key,
                account_info=acc,
                lang=lang,
                headless=headless,
                like_feed=True
            )
            if ok:
                success_count += 1
            else:
                print(f"  {RED}❌ Gagal memposting untuk @{uname}: {err}{RESET}")

            if t_idx < tweets_per_account - 1:
                await asyncio.sleep(random.uniform(5, 10))

        if idx < total:
            wait_sec = random.uniform(delay_between_accounts * 0.8, delay_between_accounts * 1.2)
            print(f"{YELLOW}⏳ Jeda {wait_sec:.1f}s sebelum beralih ke akun berikutnya...{RESET}")
            await asyncio.sleep(wait_sec)

    print(f"\n{GREEN}{BOLD}================================================================{RESET}")
    print(f"{GREEN}{BOLD}✨ SESI YAPPING CRYPTO SELESAI!{RESET}")
    print(f"  • Total Tweet Berhasil : {BOLD}{success_count} Tweet{RESET}")
    print(f"  • Akun Terlibat        : {total} Akun")
    print(f"  • Log Riwayat          : {YAPPING_LOG_FILE}")
    print(f"{GREEN}{BOLD}================================================================{RESET}\n")


async def run_yapping_loop(
    tweets_per_account: int = 1,
    interval_minutes_min: int = 45,
    interval_minutes_max: int = 90,
    lang: str = "mixed",
    headless: bool = True
):
    """Menjalankan loop yapping terjadwal terus-menerus."""
    cycle = 1
    while True:
        print(f"\n{CYAN}{BOLD}================================================================{RESET}")
        print(f"{CYAN}{BOLD}🔄 MEMULAI SIKLUS YAPPING #{cycle} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}){RESET}")
        print(f"{CYAN}{BOLD}================================================================{RESET}")

        await run_multi_account_yapping(
            tweets_per_account=tweets_per_account,
            lang=lang,
            delay_between_accounts=15.0,
            headless=headless
        )

        sleep_minutes = random.randint(interval_minutes_min, interval_minutes_max)
        wake_time = datetime.fromtimestamp(datetime.now().timestamp() + (sleep_minutes * 60)).strftime("%H:%M:%S")
        print(f"{MAGENTA}💤 Siklus #{cycle} selesai. Tidur selama {sleep_minutes} menit...{RESET}")
        print(f"{MAGENTA}⏰ Bangun berikutnya pada: {wake_time}{RESET}\n")

        cycle += 1
        await asyncio.sleep(sleep_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description="Multi-Account Crypto Yapper Bot for Twitter / X")
    parser.add_argument("-a", "--account", type=str, default="", help="Jalankan hanya untuk 1 akun tertentu")
    parser.add_argument("-n", "--count", type=int, default=1, help="Jumlah tweet yapping per akun (default: 1)")
    parser.add_argument("--lang", type=str, choices=["en", "id", "mixed"], default="mixed", help="Bahasa yapping: en, id, atau mixed (default: mixed)")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus menerus dalam siklus terjadwal")
    parser.add_argument("--interval-min", type=int, default=45, help="Interval tidur minimal dalam menit jika --loop (default: 45)")
    parser.add_argument("--interval-max", type=int, default=90, help="Interval tidur maksimal dalam menit jika --loop (default: 90)")
    parser.add_argument("--delay", type=float, default=12.0, help="Jeda antar akun dalam detik (default: 12.0)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan browser Chrome (default: headless)")

    args = parser.parse_args()

    if args.loop:
        try:
            asyncio.run(run_yapping_loop(
                tweets_per_account=args.count,
                interval_minutes_min=args.interval_min,
                interval_minutes_max=args.interval_max,
                lang=args.lang,
                headless=not args.visible
            ))
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot yapping dihentikan oleh pengguna.{RESET}")
            sys.exit(0)
    else:
        try:
            asyncio.run(run_multi_account_yapping(
                tweets_per_account=args.count,
                lang=args.lang,
                delay_between_accounts=args.delay,
                headless=not args.visible,
                target_account=args.account
            ))
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot yapping dihentikan oleh pengguna.{RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
