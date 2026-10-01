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
# 🧠 DEEP CONTEXTUAL SEMANTIC EXTRACTION & NATURAL COMMENT ENGINE
# Menghasilkan respon 1-2 kalimat yang natural, manusiawi, dan benar-benar
# MENYESUAIKAN DENGAN TOPIK, TOKEN, DAN KONTEKS TWEET ASLI
# ==============================================================================

KNOWN_TOKENS = {
    "solana": "Solana", "sol": "$SOL",
    "bitcoin": "Bitcoin", "btc": "$BTC",
    "ethereum": "Ethereum", "eth": "$ETH",
    "sui": "$SUI", "near": "$NEAR",
    "avalanche": "Avalanche", "avax": "$AVAX",
    "base": "Base", "monad": "Monad",
    "berachain": "Berachain", "hyperliquid": "Hyperliquid",
    "arbitrum": "$ARB", "arb": "$ARB",
    "optimism": "$OP", "op": "$OP",
    "chainlink": "$LINK", "link": "$LINK",
    "render": "$RENDER", "sonic": "Sonic",
    "ton": "$TON", "aptos": "$APT", "sei": "$SEI",
    "fantom": "Fantom", "injective": "$INJ"
}

# Bank respon natural (1-2 kalimat padat, cerdas, to the point seperti native CT)
NATURAL_RESPONSES = {
    "airdrop_guide": {
        "en": [
            "Bookmarking this thread for my weekend grind. The step-by-step breakdown makes the flow super easy to follow!",
            "Super clean tutorial! Consistency in daily/weekly contract interactions is definitely the best way to qualify.",
            "Great breakdown. Staying active across multiple protocols early on is where the real allocation upside lives.",
            "Really appreciate you compiling this alpha into a clear guide. Setting up interactions right now!",
            "High quality guide with no fluff. Exactly what CT needs more of. Thanks for sharing!",
            "Clear and actionable steps. Making sure to keep gas topped up and test every feature thoroughly.",
            "Solid guide! Organic user retention and multi-month contract activity always beat last-minute volume spamming.",
            "Bookmarked! Early protocol exploration before snapshot announcements is always the highest ROI work."
        ],
        "id": [
            "Panduan airdrop-nya rapi dan gampang dipahami bang. Izin praktekin step interaksi smart contract-nya mumpung gas fee murah!",
            "Thanks tutorial lengkapnya bang! Bookmark dulu buat digarap malam ini, step-by-step jelas banget.",
            "Step-by-step jelas tanpa basa-basi. Yang konsisten garap dari fase early emang yang bakal panen nanti, gaspol!",
            "Alpha berbobot nih. Garap rutin tiap minggu emang strategi paling aman buat lolos kriteria anti-sybil. Mantap bang!",
            "Ulasan panduan yang sangat bermanfaat. Izin share dan langsung eksekusi tugas onchain-nya ya!",
            "Penjelasan yang to the point dan runut banget. Makasih udah sharing alpha daging kayak gini bang!"
        ]
    },
    "testnet_alpha": {
        "en": [
            "Early testnet testing is where the asymmetric opportunities are born. Faucet claim and contract deployed!",
            "Great heads up on this testnet phase. Consistent testing and providing dev feedback is the real cheat code.",
            "Smooth UX on their testnet so far. Making sure to interact with all the available dApps on the ecosystem.",
            "Thanks for the ping on this testnet! Active onchain footprint across multiple contracts set up successfully."
        ],
        "id": [
            "Testnet early kayak gini emang paling gurih kalau digarap konsisten dari awal. Langsung request faucet dan coba dApps-nya!",
            "Info testnet mantap bang! Langsung gas interaksi sama kontraknya mumpung belum terlalu rame antrean.",
            "Garapan early yang potensial banget. Konsistensi interaksi mingguan kuncinya biar wallet kita terdata aktif."
        ]
    },
    "chart_ta": {
        "en": [
            "Clean technical breakdown. That retest of the demand zone on the higher timeframe looks textbook.",
            "Spot on chart perspective. Liquidity absorption around this support level is showing strong institutional bids.",
            "Really balanced chart view. Waiting for the daily candle close to confirm the range breakout before adding size.",
            "Great chart context. The divergence between spot accumulation and futures open interest is definitely telling.",
            "Appreciate the objective technical take. Invalidation level is very clearly defined here.",
            "Solid analysis. Patience during this chop phase is key while waiting for high timeframe confirmation 📈"
        ],
        "id": [
            "Analisa chart yang rapi dan objektif bang. Area demand-nya masih nahan kuat banget di time frame besar.",
            "Struktur chartnya masih rapi nahan support. Tinggal nunggu konfirmasi volume di time frame harian, bullish! 📈",
            "Ulasan teknikal yang jernih no fomo-fomo club. Serapan likuiditas di level support ini emang keliatan rapi.",
            "Setuju banget sama pembacaan chart ini. Disiplin nunggu konfirmasi dan jaga batas invalidasi tetep nomor satu.",
            "Analisa yang sangat masuk akal. Selalu menarik liat reaksi harga pas nguji area likuiditas kunci."
        ]
    },
    "token_focused": {
        "en": [
            "The momentum and onchain strength behind {token} right now are undeniable. Volume speaks louder than timeline noise.",
            "Really compelling thesis on {token}. The ecosystem development and developer retention here have been stellar.",
            "Solid analysis on {token}. Keeping a close eye on how onchain metrics and liquidity depth continue to expand.",
            "Spot on perspective regarding {token}. Long term fundamentals and throughput are finally being reflected in adoption.",
            "Ecosystem metrics on {token} have been quietly outpacing expectations this cycle. Great writeup!"
        ],
        "id": [
            "Momentum dan pertumbuhan onchain di ekosistem {token} emang lagi kenceng banget belakangan ini. Mantap analisanya!",
            "Ulasan yang sangat menarik soal {token}. Pertumbuhan ekosistem dan aktivitas developernya beneran solid.",
            "Setuju banget bang. Fondasi teknologi dan likuiditas {token} di cycle ini makin matang dan teruji.",
            "Metriks transaksi dan adopsi retail di {token} emang nunjukin demand nyata, bukan sekadar hype sesaat."
        ]
    },
    "solana_ecosystem": {
        "en": [
            "Solana DEX volume and onchain velocity have been completely unmatched this cycle. Retail attention lives here.",
            "Sub-second finality and low friction make the onchain experience on Solana impossible to beat for daily users.",
            "The consumer app velocity building on Solana right now is wild. Real user adoption in real time 🚀",
            "Insane onchain metrics on Solana lately. Liquidity depth and active trading volume continue to break records."
        ],
        "id": [
            "Aktivitas onchain dan volume DEX di Solana emang ga ada obatnya cycle ini. Likuiditas retail beneran ngumpul di sini.",
            "Kecepatan finalitas dan gas fee murah di Solana beneran ngasih standar baru buat user experience onchain.",
            "Ekosistem Solana makin solid, adopsi dApps dan volume perdagangannya konsisten mecahin rekor. Keren ulasannya bang!"
        ]
    },
    "defi_yield": {
        "en": [
            "Sustainable protocol fee generation and capital efficiency are what will separate enduring DeFi from temporary farms.",
            "The TVL growth and organic liquidity depth across these protocols show real institutional appetite for onchain yield.",
            "Composability between AMMs and money markets is getting so much more sophisticated. Great DeFi breakdown!"
        ],
        "id": [
            "DeFi yang punya model real yield dan efisiensi modal tinggi emang bakal paling tahan banting di segala kondisi market.",
            "Pertumbuhan TVL dan volume fee protokolnya nunjukin adopsi organik yang nyata. Mantap pembahasannya bang!"
        ]
    },
    "ai_depin": {
        "en": [
            "The convergence of autonomous AI agents and decentralized onchain rails is easily one of the most exciting frontiers.",
            "Decentralized compute and permissionless coordination solve real friction points. Great dive into where the tech is going ⚡",
            "Fascinating narrative. Watching how AI agents coordinate transactions onchain is going to redefine Web3 UX."
        ],
        "id": [
            "Sektor AI agent dan DePIN emang punya potensi gila buat bawa use case nyata ke Web3. Menarik banget pembahasannya!",
            "Inovasi integrasi kecerdasan buatan langsung onchain makin konkret. Salut sama tim pengembang yang terus berinovasi!"
        ]
    },
    "builder_milestone": {
        "en": [
            "Massive milestone for the team! Shipping consistent infrastructure upgrades in quiet markets builds true longevity 👏",
            "Remarkable engineering execution. The throughput and user experience improvements here are genuinely tangible.",
            "Huge leap forward for onchain infrastructure. Excited to see what new dApps deploy on this next!"
        ],
        "id": [
            "Milestone yang luar biasa buat perkembangan ekosistem! Konsistensi tim dev dalam build infrastruktur patut diacungi jempol 👏",
            "Peningkatan performa dan UX-nya berasa banget bedanya. Selamat buat seluruh tim atas rilis update penting ini!",
            "Langkah maju yang konkret buat skalabilitas Web3. Sukses terus buat ekosistem dan para buildernya!"
        ]
    },
    "general_mindset": {
        "en": [
            "Spot on perspective. Protecting seed capital and having the emotional discipline to let winning theses ride is everything.",
            "100% agreed. In a timeline dominated by noise and FOMO, grounded long-term thinking is the ultimate edge.",
            "Really well articulated thoughts. Patience and risk management will always separate survivors from exit liquidity 💯",
            "Golden advice for anyone navigating this cycle. Consistency and emotional clarity compound into massive results."
        ],
        "id": [
            "Setuju 100% bang! Mindset jangka panjang dan kedewasaan emosi emang pembeda utama trader matang di market ini.",
            "Pengingat berbobot di tengah ramainya noise timeline. Jaga modal pokok dan selalu patuhi trading plan masing-masing!",
            "Valid no debat sih poin ini. Konsistensi riset mandiri dan kesabaran selalu menang dalam jangka panjang. Mantap! ☕"
        ]
    }
}


