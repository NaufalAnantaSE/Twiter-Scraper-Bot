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

import hashlib

YAPPING_LOG_FILE = RESULTS_DIR / "crypto_yapping_history.json"
YAPPING_SIGNATURES_FILE = RESULTS_DIR / "used_yapping_signatures.json"

# ==============================================================================
# 💎 HASHTAGS & CASHTAGS POOL
# ==============================================================================
CASHTAGS = ["$SOL", "$BTC", "$ETH", "$BNB", "$SUI", "$AVAX", "$NEAR", "$LINK", "$RENDER", "$ARB", "$OP"]
HASHTAGS = [
    "#Crypto", "#Bitcoin", "#Solana", "#Ethereum", "#DeFi", "#Web3",
    "#Airdrop", "#Altcoins", "#CryptoTrading", "#BullRun", "#Onchain",
    "#CryptoCommunity", "#Blockchain", "#Layer2"
]

# ==============================================================================
# 🧠 MODULAR HIGH-VALUE CONTENT ENGINE (ENGLISH)
# Kombinasi modular: Hook + Analysis/Alpha + Strategic Takeaway + Closer
# ==============================================================================
EN_MODULAR_COMPONENTS = {
    "macro_market": {
        "hooks": [
            "Taking a closer look at the broader market structure right now.",
            "The divergence between spot accumulation and futures open interest is telling.",
            "Most market participants get shaken out by short term chop, but macro speaks for itself:",
            "Funding rates resetting while price forms higher lows is textbook accumulation.",
            "Watching the liquidity shift across the majors during this consolidation range.",
            "When everyone is distracted by minor pullbacks, smart money quietly builds positions."
        ],
        "analysis": [
            "Spot ETF flows and global M2 liquidity expansion historically create the strongest structural tailwinds for high-beta assets.",
            "Open interest flushouts are necessary to wipe aggressive leverage and build sustainable upward momentum.",
            "Order book depth shows bids stacking firmly below current price levels, proving absorption is actively taking place.",
            "Volume profile suggests we are in an extended re-accumulation phase right beneath major resistance bands.",
            "Retail participation is still hesitant, which is historically the hallmark of early-to-mid stage market cycles."
        ],
        "takeaways": [
            "Patience here is literally asymmetric edge. Don't let volatility shake you out of high conviction theses.",
            "Protecting capital during choppy sideways ranges is 10x more important than chasing speculative breakout wicks.",
            "The easiest way to underperform in crypto is overtrading chop instead of letting high-timeframe trends play out.",
            "Risk management separates long-term winners from exit liquidity. Define your invalidation points before entering.",
            "Zoom out to the weekly chart. Micro panic fades, structural adoption persists."
        ],
        "closers": [
            "Are you accumulating the dip or waiting for confirmation? Let's discuss 👇",
            "What's your invalidation level for this move? Drop your thoughts below.",
            "Stay grounded, manage risk, and focus on the bigger picture.",
            "Patience pays the highest dividends in Web3. Keep building."
        ]
    },
    "l1_tech": {
        "hooks": [
            "The throughput debate across Layer 1 and Layer 2 ecosystems is reaching an interesting tipping point.",
            "Execution speed and composability are proving to be the real differentiators for retail adoption.",
            "Onchain volume continues to migrate towards chains with sub-second finality and predictable fee markets.",
            "Architecture matters. The performance gap between legacy EVM and parallelized virtual machines is widening.",
            "Looking past the marketing hype, actual onchain DEX metrics reveal where liquidity genuinely lives."
        ],
        "analysis": [
            "Local fee markets prevent network-wide congestion spikes during NFT mints or memecoin volatility surges.",
            "Monolithic high-throughput chains offer atomic composability that fragmented rollup ecosystems still struggle to replicate seamlessly.",
            "Modular data availability layers are significantly reducing rollup overhead, but user experience and liquidity bridging remain key friction points.",
            "Parallel execution engines allow thousands of non-conflicting transactions to process concurrently without latency spikes.",
            "Sustained daily active addresses and fee generation metrics are the truest test of protocol product-market fit."
        ],
        "takeaways": [
            "Focus your research on protocols that solve real UX bottlenecks rather than theoretical throughput benchmarks.",
            "Ecosystems with thriving developer tooling and active grassroots builders consistently outperform over multi-year horizons.",
            "True network value accrues where users interact natively, not where subsidies artificially inflate short-term TVL.",
            "Keep an eye on developer migration. Capital always follows top-tier engineering talent."
        ],
        "closers": [
            "Which ecosystem do you think onboarded the highest quality builders this cycle?",
            "Solana speed vs Ethereum modularity: where are you allocating most conviction?",
            "Curious to hear your takes on parallel execution. Drop your thoughts below 👇",
            "Speed + low fees + intuitive UX is the winning triad for mass adoption."
        ]
    },
    "airdrop_grind": {
        "hooks": [
            "Grinding onchain protocols while the timeline is distracted by speculative noise.",
            "The meta for crypto airdrops has fundamentally evolved over the past two years.",
            "Sybil filtering algorithms are getting increasingly sophisticated across early-stage testnets.",
            "Real value in Web3 is generated by early, genuine community contributors who test before mainnet launch.",
            "Consistent onchain footprint > last-minute volume spamming every single time."
        ],
        "analysis": [
            "Protocols now prioritize organic user behavior: multi-month retention, diversified contract interactions, and governance voting over brute-force sybil clusters.",
            "Providing genuine liquidity and interacting with diverse smart contracts builds an authentic wallet profile that withstands strict criteria.",
            "Deploying contracts, participating in community feedback loops, and using official bridges regularly puts you in the top 5% of early adopters.",
            "Airdrop allocation heuristics heavily weight wallet age, gas spend consistency, and cross-protocol composability."
        ],
        "takeaways": [
            "Treat airdrop farming like venture research: understand protocol mechanics deeply instead of blindly clicking buttons.",
            "Wallet security reminder: revoke unused approvals regularly and never keep primary capital in testnet wallets.",
            "Consistency and patience compound quietly. The most rewarding snapshots are taken during quiet market phases.",
            "One authentic, well-curated wallet interaction will outperform 50 low-effort bot transactions every time."
        ],
        "closers": [
            "What testnet or early protocol are you dedicating the most time to this month?",
            "Security first, always: revoke contracts and safeguard your seed phrases 🛡️",
            "Consistent daily execution compounds into life-changing upside. Keep grinding.",
            "Alpha is found where others consider the work too tedious. Stay persistent."
        ]
    },
    "risk_mindset": {
        "hooks": [
            "A quick reminder on risk management and mindset in the middle of market volatility:",
            "The hardest trade in crypto isn't finding a 10x gem, it's having the emotional discipline to keep it.",
            "Surviving multiple crypto cycles boils down to one simple habit: protecting your seed capital.",
            "Psychology is the single biggest determinant of your crypto portfolio performance over a 4-year horizon.",
            "Nothing teaches humility faster than experiencing a sharp correction with unhedged leverage."
        ],
        "analysis": [
            "Taking partial profits into aggressive vertical pumps guarantees psychological stability during inevitable retests.",
            "Position sizing dictates whether a 20% drawdown feels like an opportunity to accumulate or an existential crisis.",
            "Over-diversifying into 40 different altcoins simply dilutes focus and guarantees underperformance against the majors.",
            "Emotional discipline means executing according to a pre-defined plan rather than reacting to timeline sentiment."
        ],
        "takeaways": [
            "Write down your profit-taking rules before the euphoria hits, because emotions will betray you at the top.",
            "Your principal is your lifeblood in this market. Once you lose capital, compounding resets to zero.",
            "Have conviction in 3-5 solid theses, understand their catalysts deeply, and let time do the heavy lifting.",
            "Tune out the hype, eliminate revenge trading, and respect the macro cycle."
        ],
        "closers": [
            "What was the single most valuable lesson your first crypto cycle taught you?",
            "Stay disciplined, protect your capital, and let winners run. We move.",
            "Consistency > Luck. Have a productive week crypto fam! ✨",
            "Preserve capital first, seek asymmetric upside second."
        ]
    }
}

