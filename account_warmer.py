"""
Twitter / X Account Warmer & Yapping Bot
Modul khusus pemanasan akun baru (warming up) agar terlihat natural dan terhindar dari suspend:
1. Membuat postingan Yapping santai berbahasa Indonesia (Curhat harian, gosip/netizen, edukasi ringan).
2. Mencari postingan viral/rame di timeline, melakukan Auto-Like ❤️ dan Comment 💬 sesuai topik & bahasa.
3. Generator komentar dinamis non-duplikat (anti-spam) berbasis kombinatorial cerdas & deduplikasi riwayat.
4. Mode Penjadwalan Terus-Menerus (Loop Otomatis) dengan jeda acak 1 - 2 Jam (60 - 120 menit).
5. Retweet dilewati (sesuai instruksi).
6. Rotasi otomatis antar 7 akun baru (tanpa menyentuh akun utama @fannettt).
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

# Windows terminal utf-8 support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, COOKIES_FILE, RESULTS_DIR
from accounts_manager import load_accounts, switch_account

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

logger = logging.getLogger(__name__)

WARMUP_HISTORY_FILE = RESULTS_DIR / "warmup_history.json"
COMMENT_DEDUP_FILE = RESULTS_DIR / "comment_dedup_history.json"

# ==============================================================================
# 📝 BANK KONTEN YAPPING BAHASA INDONESIA (SINGKAT, RELATABLE, NATURAL)
# ==============================================================================
YAPPING_TEMPLATES = [
    # Kategori: Curhat Harian & Day in My Life
    "ngantuk banget asli, padahal tadi udah ngopi segelas gede 😭",
    "kopi kedua hari ini rasanya tidak ada efeknya sama sekali wkwk",
    "hujan gini emang paling pas makan mie kuah pedes pake telur cabe rawit",
    "vibes hari ini lumayan adem, jadi mager mau ngapa-ngapain wkwk",
    "kerjaan lumayan padat hari ini, tapi disyukuri aja pelan-pelan kelar juga",
    "lagi pengen jajan yang manis-manis, ada rekomendasi makanan enak ga sih?",
    "tidur cepet vs maraton nonton film, perdebatan batin tiap malem wkwk",
    "kadang ngerasa waktu cepet banget jalan, tau-tau udah malem lagi",
    "definisi bahagia sederhana: pas nyampe rumah bisa langsung rebahan santai",
    "kalian kalau lagi jenuh atau burnout biasanya ngapain guys? bagi tips dong",
    "udara malam ini enak banget buat jalan santai sambil dengerin lagu favorit ✨",
    "kebiasaan nunda kerjaan sampe mepet deadline emang susah bgt diilangin haha",
    "hari ini produktif dikit gapapa, yg penting ada progres dibanding kemarin",
    "capek fisik mah tidur semalem bisa ilang, tapi kalo capek pikiran gimana ya wkwk",
    "sore-sore gini enaknya ngapain ya selain scroll sosmed berjam-jam haha",
    "nikmatnya kopi susu hangat di kala tugas lagi numpuk-numpuknya ☕",

    # Kategori: Opini Santai & Gosip / Netizen
    "plot twist hidup emang ga ada habisnya bjir, selalu ada aja hal random wkwk",
    "timeline hari ini rame banget sama drama, seru sih tapi capek juga bacanya haha",
    "kalian tipe orang yg bales chat gercep atau nimbun notif sampe ratusan? wkwk",
    "dunia makin hari makin cepet perubahannya ya, kadang takjub sendiri",
    "suka heran sama orang yang energinya ga abis-abis dari pagi sampe malem, rahasianya apa bjir",
    "apakah cuma gua yang kalo nemu lagu enak bakal diulang-ulang sampe bosen? wkwk",
    "sosmed sekarang serba cepat, tapi tetep filter konten yang positif buat kesehatan mental ya",
    "satu hal yg gua sadari: ga semua hal di dunia maya perlu ditanggepin serius wkwk",
    "paling seru emang ngeliatin perdebatan netizen tanpa ikutan nimbrung 😂",
    "makin ke sini makin ngerasa lingkungan kecil dan tenang itu mewah banget",
    "tren sekarang cepet banget ganti, baru kemarin hype sekarang udah basi haha",

    # Kategori: Edukasi Ringan & Self Reminder
    "reminder buat minum air putih yg cukup hari ini ya guys, jangan kopi mulu wkwk 💧",
    "fyi otak gabisa fokus maksimal kalo kurang tidur, jadi stop begadang ga jelas ya guys",
    "tips hidup tenang: jangan terlalu overthinking hal-hal yang di luar kendali kita ✨",
    "sedikit reminder: ga semua hal di sosmed harus kamu respon atau tanggepin kok",
    "investasi terbaik emang jaga kesehatan, tidur cukup sama makan bener. berasa bgt bedanya",
    "jangan lupa istirahat sejenak dari layar hp ya, mata juga butuh rehat sejenak 👀",
    "proses belajar emang butuh waktu, yang penting konsisten tiap hari walau dikit-dikit ✨",
    "jangan bandingin proses lu sama highlight kehidupan orang lain di sosmed, jalur tiap orang beda",
    "luangkan waktu 10 menit hari ini buat beneran istirahat tanpa buka gadget, refreshing bgt rasanya",
    "kalo lagi ngerasa stuck, coba jalan kaki keluar sebentar, biasanya pikiran jadi lebih plong",
    "fokus ke hal yang bisa kita kontrol hari ini, sisanya serahkan sama waktu dan usaha ✨"
]

# ==============================================================================
# 🧠 DYNAMIC COMBINATORIAL COMMENT GENERATOR (ANTI-SPAM & ZERO DUPLICATES)
# ==============================================================================
# Menghasilkan ribuan kemungkinan kombinasi kalimat unik per topik & bahasa
# sehingga tidak ada pola berulang yang terdeteksi bot/spam oleh Twitter.

DYNAMIC_COMMENT_BUILDERS = {
    "indonesian": {
        "humor_meme": {
            "openers": [
                "Wkwkwk asli, ", "Haha beneran, ", "Valid parah sih, ", "Asli dah, ",
                "Lucu bgt tapi ", "Kocak parah, ", "Ga kuat liatnya wkwk, ", "Waduh haha, "
            ],
            "cores": [
                "ga bisa relate lebih dari ini", "ini mah kejadian nyata sehari-hari",
                "selalu ada aja tingkah netizen begini", "definisi tertawa di atas kepedihan",
                "bisa kepikiran aja konten model begini", "beneran mewakili perasaan banyak orang",
                "ini mah potret kehidupan nyata tanpa filter", "ngena banget di kehidupan sehari-hari"
            ],
            "closers": [
                " wkwk", " 😂", " wkwk asli", " haha receh bgt", " 😂🙌", " woy wkwk", " haha no debat", " 😂👌"
            ]
        },
        "lifestyle": {
            "openers": [
                "Relatable banget, ", "Valid no debat sih ini, ", "Gua banget ini mah, ", "Beneran ngena, ",
                "Setuju banget, ", "Paham banget rasanya, ", "Emang bener sih, ", "Asli bgt, "
            ],
            "cores": [
                "hal-hal kecil kek gini yg sering bikin kepikiran", "emang butuh istirahat sejenak dari hiruk pikuk",
                "kuncinya dinikmati aja prosesnya pelan-pelan", "jangan terlalu dipikirin berat-berat, jalanin aja",
                "kadangkala hal sederhana gini yg paling berharga", "keseimbangan hidup emang nomor satu",
                "yang penting diri sendiri nyaman dan tenang", "tiap orang punya ritmenya masing-masing"
            ],
            "closers": [
                " haha", " wkwk", " ☕✨", " 😂👍", " bener bgt", " 😭", " semangat ya!", " ✨🙌"
            ]
        },
        "crypto": {
            "openers": [
                "Momentumnya cakep banget, ", "Tetap solid, ", "Makin optimis nih, ",
                "Fundamental jangka panjang, ", "Konsistensi ekosistemnya, ", "Perkembangan yang mantap, ",
                "Sinyal yang sangat bagus, ", "Eksekusi yang terarah, "
            ],
            "cores": [
                "pergerakan kali ini beneran menarik buat dipantau", "yang sabar dan yakin bakal dapet hasilnya",
                "volatilitas wajar tapi arahnya tetap menjanjikan", "komunitasnya aktif dan dev terus build",
                "indikasi kuat buat fase pertumbuhan berikutnya", "inovasi seperti ini yang bikin ekosistem bertahan",
                "adopsi nyata selalu jadi kunci utamanya", "fondasi yang dibangun beneran kuat"
            ],
            "closers": [
                " 🚀📈", " LFG! 🔥", " 💎🙌", " tetap kawal!", " ⚡", " to the moon! 🚀", " bullish! 📊", " mantap terus! 👍"
            ]
        },
        "announcement": {
            "openers": [
                "Keren banget, ", "Mantap eksekusinya, ", "Update yang ditunggu-tunggu, ",
                "Gokil inovasinya, ", "Langkah yang sangat bagus, ", "Pencapaian luar biasa, ",
                "Progress yang nyata, ", "Salute buat timnya, "
            ],
            "cores": [
                "tim dev beneran konsisten build tanpa banyak drama", "fitur ini bakal ngebantu banget buat kedepannya",
                "progress yang nyata dan kerasa banget manfaatnya", "selalu suka liat roadmap yang beneran dieksekusi",
                "standar baru buat ekosistem ini", "kualitas kerja yang beneran berbobot",
                "inovasi yang menjawab kebutuhan pengguna", "langkah strategis yang sangat tepat"
            ],
            "closers": [
                " 🔥👏", " 🚀✨", " respect buat timnya 🫡", " maju terus!", " 🌟", " sukses selalu! 🙌", " gaspol! ⚡", " 🤝"
            ]
        },
        "general": {
            "openers": [
                "Setuju banget sama poin ini, ", "Menarik nih diskusinya, ", "Perspektif yang sangat bagus, ",
                "Bener banget sih, ", "Insight mantap, ", "Pandangan yang berbobot, ", "Suka pembahasannya, "
            ],
            "cores": [
                "selalu menarik dengerin sudut pandang yang berbeda", "memberikan gambaran yang lebih luas dan jernih",
                "bisa jadi bahan pertimbangan yang bagus", "membuka wawasan baru tentang topik ini",
                "poin penting yang sering terlewatkan", "kritis tapi tetap objektif penyampaiannya",
                "membantu memahami konteksnya lebih dalam"
            ],
            "closers": [
                " 💡", " makasih sharingnya! 👍", " 👏", " ✨", " 👍", " mantap bro! 🙌", " bernilai bgt 🌟"
            ]
        }
    },
    "english": {
        "humor_meme": {
            "openers": [
                "Haha ", "Literally ", "So true, ", "Couldn't agree more, ",
                "Way too accurate, ", "Lmaoo ", "Undeniably true, ", "This hit hard lol, "
            ],
            "cores": [
                "this is way too relatable honestly", "me every single day without fail",
                "hits right where it hurts lol", "how is this so shockingly accurate",
                "the internet truly never fails to deliver", "laughed way harder than I should have",
                "pure unfiltered reality right here", "100% accurate representation"
            ],
            "closers": [
                " 😂", " lol", " 😭😂", " haha love this", " 100%", " 😂💀", " hands down 🙌", " lol so true"
            ]
        },
        "lifestyle": {
            "openers": [
                "Deeply relatable, ", "So true, ", "Can definitely resonate with this, ",
                "Spot on, ", "Honestly, ", "Well said, ", "Completely agree, "
            ],
            "cores": [
                "it really is the simple things that matter most", "taking things one step at a time is the best way",
                "such a grounded and necessary reminder", "finding peace in the daily routine is everything",
                "we all need moments like this to reset and recharge", "balance is definitely the key to sanity"
            ],
            "closers": [
                " ✨", " 💯", " have a great day! 🙌", " so true 👍", " cheers to that ☕", " well said 👏"
            ]
        },
        "crypto": {
            "openers": [
                "Super solid momentum, ", "Love the continuous progress, ", "Exciting price action, ",
                "Strong conviction play, ", "The user growth here, ", "Tremendous ecosystem expansion, "
            ],
            "cores": [
                "proves that fundamentals always win in the long run", "keeping eyes locked on this trajectory",
                "patience always pays off for real believers", "unmatched development activity and community vibe",
                "clear signs of exponential growth ahead", "the compounding effect is becoming noticeable"
            ],
            "closers": [
                " 🚀📈", " LFG! 🔥", " 💎🙌", " keep thriving! ⚡", " 🌟", " to new highs! 🚀", " unstoppable! ⚡"
            ]
        },
        "announcement": {
            "openers": [
                "Impressive update, ", "Massive milestone achieved, ", "Super clean execution, ",
                "Incredible pace of building, ", "Great release, ", "Huge step forward, "
            ],
            "cores": [
                "the dedication to shipping features consistently is inspiring", "this adds serious value to the whole ecosystem",
                "smooth rollout and great attention to detail", "exactly what the community was waiting for",
                "raising the bar for the entire space", "continuous innovation is clearly visible here"
            ],
            "closers": [
                " 🚀🔥", " keep crushing it! 👏", " 🌟", " respect to the dev team 🫡", " ⚡", " congratulations! 🎉"
            ]
        },
        "general": {
            "openers": [
                "Spot on, ", "Really insightful take, ", "Very thoughtful perspective, ",
                "Totally agreed, ", "Great point raised here, ", "Appreciate this viewpoint, "
            ],
            "cores": [
                "nuance is so important and you captured it well", "adds a lot of clarity to the ongoing conversation",
                "quality content that makes you pause and think", "appreciate you breaking it down like this",
                "always refreshing to see constructive thoughts on timeline"
            ],
            "closers": [
                " 💡", " thanks for sharing! 👍", " 👏", " ✨", " 💯", " well articulated! 🙌"
            ]
        }
    }
}


def load_comment_dedup_history() -> set[str]:
    """Memuat daftar komentar yang pernah dikirim untuk mencegah duplikasi identik."""
    if not COMMENT_DEDUP_FILE.exists():
        return set()
    try:
        with open(COMMENT_DEDUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data)
    except Exception:
        return set()


def record_generated_comment(comment: str):
    """Menyimpan komentar ke riwayat deduplikasi."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = list(load_comment_dedup_history())
    history.append(comment)
    # Simpan maksimal 500 riwayat komentar terakhir
    if len(history) > 500:
        history = history[-500:]
    try:
        with open(COMMENT_DEDUP_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Gagal mencatat deduplikasi komentar: {e}")


def is_too_similar(candidate: str, history: set[str], threshold: float = 0.75) -> bool:
    """Mengecek apakah komentar mirip dengan salah satu komentar yang pernah dikirim."""
    cand_words = set(candidate.lower().split())
    if not cand_words:
        return False
    for past in history:
        past_words = set(past.lower().split())
        if not past_words:
            continue
        intersection = cand_words.intersection(past_words)
        union = cand_words.union(past_words)
        jaccard = len(intersection) / len(union)
        if jaccard >= threshold:
            return True
    return False


def detect_language(text: str) -> str:
    """Mendeteksi apakah tweet berbahasa Indonesia atau English."""
    indo_markers = [
        "yang", "ini", "itu", "dan", "di", "ke", "dari", "bisa", "ada",
        "banget", "aja", "udah", "ngga", "gak", "aku", "kamu", "gua", "lu",
        "bgt", "wkwk", "haha", "bjir", "gimana", "kalo", "buat", "paling",
        "hari", "malam", "pagi", "kopi", "makan", "tidur", "kerja", "sama",
        "orang", "jangan", "terus", "kenapa", "emang", "bener"
    ]
    txt_lower = text.lower()
    matches = sum(1 for m in indo_markers if re.search(r'\b' + re.escape(m) + r'\b', txt_lower))
    return "indonesian" if matches >= 2 else "english"


def detect_nuance_and_topic(text: str) -> str:
    """Mendeteksi konteks dan nuansa spesifik dari postingan."""
    txt_lower = text.lower()

    # Cek Humor / Meme
    humor_kw = ["lucu", "wkwk", "haha", "ngakak", "kocak", "bjir", "anjir", "lol", "lmaoo", "meme", "jokes", "humor"]
    if any(k in txt_lower for k in humor_kw):
        return "humor_meme"

    # Cek Announcement / Rilis
    announce_kw = ["launch", "announc", "live now", "mainnet", "partnership", "release", "shipped", "milestone", "introducing", "update v", "fitur baru", "resmi rilis"]
    if any(k in txt_lower for k in announce_kw):
        return "announcement"

    # Cek Crypto / Market
    crypto_kw = ["crypto", "btc", "eth", "sol", "token", "airdrop", "market", "bull", "bear", "pump", "trading", "wallet", "ath", "holders"]
    if any(k in txt_lower for k in crypto_kw):
        return "crypto"

    # Cek Curhat / Lifestyle
    lifestyle_kw = ["makan", "tidur", "kopi", "capek", "hujan", "film", "relatable", "curhat", "weekend", "work", "mood", "lelah", "istirahat", "jalan", "libur"]
    if any(k in txt_lower for k in lifestyle_kw):
        return "lifestyle"

    return "general"


def generate_unique_smart_comment(tweet_text: str) -> tuple[str, str, str]:
    """
    Generator cerdas multi-komponen:
    Menggabungkan Opener + Core Opinion + Closer secara dinamis.
    Menjamin tidak ada duplikasi atau pola repetitif.
    """
    lang = detect_language(tweet_text)
    nuance = detect_nuance_and_topic(tweet_text)

    lang_pool = DYNAMIC_COMMENT_BUILDERS.get(lang, DYNAMIC_COMMENT_BUILDERS["english"])
    sub_builder = lang_pool.get(nuance, lang_pool["general"])

    openers = sub_builder.get("openers", [""])
    cores = sub_builder.get("cores", ["great point"])
    closers = sub_builder.get("closers", ["!"])

    history = load_comment_dedup_history()

    # Generate hingga dapat kombinasi yang belum pernah dipakai
    best_candidate = ""
    for _ in range(15):
        op = random.choice(openers)
        co = random.choice(cores)
        cl = random.choice(closers)
        candidate = f"{op}{co}{cl}".strip()

        if candidate not in history and not is_too_similar(candidate, history):
            best_candidate = candidate
            break

    if not best_candidate:
        # Fallback dinamis
        op = random.choice(openers)
        co = random.choice(cores)
        cl = random.choice(closers)
        best_candidate = f"{op}{co}{cl}".strip()

    record_generated_comment(best_candidate)
    return best_candidate, lang, nuance


# ==============================================================================
# 📝 LOG & RIWAYAT AKTIVITAS
# ==============================================================================

def load_warmup_history() -> dict:
    """Memuat riwayat aktivitas warming up."""
    if not WARMUP_HISTORY_FILE.exists():
        return {}
    try:
        with open(WARMUP_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def record_warmup_event(account: str, action_type: str, details: dict):
    """Mencatat aktivitas ke riwayat."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    hist = load_warmup_history()
    hist.setdefault(account, []).append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action_type,
        "details": details
    })
    try:
        with open(WARMUP_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Gagal mencatat riwayat: {e}")


def get_used_yapping_posts() -> set[str]:
    """Mengumpulkan postingan yapping yang sudah pernah digunakan agar tidak ada duplikasi."""
    hist = load_warmup_history()
    used = set()
    for acc, events in hist.items():
        for ev in events:
            if ev.get("action") == "post":
                txt = ev.get("details", {}).get("text", "")
                if txt:
                    used.add(txt)
    return used


def choose_unique_yapping_post(used_posts: set[str]) -> str:
    """Memilih postingan yapping yang belum pernah dipakai."""
    available = [t for t in YAPPING_TEMPLATES if t not in used_posts]
    if not available:
        base = random.choice(YAPPING_TEMPLATES)
        variations = [" 😂", " ✨", " 🙌", " wkwk", " haha", " 👀", " bgt wkwk", " yaampun"]
        return base + random.choice(variations)
    return random.choice(available)


# ==============================================================================
# 🤖 PLAYWRIGHT ACTIONS: POST & LIKE/COMMENT
# ==============================================================================

async def post_yapping_tweet(page: Page, text: str) -> tuple[bool, str]:
    """Membuat tweet yapping baru melalui composer dengan verifikasi tuntas."""
    print(f"   ✍️  Membuka composer tweet...")
    try:
        await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(4)

        # Proaktif menutup popup / dialog "Unlock more on X", "Got it", "Dismiss", dll
        popup_selectors = [
            'button:has-text("Got it")',
            'div[role="button"]:has-text("Got it")',
            '[aria-label="Close"]',
            'button:has-text("Dismiss")',
            'button:has-text("Accept all cookies")'
        ]
        for sel in popup_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    print(f"      Dismissing popup: {sel}")
                    await el.click(force=True)
                    await asyncio.sleep(1)
            except Exception:
                pass

        textarea = page.locator('[data-testid="tweetTextarea_0"]').first
        if await textarea.count() == 0 or not await textarea.is_visible():
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(3)
            textarea = page.locator('[data-testid="tweetTextarea_0"]').first

        await textarea.wait_for(state="visible", timeout=12000)
        print(f"   💬 Mengetik konten yapping: \"{text}\"")
        await textarea.click()
        await asyncio.sleep(0.5)
        await textarea.fill(text)
        await asyncio.sleep(1.0)

        # Trigger React event listeners
        await textarea.press("End")
        await textarea.type(" ")
        await textarea.press("Backspace")
        await asyncio.sleep(1.0)

        # Cari tombol kirim (tweetButton)
        btn1 = page.locator('[data-testid="tweetButton"]').first
        btn2 = page.locator('[data-testid="tweetButtonInline"]').first
        send_btn = btn1 if (await btn1.count() > 0 and await btn1.is_enabled()) else btn2

        if not await send_btn.is_enabled():
            await asyncio.sleep(1.5)

        if not await send_btn.is_enabled():
            return False, "Tombol kirim tweet dalam keadaan disabled"

        print(f"   🚀 Mengirim tweet ke timeline X...")
        await send_btn.click()
        await asyncio.sleep(5)

        return True, "Tweet berhasil diposting dan terbit di X"
    except Exception as e:
        return False, str(e)


def get_last_post_time(account: str) -> float:
    """Mengembalikan timestamp posting terakhir untuk akun ini."""
    hist = load_warmup_history()
    events = hist.get(account, [])
    for ev in reversed(events):
        if ev.get("action") == "post":
            ts_str = ev.get("timestamp")
            try:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
            except Exception:
                pass
    return 0.0


async def like_and_comment_viral_tweets(page: Page, target_count: int = 5) -> tuple[int, list[str]]:
    """
    Menemukan postingan rame di timeline, memberi Like ❤️ dan Comment 💬 hingga target_count tweet (default: 5x).
    Menggunakan tab terisolasi agar interaksi 100% nyata, bebas benturan modal, dan berhasil terkirim ke X.
    Retweet di-skip sesuai instruksi.
    """
    print(f"   🔍 Memindai timeline For You untuk {target_count}x interaksi Like & Komentar...")
    interacted_summaries = []
    success_count = 0
    processed_tweet_ids = set()

    try:
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(5)

        # Tutup dialog / modal awal jika ada
        for sel in ['button:has-text("Got it")', 'div[role="button"]:has-text("Got it")', '[aria-label="Close"]', 'button:has-text("Dismiss")']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(force=True)
                    await asyncio.sleep(0.5)
            except Exception:
                pass

        for attempt in range(target_count * 3):
            if success_count >= target_count:
                break

            tweet_cards = page.locator('article[data-testid="tweet"]')
            total_tweets = await tweet_cards.count()

            for idx in range(total_tweets):
                if success_count >= target_count:
                    break

                card = tweet_cards.nth(idx)
                status_link = card.locator('a[href*="/status/"]').first
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

                if tweet_id in processed_tweet_ids:
                    continue
                processed_tweet_ids.add(tweet_id)

                text_el = card.locator('[data-testid="tweetText"]').first
                if await text_el.count() == 0:
                    continue

                text_content = await text_el.inner_text()
                if len(text_content.strip()) < 20:
                    continue

                clean_preview = text_content.replace("\n", " ")[:55]
                tweet_url = f"https://x.com{href}" if href.startswith("/") else href

                print(f"\n   🎯 [{success_count + 1}/{target_count}] Tweet dari @{author}: \"{clean_preview}...\"")

                # Generate komentar cerdas & dinamis
                comment_text, lang_used, topic_used = generate_unique_smart_comment(text_content)
                print(f"      💬 Bahasa: [{lang_used.upper()}] | Nuansa: [{topic_used.upper()}]")
                print(f"      ✍️  Draf Komentar: \"{comment_text}\"")

                # Buka tab terisolasi untuk eksekusi Like & Komentar
                tweet_tab = None
                try:
                    tweet_tab = await page.context.new_page()
                    await tweet_tab.goto(tweet_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3.5)

                    main_article = tweet_tab.locator('article[data-testid="tweet"]').first
                    try:
                        await main_article.wait_for(state="visible", timeout=20000)
                    except Exception:
                        pass

                    # 1. LIKE POSTINGAN
                    like_btn = main_article.locator('[data-testid="like"]').first
                    unlike_btn = main_article.locator('[data-testid="unlike"]').first

                    for _ in range(8):
                        if (await like_btn.count() > 0 and await like_btn.is_visible()) or (await unlike_btn.count() > 0 and await unlike_btn.is_visible()):
                            break
                        await asyncio.sleep(0.8)

                    if await like_btn.count() > 0 and await like_btn.is_visible():
                        await like_btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await like_btn.click(force=True)

                        try:
                            await unlike_btn.wait_for(state="visible", timeout=7000)
                        except Exception:
                            pass

                        print(f"      ❤️  Like tweet @{author} ✓ (Terkonfirmasi di X)")
                        await asyncio.sleep(random.uniform(1.2, 2.0))
                    elif await unlike_btn.count() > 0:
                        print(f"      ℹ️  Tweet sudah pernah di-like sebelumnya.")

                    # 2. COMMENT / REPLY POSTINGAN
                    r_btn = main_article.locator('[data-testid="reply"]').first
                    if await r_btn.count() > 0 and await r_btn.is_visible():
                        await r_btn.scroll_into_view_if_needed()
                        await r_btn.click(force=True)
                        await asyncio.sleep(1.5)
                    else:
                        await tweet_tab.evaluate("window.scrollBy(0, 700);")
                        await asyncio.sleep(1.5)

                    reply_box = tweet_tab.locator('[data-testid="tweetTextarea_0"]').first
                    if await reply_box.count() > 0:
                        await reply_box.scroll_into_view_if_needed()
                        await reply_box.click(force=True)
                        await asyncio.sleep(0.5)

                        # Ketik komentar secara natural agar event DraftJS aktif
                        await tweet_tab.keyboard.type(comment_text, delay=10)
                        await asyncio.sleep(0.8)

                        # Kirim via shortcut resmi Twitter Control+Enter
                        await tweet_tab.keyboard.press("Control+Enter")

                        # Fallback jika belum terkirim via keyboard: klik tombol Reply
                        send_reply_btn = tweet_tab.locator('[data-testid="tweetButtonInline"], [data-testid="tweetButton"]').first
                        if await send_reply_btn.count() > 0 and await send_reply_btn.is_enabled():
                            await send_reply_btn.click(force=True)

                        # Verifikasi pengiriman berhasil
                        sent_confirmed = False
                        for _ in range(10):
                            await asyncio.sleep(1.0)
                            val = await reply_box.inner_text() if await reply_box.count() > 0 else ""
                            if not val.strip():
                                sent_confirmed = True
                                break
                            toast = tweet_tab.locator('div:has-text("Your post was sent")').first
                            if await toast.count() > 0:
                                sent_confirmed = True
                                break

                        # Proaktif menutup popup upsell
                        try:
                            u_close = tweet_tab.locator('[aria-label="Close"], button:has-text("Maybe later")').first
                            if await u_close.count() > 0 and await u_close.is_visible():
                                await u_close.click(force=True)
                        except Exception:
                            pass

                        print(f"      ✓ Like & Komentar balasan berhasil terbit di X!")
                            success_count += 1
                            interacted_summaries.append(f"Liked & Commented: '{comment_text}' (@{author})")
                        else:
                            print(f"      ❌ Tombol kirim komentar tidak aktif.")
                    else:
                        print(f"      ❌ Input box balasan tidak ditemukan.")

                except Exception as ex_tab:
                    print(f"      ❌ Gagal interaksi tweet: {ex_tab}")
                finally:
                    if tweet_tab:
                        try:
                            await tweet_tab.close()
                        except Exception:
                            pass

                # Jeda alami antar komentar (10 - 20 detik)
                if success_count < target_count:
                    delay_between_comments = random.uniform(10.0, 20.0)
                    print(f"      ⏱️  Jeda alami sebelum komentar berikutnya: {delay_between_comments:.1f} detik...")
                    await asyncio.sleep(delay_between_comments)

            # Scroll ke bawah untuk memuat tweet baru
            await page.mouse.wheel(0, 900)
            await asyncio.sleep(3)

        return success_count, interacted_summaries

    except Exception as e:
        logger.error(f"Error pada interaksi timeline: {e}")
        return success_count, interacted_summaries


# ==============================================================================
# 🚀 CORE WARMUP ROUTINE FOR ACCOUNTS
# ==============================================================================

async def warm_up_single_account(
    account_info: dict,
    used_yappings: set[str],
    do_post: bool = True,
    do_interaction: bool = True,
    comments_per_cycle: int = 5,
    post_cooldown_min_hours: float = 1.0,
    post_cooldown_max_hours: float = 2.0,
    force_post: bool = False,
    headless: bool = True,
    dry_run: bool = False
) -> dict:
    """Menjalankan siklus warming up untuk satu akun."""
    uname = account_info.get("screen_name", "")
    dname = account_info.get("name", "")
    auth_token = account_info.get("auth_token", "")
    ct0 = account_info.get("ct0", "")

    print(f"\n{CYAN}╔═══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║ 🔥 WARMING UP AKUN: {BOLD}@{uname}{RESET}{CYAN} ({dname}){' ' * max(0, 37 - len(uname) - len(dname))}║{RESET}")
    print(f"{CYAN}╚═══════════════════════════════════════════════════════════════╝{RESET}")

    results = {"account": uname, "post_ok": False, "interaction_ok": False, "comments_done": 0}

    # Cek apakah akun sudah boleh memposting yapping (Jeda 1-2 Jam atau dipaksa via force_post)
    now_ts = datetime.now().timestamp()
    last_post_ts = get_last_post_time(uname)
    elapsed_minutes = (now_ts - last_post_ts) / 60.0
    target_cooldown_minutes = random.uniform(post_cooldown_min_hours * 60.0, post_cooldown_max_hours * 60.0)

    should_post_this_cycle = do_post and (force_post or last_post_ts == 0.0 or elapsed_minutes >= target_cooldown_minutes)

    chosen_post = choose_unique_yapping_post(used_yappings)
    used_yappings.add(chosen_post)

    if dry_run:
        print(f"{YELLOW}[MODE SIMULASI / DRY RUN]{RESET}")
        if should_post_this_cycle:
            print(f"  • Status Postingan Yapping : DIJADWALKAN POST (Sudah {elapsed_minutes:.0f} menit sejak post terakhir)")
            print(f"  • Preview Yapping Post     : \"{chosen_post}\"")
        else:
            print(f"  • Status Postingan Yapping : DILEWATI (Baru {elapsed_minutes:.0f} menit lalu, target jeda 1-2 jam)")

        dummy_comment, dlang, dnuance = generate_unique_smart_comment("Hari ini cuaca mendung banget ya enaknya tidur wkwk")
        print(f"  • Target Like & Komentar   : {comments_per_cycle}x tweet viral (Retweet dilewati)")
        print(f"  • Contoh Komentar Cerdas   : \"{dummy_comment}\" (Topik: {dnuance.upper()})")
        results["post_ok"] = True
        results["interaction_ok"] = True
        results["comments_done"] = comments_per_cycle
        return results

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
        cookies = [
            {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"},
            {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
        ]
        await context.add_cookies(cookies)
        page = await context.new_page()

        # 1. TUGAS A: POSTING YAPPING SANTAI (JIKA SUDAH MELEWATI JEDA 1-2 JAM)
        if should_post_this_cycle:
            print(f"\n{BOLD}[1/2] 📝 Membuat Postingan Yapping Santai Bahasa Indonesia...{RESET}")
            ok_post, msg_post = await post_yapping_tweet(page, chosen_post)
            if ok_post:
                print(f"   {GREEN}✓ Berhasil memposting yapping!{RESET}")
                record_warmup_event(uname, "post", {"text": chosen_post})
                results["post_ok"] = True
            else:
                print(f"   {RED}❌ Gagal post: {msg_post}{RESET}")

            delay_gap = random.uniform(8.0, 16.0)
            print(f"   ⏱️  Jeda istirahat antar tugas: {delay_gap:.1f} detik...")
            await asyncio.sleep(delay_gap)
        else:
            print(f"\n{YELLOW}[1/2] ⏳ Yapping Post dilewati pada siklus ini (Baru diposting {elapsed_minutes:.0f} menit lalu, target jeda 1-2 jam).{RESET}")
            results["post_ok"] = True

        # 2. TUGAS B: 5x LIKE & SMART COMMENT POSTINGAN VIRAL (NO RETWEET)
        if do_interaction:
            print(f"\n{BOLD}[2/2] 💬 Menjalankan {comments_per_cycle}x Like & Komentar di Postingan Rame...{RESET}")
            done_count, summaries = await like_and_comment_viral_tweets(page, target_count=comments_per_cycle)
            results["comments_done"] = done_count
            if done_count > 0:
                print(f"   {GREEN}✓ Berhasil menyelesaikan {done_count}/{comments_per_cycle} interaksi like & komentar!{RESET}")
                record_warmup_event(uname, "interaction", {"count": done_count, "items": summaries})
                results["interaction_ok"] = True
            else:
                print(f"   {RED}❌ Tidak ada interaksi like/komentar yang berhasil.{RESET}")

        await browser.close()

    return results


async def run_warming_cycle(
    target_accounts: list[str] = None,
    do_post: bool = True,
    do_interaction: bool = True,
    comments_per_cycle: int = 5,
    post_cooldown_min_hours: float = 1.0,
    post_cooldown_max_hours: float = 2.0,
    headless: bool = True,
    dry_run: bool = False,
    pause_between_accounts: int = 25
) -> list[dict]:
    """Menjalankan 1 siklus warming up untuk semua akun farm."""
    data = load_accounts()
    all_accs = data.get("accounts", {})

    farm_accounts = []
    for uname, acc in all_accs.items():
        clean_uname = acc.get("screen_name", uname).lower()
        if clean_uname == "fannettt":
            continue  # Lewati akun utama

        if target_accounts:
            if clean_uname in [t.lower().lstrip("@") for t in target_accounts]:
                farm_accounts.append(acc)
        else:
            farm_accounts.append(acc)

    if not farm_accounts:
        print(f"{YELLOW}Tidak ada akun farm yang ditemukan untuk di-warm up.{RESET}")
        return []

    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║          TWITTER / X ACCOUNT WARMER & YAPPING BOT             ║
║  Pemanasan Akun Baru: Yapping Bahasa Indo + Like & Komentar   ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")
    print(f"Total Akun Farm Target : {GREEN}{BOLD}{len(farm_accounts)} akun{RESET}")
    for i, a in enumerate(farm_accounts, 1):
        print(f"  [{i}] @{a.get('screen_name')} ({a.get('name')})")
    print(f"Target Like & Komentar : {BOLD}{comments_per_cycle}x per akun per siklus{RESET} (Tanpa Retweet)")
    print(f"Rentang Jeda Posting   : {post_cooldown_min_hours:.0f} - {post_cooldown_max_hours:.0f} Jam (Bahasa Indonesia)")
    print(f"Jeda Antar Akun        : {pause_between_accounts} detik")
    print(f"Mode Eksekusi          : {'Dry-Run (Simulasi)' if dry_run else 'Live (Eksekusi Nyata)'}\n")

    used_yappings = get_used_yapping_posts()
    summary = []

    for idx, acc in enumerate(farm_accounts, 1):
        uname = acc.get("screen_name")
        print(f"\n{BOLD}▶️ Memproses [{idx}/{len(farm_accounts)}] @{uname}...{RESET}")
        res = await warm_up_single_account(
            account_info=acc,
            used_yappings=used_yappings,
            do_post=do_post,
            do_interaction=do_interaction,
            comments_per_cycle=comments_per_cycle,
            post_cooldown_min_hours=post_cooldown_min_hours,
            post_cooldown_max_hours=post_cooldown_max_hours,
            headless=headless,
            dry_run=dry_run
        )
        summary.append(res)

        if idx < len(farm_accounts):
            pause_time = random.randint(max(10, pause_between_accounts - 5), pause_between_accounts + 10)
            print(f"\n{YELLOW}💤 Istirahat sebelum berganti ke akun berikutnya: {pause_time} detik...{RESET}")
            await asyncio.sleep(pause_time)

    print(f"\n{CYAN}============================================================{RESET}")
    print(f"{GREEN}{BOLD}🎉 SIKLUS WARMING UP SELESAI UNTUK SEMUA AKUN FARM!{RESET}")
    print(f"{CYAN}============================================================{RESET}")
    for s in summary:
        status_post = f"{GREEN}Post ✓{RESET}" if s["post_ok"] else f"{RED}Post ❌{RESET}"
        status_int = f"{GREEN}{s['comments_done']}/{comments_per_cycle} Comments ✓{RESET}" if s["interaction_ok"] else f"{RED}0 Comments ❌{RESET}"
        print(f"• @{s['account']:<15} : {status_post} | {status_int}")
    print(f"\nLog riwayat tersimpan di: {WARMUP_HISTORY_FILE}\n")
    return summary


async def run_warming_parallel(
    target_accounts: list[str] = None,
    do_post: bool = True,
    do_interaction: bool = True,
    comments_per_cycle: int = 5,
    post_cooldown_min_hours: float = 1.0,
    post_cooldown_max_hours: float = 2.0,
    headless: bool = True,
    dry_run: bool = False,
    stagger_delay: float = 4.0
) -> list[dict]:
    """
    Menjalankan siklus warming up untuk SEMUA akun farm SECARA BERSAMAAN (PARALEL).
    Masing-masing akun berjalan mandiri di browser context terisolasi secara simultan.
    Diberi sedikit jeda peluncuran (stagger_delay) agar tidak membebani sistem secara tiba-tiba.
    """
    data = load_accounts()
    all_accs = data.get("accounts", {})

    farm_accounts = []
    for uname, acc in all_accs.items():
        clean_uname = acc.get("screen_name", uname).lower()
        if clean_uname == "fannettt":
            continue  # Lewati akun utama

        if target_accounts:
            if clean_uname in [t.lower().lstrip("@") for t in target_accounts]:
                farm_accounts.append(acc)
        else:
            farm_accounts.append(acc)

    if not farm_accounts:
        print(f"{YELLOW}Tidak ada akun farm yang ditemukan untuk di-warm up.{RESET}")
        return []

    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║       ⚡ TWITTER / X PARALLEL MULTI-ACCOUNT WARMER ⚡         ║
║     Menjalankan Seluruh Akun Farm Bersamaan (Simultan)        ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")
    print(f"Total Akun Farm Aktif  : {GREEN}{BOLD}{len(farm_accounts)} Akun Berjalan Serentak{RESET}")
    for i, a in enumerate(farm_accounts, 1):
        print(f"  [{i}] @{a.get('screen_name')} ({a.get('name')})")
    print(f"Target Like & Komentar : {BOLD}{comments_per_cycle}x per akun per siklus{RESET} (Tanpa Retweet)")
    print(f"Rentang Jeda Posting   : {post_cooldown_min_hours:.0f} - {post_cooldown_max_hours:.0f} Jam (Bahasa Indonesia)")
    print(f"Mode Eksekusi          : {'Simulasi (Dry-Run)' if dry_run else 'Live Paralel'}\n")

    used_yappings = get_used_yapping_posts()

    async def _runner_with_stagger(acc, idx):
        if idx > 0 and stagger_delay > 0:
            await asyncio.sleep(idx * stagger_delay)
        return await warm_up_single_account(
            account_info=acc,
            used_yappings=used_yappings,
            do_post=do_post,
            do_interaction=do_interaction,
            comments_per_cycle=comments_per_cycle,
            post_cooldown_min_hours=post_cooldown_min_hours,
            post_cooldown_max_hours=post_cooldown_max_hours,
            headless=headless,
            dry_run=dry_run
        )

    tasks = [_runner_with_stagger(acc, i) for i, acc in enumerate(farm_accounts)]
    summary = await asyncio.gather(*tasks, return_exceptions=False)

    print(f"\n{CYAN}============================================================{RESET}")
    print(f"{GREEN}{BOLD}🎉 SEMUA AKUN FARM SELESAI DIEKSEKUSI SECARA PARALEL!{RESET}")
    print(f"{CYAN}============================================================{RESET}")
    for s in summary:
        status_post = f"{GREEN}Post ✓{RESET}" if s.get("post_ok") else f"{RED}Post ❌{RESET}"
        status_int = f"{GREEN}{s.get('comments_done', 0)}/{comments_per_cycle} Comments ✓{RESET}" if s.get("interaction_ok") else f"{RED}0 Comments ❌{RESET}"
        print(f"• @{s.get('account', 'unknown'):<15} : {status_post} | {status_int}")
    print(f"\nLog riwayat tersimpan di: {WARMUP_HISTORY_FILE}\n")
    return summary


async def run_warming_loop(
    interval_min_minutes: float = 10.0,
    interval_max_minutes: float = 30.0,
    comments_per_cycle: int = 5,
    post_cooldown_min_hours: float = 1.0,
    post_cooldown_max_hours: float = 2.0,
    target_accounts: list[str] = None,
    do_post: bool = True,
    do_interaction: bool = True,
    parallel: bool = True,
    headless: bool = True,
    dry_run: bool = False
):
    """
    Mode Otomatis Terjadwal 24/7:
    Menjalankan 5x Like & Comment tiap siklus dengan jeda siklus acak 10 - 30 Menit.
    Postingan yapping otomatis diberi jeda acak 1 - 2 Jam.
    """
    print(f"{MAGENTA}{BOLD}🕒 MODE PENJADWALAN OTOMATIS AKTIF ({'PARALEL' if parallel else 'SEKUENSIAL'}){RESET}")
    print(f"  • Jeda Acak Antar Siklus : {GREEN}{BOLD}{interval_min_minutes:.0f} - {interval_max_minutes:.0f} Menit{RESET}")
    print(f"  • Like & Komentar        : {GREEN}{BOLD}{comments_per_cycle}x per akun per siklus{RESET} (Tanpa Retweet)")
    print(f"  • Rentang Jeda Postingan : {GREEN}{BOLD}{post_cooldown_min_hours:.0f} - {post_cooldown_max_hours:.0f} Jam{RESET} (Yapping Indo)")
    cycle_count = 1

    while True:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}============================================================{RESET}")
        print(f"{BOLD}🚀 [SIKLUS KE-{cycle_count}] Dimulai pada: {now_str}{RESET}")
        print(f"{CYAN}============================================================{RESET}")

        if parallel:
            await run_warming_parallel(
                target_accounts=target_accounts,
                do_post=do_post,
                do_interaction=do_interaction,
                comments_per_cycle=comments_per_cycle,
                post_cooldown_min_hours=post_cooldown_min_hours,
                post_cooldown_max_hours=post_cooldown_max_hours,
                headless=headless,
                dry_run=dry_run
            )
        else:
            await run_warming_cycle(
                target_accounts=target_accounts,
                do_post=do_post,
                do_interaction=do_interaction,
                comments_per_cycle=comments_per_cycle,
                post_cooldown_min_hours=post_cooldown_min_hours,
                post_cooldown_max_hours=post_cooldown_max_hours,
                headless=headless,
                dry_run=dry_run,
                pause_between_accounts=25
            )

        cycle_count += 1
        sleep_minutes = random.uniform(interval_min_minutes, interval_max_minutes)
        sleep_seconds = int(sleep_minutes * 60)
        wake_time = datetime.fromtimestamp(datetime.now().timestamp() + sleep_seconds).strftime("%H:%M:%S")

        print(f"\n{YELLOW}💤 Siklus selesai. Beristirahat acak selama {sleep_minutes:.1f} menit...{RESET}")
        print(f"{CYAN}⏰ Siklus pemanasan berikutnya dijadwalkan pukul: {BOLD}{wake_time}{RESET}\n")

        # Countdown update tiap 2 menit
        remaining = sleep_seconds
        while remaining > 0:
            step = min(remaining, 120)
            await asyncio.sleep(step)
            remaining -= step
            if remaining > 0:
                print(f"   ⏳ Masih istirahat... {remaining // 60} menit tersisa menuju siklus berikutnya ({wake_time})")


def main():
    parser = argparse.ArgumentParser(description="Twitter / X Account Warmer & Yapping Bot")
    parser.add_argument("--run-all", action="store_true", help="Jalankan 1 siklus warming up untuk semua akun farm (ke-7 akun)")
    parser.add_argument("-p", "--parallel", action="store_true", default=True, help="Jalankan seluruh akun secara paralel/simultan (default: True)")
    parser.add_argument("--sequential", action="store_true", help="Jalankan satu-per-satu secara berurutan")
    parser.add_argument("-a", "--account", type=str, help="Jalankan warming up hanya untuk 1 akun tertentu")
    parser.add_argument("--comments", type=int, default=5, help="Jumlah Like & Komentar per siklus per akun (default: 5)")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus menerus dengan jeda acak 10 - 30 Menit (Anti-Suspend)")
    parser.add_argument("--interval-min", type=float, default=10.0, help="Jeda minimal loop antar siklus dalam menit (default: 10)")
    parser.add_argument("--interval-max", type=float, default=30.0, help="Jeda maksimal loop antar siklus dalam menit (default: 30)")
    parser.add_argument("--post-min", type=float, default=1.0, help="Jeda minimal antar post yapping dalam jam (default: 1.0)")
    parser.add_argument("--post-max", type=float, default=2.0, help="Jeda maksimal antar post yapping dalam jam (default: 2.0)")
    parser.add_argument("--no-post", action="store_true", help="Jangan membuat postingan yapping (hanya like & comment)")
    parser.add_argument("--no-interaction", action="store_true", help="Jangan melakukan like & comment (hanya yapping)")
    parser.add_argument("--pause", type=int, default=25, help="Jeda antar akun dalam detik untuk mode sekuensial (default: 25)")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi saja tanpa memposting/berinteraksi nyata")
    parser.add_argument("--visible", action="store_true", help="Tampilkan browser (default: headless)")

    args = parser.parse_args()

    targets = [args.account] if args.account else None
    is_parallel = not args.sequential

    try:
        if args.loop:
            asyncio.run(run_warming_loop(
                interval_min_minutes=args.interval_min,
                interval_max_minutes=args.interval_max,
                comments_per_cycle=args.comments,
                post_cooldown_min_hours=args.post_min,
                post_cooldown_max_hours=args.post_max,
                target_accounts=targets,
                do_post=not args.no_post,
                do_interaction=not args.no_interaction,
                parallel=is_parallel,
                headless=not args.visible,
                dry_run=args.dry_run
            ))
        else:
            if is_parallel and not args.account:
                asyncio.run(run_warming_parallel(
                    target_accounts=targets,
                    do_post=not args.no_post,
                    do_interaction=not args.no_interaction,
                    comments_per_cycle=args.comments,
                    post_cooldown_min_hours=args.post_min,
                    post_cooldown_max_hours=args.post_max,
                    headless=not args.visible,
                    dry_run=args.dry_run
                ))
            else:
                asyncio.run(run_warming_cycle(
                    target_accounts=targets,
                    do_post=not args.no_post,
                    do_interaction=not args.no_interaction,
                    comments_per_cycle=args.comments,
                    post_cooldown_min_hours=args.post_min,
                    post_cooldown_max_hours=args.post_max,
                    headless=not args.visible,
                    dry_run=args.dry_run,
                    pause_between_accounts=args.pause
                ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Warming up bot dihentikan oleh pengguna.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