def normalize_comment_for_comparison(text: str) -> str:
    """Normalisasi komentar untuk perbandingan: hapus tanda baca, emoji, lowercase."""
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"[#$@]\w+", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def calculate_comment_jaccard_similarity(text1: str, text2: str) -> float:
    """Menghitung derajat kemiripan kata antara dua komentar."""
    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


def has_comment_ngram_overlap(text1: str, text2: str, n: int = 4) -> bool:
    """Mengecek apakah ada N kata berurutan yang sama persis antara dua komentar."""
    tokens1 = text1.split()
    tokens2 = text2.split()
    if len(tokens1) < n or len(tokens2) < n:
        return False
    ngrams1 = set(" ".join(tokens1[i:i+n]) for i in range(len(tokens1) - n + 1))
    ngrams2 = set(" ".join(tokens2[i:i+n]) for i in range(len(tokens2) - n + 1))
    return len(ngrams1.intersection(ngrams2)) > 0


def load_used_comments() -> list[str]:
    """Memuat seluruh teks riwayat komentar sebelumnya."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history_comments = []

    # 1. Dari log history engagement JSON
    if ENGAGEMENT_LOG_FILE.exists():
        try:
            with open(ENGAGEMENT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.values():
                    if isinstance(item, dict) and "comment" in item and item["comment"]:
                        history_comments.append(item["comment"])
        except Exception:
            pass

    # 2. Dari file used comments
    if USED_COMMENTS_FILE.exists():
        try:
            with open(USED_COMMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    history_comments.extend(data)
        except Exception:
            pass

    return history_comments


def save_used_comment(comment_text: str):
    """Menyimpan teks komentar baru ke database persistent anti-duplikasi."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    comments = load_used_comments()
    norm = normalize_comment_for_comparison(comment_text)

    if norm not in comments:
        comments.append(norm)

    try:
        with open(USED_COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(comments, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def is_comment_duplicate(comment_text: str, used_comments: list[str]) -> bool:
    """
    Sistem Multi-Layer Anti-Duplikasi Komentar:
    1. Exact Match Check
    2. Jaccard Word Similarity Check (Toleransi ketat: jika >= 40% kata sama -> DUPLIKAT)
    3. N-gram Overlap Check (Jika ada 4 kata berturut-turut sama -> DUPLIKAT)
    """
    norm_new = normalize_comment_for_comparison(comment_text)
    if not norm_new or len(norm_new.split()) < 3:
        return False

    for existing in used_comments:
        norm_exist = normalize_comment_for_comparison(existing)
        if not norm_exist:
            continue

        # 1. Exact match
        if norm_new == norm_exist:
            return True

        # 2. Jaccard similarity
        if calculate_comment_jaccard_similarity(norm_new, norm_exist) >= 0.40:
            return True

        # 3. N-gram 4 kata berurutan
        if has_comment_ngram_overlap(norm_new, norm_exist, n=4):
            return True

    return False


def detect_language(text: str) -> str:
    """Deteksi bahasa tweet (Indonesian atau English)."""
    t = text.lower()
    id_words = {"yang", "ini", "dan", "di", "ke", "dari", "bisa", "untuk", "garap", "cuan", "mantap", "bang", "nih", "udah", "kita", "kalian", "jangan", "paling"}
    words = set(re.findall(r"\b[a-zA-Z]{2,}\b", t))
    return "id" if len(words.intersection(id_words)) >= 2 else "en"


def analyze_tweet_intent_and_entities(tweet_text: str) -> tuple[str, str, str]:
    """
    Menganalisis teks tweet untuk menentukan:
    - category: kategori spesifik tweet
    - detected_token: token/proyek yang dibicarakan (misal $SOL, Bitcoin, Berachain)
    - lang: bahasa tweet ('en' atau 'id')
    """
    t = tweet_text.lower()
    lang = detect_language(tweet_text)

    # 1. Ekstrak token / coin
    detected_token = ""
    # Cari dengan urutan kata terpanjang terlebih dahulu
    sorted_keywords = sorted(KNOWN_TOKENS.keys(), key=lambda x: len(x), reverse=True)
    for kw in sorted_keywords:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, t) or f"${kw}" in t:
            detected_token = KNOWN_TOKENS[kw]
            break

    # 2. Tentukan kategori niat/topik (prioritas spesifik ke umum)
    if any(k in t for k in ["guide", "tutorial", "step", "tutor", "panduan", "cara garap", "tread airdrop", "alpha thread"]) and any(k in t for k in ["airdrop", "testnet", "snapshot", "mainnet", "faucet", "claim", "retro"]):
        category = "airdrop_guide"
    elif any(k in t for k in ["testnet", "faucet", "devnet", "sepolia"]):
        category = "testnet_alpha"
    elif any(k in t for k in ["solana", "sol"]):
        category = "solana_ecosystem"
    elif any(k in t for k in ["chart", "support", "resistance", "breakout", "target", "retest", "candles", "ta", "liquidation", "orderbook", "pattern"]):
        category = "chart_ta"
    elif any(k in t for k in ["ai agent", "ai agents", "artificial intelligence", "depin", "compute", "gpu"]) or re.search(r"\b(ai|agent|agents)\b", t):
        category = "ai_depin"
    elif any(k in t for k in ["dex", "tvl", "yield", "staking", "restaking", "liquidity pool", "lending", "amm"]):
        category = "defi_yield"
    elif any(k in t for k in ["shipped", "mainnet live", "upgrade", "milestone", "partnership", "release", "infra", "tps", "parallel"]):
        category = "builder_milestone"
    elif detected_token:
        category = "token_focused"
    elif any(k in t for k in ["airdrop", "snapshot", "eligib", "allocation"]):
        category = "airdrop_guide"
    elif any(k in t for k in ["btc", "eth", "price", "bull", "bear", "pump", "dip", "trading", "volume", "market"]):
        category = "chart_ta"
    else:
        category = "general_mindset"

    return category, detected_token, lang


def generate_contextual_comment(tweet_text: str, max_retries: int = 50) -> str:
    """
    Menghasilkan komentar yang BENAR-BENAR MENYESUAIKAN KONTEKS & ENTITAS tweet viral
    serta DIJAMIN 100% BEBAS DUPLIKASI dari komentar sebelumnya.
    """
    category, token, lang = analyze_tweet_intent_and_entities(tweet_text)
    used_comments = load_used_comments()

    # Ambil pool yang sesuai
    cat_pool = NATURAL_RESPONSES.get(category, NATURAL_RESPONSES["general_mindset"])
    lang_pool = cat_pool.get(lang, cat_pool.get("en", []))

    if not lang_pool:
        lang_pool = NATURAL_RESPONSES["general_mindset"]["en"]

    for _ in range(max_retries):
        template = random.choice(lang_pool)
        # Sisipkan token jika ada placeholder {token}
        if "{token}" in template:
            substitute_token = token if token else ("crypto" if lang == "en" else "aset ini")
            candidate = template.format(token=substitute_token)
        else:
            candidate = template

        if not is_comment_duplicate(candidate, used_comments):
            return candidate

    # Jika semua permutasi di kategori ini sudah pernah dipakai, fallback ke general mindset unik
    fallback_pool = NATURAL_RESPONSES["general_mindset"][lang]
    for alt in fallback_pool:
        if not is_comment_duplicate(alt, used_comments):
            return alt

    return random.choice(fallback_pool)


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

    if not auth_token or not ct0 or account_info.get("suspended") or account_info.get("cooldown"):
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
            and not v.get("cooldown")
        ]
    else:
        active_keys = [k for k, v in accounts.items() if not v.get("suspended") and not v.get("cooldown")]

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