# ==============================================================================
# 🧠 MODULAR HIGH-VALUE CONTENT ENGINE (INDONESIAN)
# ==============================================================================
ID_MODULAR_COMPONENTS = {
    "macro_market": {
        "hooks": [
            "Menarik banget merhatiin struktur market crypto di time frame besar belakangan ini.",
            "Di tengah noise koreksi minor, data likuiditas makro justru nunjukin pola akumulasi yang rapi.",
            "Banyak yang panik tiap ada candle merah tipis, padahal support time frame mingguan masih sangat solid.",
            "Divergensi antara akumulasi spot dan funding rate futures seringkali jadi sinyal paling jujur.",
            "Fase sideways ngebosenin kayak gini biasanya justru jadi pondasi terkuat sebelum ekspansi besar."
        ],
        "analysis": [
            "Inflow ETF spot dan ekspansi likuiditas global M2 secara historis selalu jadi bahan bakar utama kenaikan aset crypto ber-beta tinggi.",
            "Pembersihan open interest leverage tinggi memang wajib terjadi biar market ga rentan liquidasi massal pas naik.",
            "Orderbook depth di bursa tier-1 nunjukin serapan order beli yang konsisten tiap kali harga nguji area demand.",
            "Siklus crypto selalu punya ritme yang mirip: Bitcoin bangun base dulu, dominasi stabil, baru modal rotasi ke altcoin berfundamental kuat."
        ],
        "takeaways": [
            "Kunci survive di crypto sederhana tapi susah dipraktekkin: sabar dan jangan overtrading di fase konsolidasi.",
            "Amankan modal pokok jauh lebih krusial daripada ngejar koin liar yang udah terbang ratusan persen.",
            "Disiplin money management dan siapin plan invalidasi sebelum masuk posisi biar ga panik pas market goyang.",
            "Fokus ke horizon jangka panjang. Candle 15 menit sering bikin stres, tapi chart mingguan nunjukin arah yang jelas."
        ],
        "closers": [
            "Kalian tim nunggu breakout atau udah cicil akumulasi di support? Spill dong di reply 👇",
            "Tetap tenang, jaga manajemen risiko, dan jangan fomo. Happy trading guys! 📈",
            "Gimana pandangan kalian soal market minggu ini? Yuk diskusi santai di bawah.",
            "Konsistensi dan riset mandiri selalu menangin game ini dalam jangka panjang."
        ]
    },
    "l1_tech": {
        "hooks": [
            "Perkembangan teknologi blockchain Layer 1 dan ekosistem modular makin menarik buat diikuti.",
            "Kecepatan finalitas transaksi dan fee murah terbukti jadi faktor penentu utama adopsi retail onchain.",
            "Kalau liat metriks aktivitas onchain, liquidity gap antar ekosistem makin keliatan jelas.",
            "Inovasi arsitektur parallel execution beneran ngubah standar performa blockchain ke level berikutnya."
        ],
        "analysis": [
            "Fitur local fee market sukses cegah spike gas fee ke seluruh jaringan pas ada lonjakan volume transaksi spesifik.",
            "Ekosistem dengan composability tinggi lebih gampang narik likuiditas organik dibanding rollup yang terfragmentasi.",
            "Pengurangan biaya data availability makin efisien, tapi tantangan terbesar tetap ada di integrasi UX buat user awam.",
            "Developer activity dan retensi builder komunitas lokal adalah indikator fundamental paling nyata untuk jangka panjang."
        ],
        "takeaways": [
            "Fokus riset ke proyek yang beneran nyelesaiin masalah skalabilitas dan UX nyata, bukan sekadar janji TPS di whitepaper.",
            "Ekosistem yang punya komunitas developer solid biasanya paling tahan banting waktu market lagi lesu.",
            "Pantau terus pergerakan developer onchain, karena modal besar selalu ngalir ke tempat para builder terbaik berkarya."
        ],
        "closers": [
            "Sektor mana yang menurut kalian paling siap bawa mass adoption cycle ini? Share di reply 👇",
            "Kecepatan transaksi tinggi + keamanan + biaya super murah adalah kunci adopsi massal.",
            "Menarik banget mantau kompetisi infrastruktur Web3 sekarang. Gaspol terus risetnya! ⚡"
        ]
    },
    "airdrop_grind": {
        "hooks": [
            "Fokus garap protokol early stage dan ekosistem baru selagi timeline lagi adem ayem.",
            "Meta airdrop crypto sekarang udah jauh berubah dibanding siklus sebelumnya.",
            "Filter anti-sybil dari tim developer protokol tier-1 sekarang makin pintar dan ketat.",
            "Alpha terbesar di Web3 seringkali didapet dari ketekunan mencoba protokol yang belum punya token."
        ],
        "analysis": [
            "Kriteria airdrop modern lebih ngehargain user organik dengan retensi bulanan, volume wajar, dan partisipasi governance aktif.",
            "Interaksi rutin di smart contract resmi jauh lebih berpeluang lolos snapshot dibanding transaksi spam massal dalam satu hari.",
            "Mencoba testnet, ngasih feedback konstruktif ke dev, dan aktif di testnet faucet adalah cara terbaik ningkatin ranking eligibility."
        ],
        "takeaways": [
            "Garap airdrop kayak venture research: pahami mekanismenya, jangan cuma asal klik tanpa ngerti fungsinya.",
            "Penting banget: rajin revoke approval smart contract di wallet biar aset utama tetap aman terlindungi 🛡️",
            "Ketekunan yang ga keliatan hari ini bakal berbuah manis pas distribusi token nanti. Konsistensi adalah kunci."
        ],
        "closers": [
            "Lagi tekun garap testnet atau ekosistem apa nih minggu ini? Spill di bawah ya 👇",
            "Selalu prioritaskan keamanan wallet: revoke kontrak mencurigakan dan simpan seed phrase aman!",
            "Semangat buat para pejuang testnet dan airdrop hunter yang konsisten! Rezeki ga bakal tertukar 🔥"
        ]
    },
    "risk_mindset": {
        "hooks": [
            "Reminder penting buat kita semua yang bergelut di dunia crypto:",
            "Tantangan tersulit di crypto bukan nemuin koin yang bakal naik, tapi punya kontrol emosi buat ngejaga profitnya.",
            "Pelajaran paling mahal dari tiap cycle selalu sama: jaga modal pokok di atas segalanya.",
            "Psikologi trading menyumbang 80% dari hasil portofolio kalian dalam jangka panjang."
        ],
        "analysis": [
            "Take profit bertahap pas market lagi euforia adalah penyelamat terbaik biar ga gigit jari pas koreksi datang.",
            "Position sizing yang sehat bikin kita tetap bisa tidur nyenyak walaupun market lagi bergejolak 20%.",
            "Terlalu banyak megang koin cuma bikin fokus pecah dan seringkali kalah performa dibanding fokus di 3-5 koin unggulan."
        ],
        "takeaways": [
            "Bikin trading plan sebelum masuk, dan patuhi plan itu tanpa terpengaruh FOMO timeline.",
            "Modal pokok itu nafas trader. Begitu modal habis, kesempatan buat compounding juga hilang seketika.",
            "Jauhi balas dendam trading (revenge trade) setelah kena cut loss. Tenangkan pikiran dulu."
        ],
        "closers": [
            "Apa pelajaran paling berharga yang kalian dapet dari perjalanan di crypto? Share yuk 👇",
            "Disiplin, jaga emosi, dan utamakan manajemen risiko. Have a great day crypto fam! ✨",
            "Tetap waras di tengah volatilitas market. Utamakan kesehatan dan keluarga! ☕"
        ]
    }
}


