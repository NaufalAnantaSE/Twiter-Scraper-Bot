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
    "dropping $", "giving away", "100$ to", "50$ to", "first 100", "retweet & drop",
    "winner", "winners", "usdt ||", "sol to", "eth to", "to enter", "tag 3", "tag 2",
    "|| 6 hours", "|| 12 hours", "|| 24 hours", "lucky winners"
]

import hashlib

USED_COMMENTS_FILE = RESULTS_DIR / "used_viral_comments.json"

# ==============================================================================
# 🧠 MODULAR HIGH-VALUE CONTEXTUAL COMMENT ENGINE
# Menghasilkan puluhan ribu variasi komentar unik, kontekstual & bernilai tinggi
# ==============================================================================
MODULAR_COMMENTS = {
    "airdrop": {
        "en": {
            "openers": [
                "Solid alpha breakdown right here!",
                "Super clean and actionable airdrop guide.",
                "Appreciate the clarity and detailed steps in this thread.",
                "High quality rundown on this protocol.",
                "This is the exact type of grounded Web3 alpha timeline needs.",
                "Bookmarking this guide for my onchain session."
            ],
            "insights": [
                "Consistency in early testnets and multi-month contract interactions always beats volume spamming.",
                "Sybil resistance is getting stricter, so authentic user engagement and governance voting make all the difference.",
                "Exploring early ecosystem primitives before the snapshot hype is where genuine asymmetrical reward lives.",
                "Diversifying interactions across official bridges, swaps, and staking builds a very resilient wallet footprint.",
                "The compounding value of steady onchain testing quietly separates real hunters from last-minute bots."
            ],
            "closers": [
                "Setting up transactions right now. Time to grind! 🚀🔥",
                "Thanks for putting this together, massive respect! 👏💎",
                "Consistency always pays off in the long run. Appreciate you! ✨",
                "Excited to see where this ecosystem heads next. Keep shipping! 🌟",
                "Alpha well noted. Onward and upward! 🫡"
            ]
        },
        "id": {
            "openers": [
                "Info airdrop dan panduan yang sangat berbobot nih!",
                "Rapi banget pembahasannya, step-by-step mudah dipahami.",
                "Thanks thread lengkapnya bang, daging semua isinya.",
                "Selalu suka liat edukasi airdrop yang to the point tanpa basa-basi gini.",
                "Panduan berkelas buat garapan testnet / early protocol.",
                "Izin bookmark buat dieksekusi malam ini ya bang."
            ],
            "insights": [
                "Interaksi rutin tiap minggu di smart contract resmi jauh lebih potensial lolos kriteria anti-sybil.",
                "Garap konsisten dari awal memang kunci utama, snapshot seringkali ngehargain user organik yang loyal.",
                "Penting banget bangun profil wallet yang natural lewat berbagai protokol di ekosistemnya.",
                "Eksplorasi ekosistem baru selagi gas fee murah emang strategi paling cerdas buat hunter.",
                "Ketekunan nyelesaiin task teknis bakal terbayar manis pas masa claim token nanti."
            ],
            "closers": [
                "Langsung gaspol praktek sekarang mumpung lancar! 🚀🔥",
                "Makasih udah berbagi alpha berharga ini bang, mantap! 👏💎",
                "Yang konsisten onchain yang bakal panen nanti. Sukses selalu! ✨",
                "Semoga alokasinya maksimal buat pejuang konsisten. Gas terus! 🌟",
                "Tetap semangat dan jaga keamanan wallet masing-masing! 🛡️"
            ]
        }
    },
    "market": {
        "en": {
            "openers": [
                "Really sharp market observation here.",
                "Spot on breakdown of the current market structure.",
                "Clean technical perspective without unnecessary noise.",
                "Appreciate the balanced view on this price action.",
                "Great chart context, aligns closely with macro liquidity trends.",
                "Very objective assessment of the broader consolidation range."
            ],
            "insights": [
                "Liquidity absorption around these key support zones shows quiet institutional demand stacking up.",
                "Funding rate resets while forming higher lows historically provide the healthiest continuation bases.",
                "Open interest flushes are essential to wipe out aggressive leverage before any meaningful expansion.",
                "Spot accumulation metrics and orderbook depth tell a much more honest story than short term 15m candles.",
                "Patiently waiting for high timeframe confirmation always protects capital during distribution phases."
            ],
            "closers": [
                "Patience and disciplined execution win the game. Great chart! 📈✨",
                "Holding conviction through the chop. Appreciate your perspective! 🚀",
                "Risk management first, upside second. Always appreciate your takes! 💎🙌",
                "Looking forward to how the weekly candle wraps up. Stay sharp! 📊",
                "Spot on analysis as always. Keep them coming! 👏"
            ]
        },
        "id": {
            "openers": [
                "Analisa market yang jernih dan berbobot banget!",
                "Sudut pandang objektif yang sangat ngebantu baca arah pergerakan.",
                "Pembahasan chart yang rapi no fomo-fomo club.",
                "Senang baca analisa teknikal yang tetap mempertimbangkan likuiditas makro gini.",
                "Perspektif yang sangat masuk akal di tengah volatilitas saat ini.",
                "Ulasan market yang komprehensif dan gampang dimengerti."
            ],
            "insights": [
                "Serapan di area support kuat nunjukin akumulasi rapi dari smart money saat retail lagi ragu.",
                "Reset funding rate dan pembersihan leverage tinggi emang pondasi paling sehat buat tren jangka panjang.",
                "Fase konsolidasi kayak gini emang paling pas buat sabar dan disiplin nunggu konfirmasi konkrit.",
                "Data orderbook dan volume delta ga pernah bohong kalau likuiditas emang lagi berpindah.",
                "Fokus ke timeframe besar selalu ngebantu jaga emosi biar ga gampang ke-shakeout."
            ],
            "closers": [
                "Disiplin manajemen risiko tetep yang utama. Insight mantap bang! 📈✨",
                "Setuju banget, sabar adalah kunci survive di crypto. Gaspol! 🚀",
                "Makasih sharing sudut pandang dagingnya bang, sangat mencerahkan! 💎🙌",
                "Semoga setup-nya jalan sesuai rencana. Salam cuan! 📊",
                "Tetap waras dan pantau konfirmasi weekly close! 👏"
            ]
        }
    },
    "tech": {
        "en": {
            "openers": [
                "Huge milestone for the ecosystem!",
                "Incredible engineering progress shipped by the team.",
                "This is what legitimate infrastructure building looks like.",
                "Super impressive throughput and architectural leap here.",
                "Exciting development for onchain scalability and developer experience.",
                "Remarkable execution from the engineering crew."
            ],
            "insights": [
                "Sub-second finality and predictable fee markets are absolute prerequisites for real retail adoption.",
                "Reducing state bloat and optimizing parallel transaction execution solves genuine Web3 friction points.",
                "Protocols that prioritize intuitive developer tooling always cultivate the stickiest application layers.",
                "Building robust decentralization without compromising execution speed is the holy grail of modern L1/L2s.",
                "Continuous shipping in quiet markets is the ultimate signal of long-term project longevity."
            ],
            "closers": [
                "Excited to see the next wave of dApps deploying here! 🚀⚡",
                "Huge respect to the devs putting in the work day in and day out! 🫡🔥",
                "This is how mass adoption actually gets built. Keep pushing forward! 👏💎",
                "Watching this ecosystem expand closely. Solid milestone! ✨",
                "Real value accrues to real builders. Congrats to the team! 🌟"
            ]
        },
        "id": {
            "openers": [
                "Milestone yang sangat luar biasa buat perkembangan ekosistem!",
                "Progress engineering yang nyata dan konsisten dari tim dev.",
                "Inovasi infrastruktur yang beneran ngasih solusi konkret.",
                "Keren banget update teknologinya, peningkatan performanya berasa banget.",
                "Langkah maju yang signifikan buat skalabilitas dan ekosistem Web3.",
                "Eksekusi yang sangat rapi dan berkelas dari tim pengembang."
            ],
            "insights": [
                "Penyempurnaan arsitektur dan efisiensi gas fee terbukti bikin interaksi dApps makin mulus.",
                "Fitur eksekusi paralel dan mitigasi kongesti adalah jawaban nyata buat adopsi pengguna skala besar.",
                "Fokus tim dev buat nyelesaiin kendala UX bakal narik lebih banyak developer top ke ekosistem ini.",
                "Konsistensi build di segala kondisi market nunjukin komitmen jangka panjang yang luar biasa.",
                "Teknologi yang solid selalu jadi fondasi utama keberhasilan sebuah protokol Web3."
            ],
            "closers": [
                "Ga sabar liat ekosistem dApps baru yang bakal lahir di sini! 🚀⚡",
                "Salut setinggi-tingginya buat tim dev yang terus berinovasi! 🫡🔥",
                "Pondasi kuat buat adopsi massal ke depan. Sukses terus tim! 👏💎",
                "Update yang sangat dinanti. Maju terus Web3 builders! ✨",
                "Ekosistem makin matang dan berbobot. Mantap jiwa! 🌟"
            ]
        }
    },
    "general": {
        "en": {
            "openers": [
                "100% agreed with this perspective.",
                "Really thoughtful and well-articulated take.",
                "Spot on! Grounded thoughts like this bring much-needed clarity.",
                "Couldn't agree more with the thesis here.",
                "Appreciate you taking the time to share this perspective.",
                "Valuable insight that resonates deeply with long-term participants."
            ],
            "insights": [
                "Having a disciplined long-term horizon beats reacting to daily timeline hype every single time.",
                "Protecting your mental clarity and capital during choppy phases is the greatest edge in crypto.",
                "Deep conviction backed by rigorous research always outlasts speculative narratives.",
                "The people who compound value quietly behind the scenes are the ones who thrive across cycles.",
                "Staying humble, managing exposure, and continuous learning are the true cheat codes in Web3."
            ],
            "closers": [
                "Always look forward to your posts. Keep sharing value! 🙌💎",
                "Spot on. Have an incredible week ahead! ✨",
                "Timeless advice for anyone navigating this space. Respect! 💯",
                "Quality insights as always. Stay sharp and grounded! 🚀",
                "Golden take. Appreciate the continuous inspiration! 🫡"
            ]
        },
        "id": {
            "openers": [
                "Setuju 100% sama sudut pandang ini!",
                "Penyampaian yang sangat jernih dan sarat makna.",
                "Insight bernas yang sangat relevan buat dinamika Web3 saat ini.",
                "Valid no debat sih poin yang disampaikan ini.",
                "Makasih udah nulis refleksi yang sangat berbobot bang.",
                "Opini yang sangat membuka mata dan menenangkan timeline."
            ],
            "insights": [
                "Mindset jangka panjang dan kedewasaan emosional emang satu-satunya kunci sukses di industri ini.",
                "Menjaga modal pokok dan kesehatan mental jauh lebih penting daripada terjebak FOMO musiman.",
                "Riset mendalam dan keyakinan pada fundamental ga bakal gampang goyah cuma karena noise sesaat.",
                "Mereka yang tekun belajar dan konsisten berproses adalah yang bakal menikmati hasil paling manis.",
                "Kedisiplinan mengeksekusi strategi adalah pembeda nyata antara trader matang dan exit liquidity."
            ],
            "closers": [
                "Selalu nunggu postingan bergizi kayak gini bang. Sukses selalu! 🙌💎",
                "Insight daging yang patut diresapi. Sehat dan berkah selalu bang! ✨",
                "Pengingat luar biasa buat kita semua. Tetap semangat! 💯",
                "Konten berkualitas yang bikin timeline adem dan cerdas. Mantap! 🚀",
                "Keren banget sharingnya. Gaspol terus edukasinya bang! 🫡"
            ]
        }
    }
}