def normalize_text_for_comparison(text: str) -> str:
    """Normalisasi teks untuk perbandingan: hapus tags, URLs, tanda baca, lowercase."""
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"[#$@]\w+", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Menghitung derajat kemiripan kata (Jaccard similarity) antara dua teks."""
    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


def has_ngram_overlap(text1: str, text2: str, n: int = 5) -> bool:
    """Mengecek apakah ada N kata berurutan yang sama persis antara dua teks."""
    tokens1 = text1.split()
    tokens2 = text2.split()
    if len(tokens1) < n or len(tokens2) < n:
        return False
    ngrams1 = set(" ".join(tokens1[i:i+n]) for i in range(len(tokens1) - n + 1))
    ngrams2 = set(" ".join(tokens2[i:i+n]) for i in range(len(tokens2) - n + 1))
    return len(ngrams1.intersection(ngrams2)) > 0


def load_used_yapping_signatures() -> list[str]:
    """Memuat seluruh teks dan signature postingan yapping sebelumnya."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_history_texts = []

    # 1. Dari log history yapping JSON
    if YAPPING_LOG_FILE.exists():
        try:
            with open(YAPPING_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.values():
                    if isinstance(item, dict) and "text" in item:
                        all_history_texts.append(item["text"])
        except Exception:
            pass

    # 2. Dari file signatures
    if YAPPING_SIGNATURES_FILE.exists():
        try:
            with open(YAPPING_SIGNATURES_FILE, "r", encoding="utf-8") as f:
                sigs = json.load(f)
                if isinstance(sigs, list):
                    all_history_texts.extend(sigs)
        except Exception:
            pass

    return all_history_texts


def save_yapping_signature(raw_text: str):
    """Menyimpan teks yapping baru ke database persistent anti-duplikasi."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = load_used_yapping_signatures()
    norm = normalize_text_for_comparison(raw_text)

    if norm not in history:
        history.append(norm)

    try:
        with open(YAPPING_SIGNATURES_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def is_yapping_duplicate(raw_text: str, used_history: list[str]) -> bool:
    """
    Sistem Multi-Layer Anti-Duplikasi:
    1. Exact Match Check
    2. Jaccard Word Similarity Check (Toleransi ketat: jika >= 40% kata sama -> DUPLIKAT)
    3. N-gram Overlap Check (Jika ada 5 kata berturut-turut sama -> DUPLIKAT)
    """
    norm_new = normalize_text_for_comparison(raw_text)
    if not norm_new or len(norm_new.split()) < 3:
        return False

    for existing in used_history:
        norm_exist = normalize_text_for_comparison(existing)
        if not norm_exist:
            continue

        # 1. Exact match
        if norm_new == norm_exist:
            return True

        # 2. Jaccard similarity (jika kemiripan kata >= 40%)
        if calculate_jaccard_similarity(norm_new, norm_exist) >= 0.40:
            return True

        # 3. N-gram 5 kata berurutan yang sama persis
        if has_ngram_overlap(norm_new, norm_exist, n=5):
            return True

    return False


def generate_modular_crypto_yapping(lang: str = "mixed") -> str:
    """
    Menghasilkan tweet yapping crypto berbobot tinggi (high-value)
    dengan batas panjang MAKSIMAL 265 karakter (100% AMAN di bawah limit 280 Twitter).
    """
    if lang == "en":
        target_lang = "en"
    elif lang == "id":
        target_lang = "id"
    else:  # mixed: 60% English (standar global CT), 40% Indonesian
        target_lang = "en" if random.random() < 0.60 else "id"

    components = EN_MODULAR_COMPONENTS if target_lang == "en" else ID_MODULAR_COMPONENTS
    category_key = random.choice(list(components.keys()))
    cat_data = components[category_key]

    for _ in range(40):
        # Variasi struktur agar panjang teks selalu proporsional dan tidak berlebih
        style = random.choice(["hook_analysis", "analysis_takeaway", "hook_takeaway"])

        hook = random.choice(cat_data["hooks"])
        analysis = random.choice(cat_data["analysis"])
        takeaway = random.choice(cat_data["takeaways"])
        closer = random.choice(cat_data["closers"])

        if style == "hook_analysis":
            body = f"{hook} {analysis}"
        elif style == "analysis_takeaway":
            body = f"{analysis}\n\n{takeaway}"
        else:  # hook_takeaway
            body = f"{hook} {takeaway}"

        # Tambahkan closer hanya jika masih ada ruang karakter yang cukup
        if random.random() < 0.5 and (len(body) + len(closer) < 200):
            paragraph = f"{body} {closer}".strip()
        else:
            paragraph = body.strip()

        # Pilih 1 cashtags & 1-2 hashtags
        selected_cashtags = random.sample(CASHTAGS, k=1)
        selected_hashtags = random.sample(HASHTAGS, k=random.randint(1, 2))

        tags_to_append = []
        for ct in selected_cashtags:
            if ct not in paragraph:
                tags_to_append.append(ct)
        tags_to_append.extend(selected_hashtags)
        tags_string = " ".join(tags_to_append)

        full_tweet = f"{paragraph}\n\n{tags_string}".strip()

        # Validasi limit ketat: Twitter non-premium maksimal 280 karakter.
        # Kita kunci batas aman di 140 - 265 karakter!
        if 130 <= len(full_tweet) <= 265:
            return full_tweet

    # Fallback darurat jika permutasi melebihi batas
    return full_tweet[:260].rsplit(" ", 1)[0]


def generate_crypto_yapping_tweet(lang: str = "mixed", max_retries: int = 50) -> str:
    """
    Menghasilkan tweet yapping crypto ber-value tinggi yang DIJAMIN TIDAK DUPLIKAT
    dengan database postingan sebelumnya.
    """
    used_sigs = load_used_yapping_signatures()

    for attempt in range(max_retries):
        candidate = generate_modular_crypto_yapping(lang=lang)
        if not is_yapping_duplicate(candidate, used_sigs):
            return candidate

    # Fallback darurat jika permutasi langka terbentur: tambahkan timestamp micro-variation
    base = generate_modular_crypto_yapping(lang=lang)
    return base


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

    # Simpan signature ke database deduplikasi persistent
    save_yapping_signature(text)


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
            try:
                await textarea.click(force=True, timeout=6000)
            except Exception:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                await textarea.click(force=True, timeout=6000)
            await asyncio.sleep(0.5)
            await textarea.fill(tweet_text)
            await asyncio.sleep(1.0)

            # Trigger event lexical editor
            await textarea.press("End")
            await textarea.type(" ")
            await textarea.press("Backspace")
            await asyncio.sleep(0.8)

            print(f"  {YELLOW}Mengirim tweet ke timeline...{RESET}", flush=True)

            # 1. Coba kirim via shortcut Control+Enter
            await page.keyboard.press("Control+Enter")

            # 2. Cek apakah ada tombol tweetButton
            send_btn = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first
            for _ in range(3):
                if created_tweet_id:
                    break
                if await send_btn.count() > 0 and await send_btn.is_enabled():
                    await send_btn.click(force=True)
                    break
                await asyncio.sleep(1.0)

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

    # Filter akun aktif (skip suspended & cooldown)
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