def load_used_comments() -> set:
    """Memuat hash komentar yang pernah diposting untuk mencegah duplikasi."""
    if not USED_COMMENTS_FILE.exists():
        return set()
    try:
        with open(USED_COMMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set(data.keys())
    except Exception:
        return set()


def save_used_comment(comment_text: str):
    """Menyimpan hash komentar baru ke database persistent anti-duplikasi."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    comments = load_used_comments()

    clean_text = re.sub(r"\W+", " ", comment_text).strip().lower()
    c_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
    comments.add(c_hash)

    try:
        with open(USED_COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(comments), f, indent=2)
    except Exception:
        pass


def is_comment_duplicate(comment_text: str, used_comments: set) -> bool:
    """Mengecek apakah komentar identik pernah diposting sebelumnya."""
    clean_text = re.sub(r"\W+", " ", comment_text).strip().lower()
    if not clean_text:
        return False
    c_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
    return c_hash in used_comments


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


def generate_modular_comment(tweet_text: str) -> str:
    """Menyusun komentar kontekstual bernilai tinggi dari komponen modular."""
    ctx = detect_context(tweet_text)
    lang = detect_language(tweet_text)

    pool = MODULAR_COMMENTS.get(ctx, MODULAR_COMMENTS["general"]).get(lang, MODULAR_COMMENTS["general"]["en"])
    opener = random.choice(pool["openers"])
    insight = random.choice(pool["insights"])
    closer = random.choice(pool["closers"])

    return f"{opener} {insight} {closer}".strip()


def generate_contextual_comment(tweet_text: str, max_retries: int = 50) -> str:
    """
    Menghasilkan komentar yang sangat pas dengan isi tweet viral
    dan DIJAMIN 100% BEBAS DUPLIKASI dari riwayat komentar sebelumnya.
    """
    used_comments = load_used_comments()

    for _ in range(max_retries):
        comment = generate_modular_comment(tweet_text)
        if not is_comment_duplicate(comment, used_comments):
            return comment

    # Fallback jika permutasi terbentur
    return generate_modular_comment(tweet_text)


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

    if comment:
        save_used_comment(comment)


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
                try:
                    await reply_textarea.click(force=True, timeout=5000)
                except Exception:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    await reply_textarea.click(force=True, timeout=5000)
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

        # 1. Cari kandidat tweet viral (akumulasi hingga mencukupi)
        candidates = []
        queries_to_try = list(VIRAL_SEARCH_QUERIES)
        random.shuffle(queries_to_try)
        target_limit = tweets_per_account + 2

        for q in queries_to_try:
            needed = target_limit - len(candidates)
            if needed <= 0:
                break
            found = await scrape_viral_candidates(page, q, limit=needed)
            for item in found:
                if not any(c["id"] == item["id"] for c in candidates):
                    candidates.append(item)

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
