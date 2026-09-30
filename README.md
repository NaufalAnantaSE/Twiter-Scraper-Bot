# 𝕏 (Twitter) Multi-Account Automation & Giveaway Hunter Suite 🚀

Suite otomatisasi multi-akun Twitter / X terlengkap dan modern berbasis **Python + Playwright (Headless Chrome)**. Dirancang khusus untuk **Scraping & Auto-Hunter Airdrop Giveaway (EVM & Solana)**, **Warming Up Akun (Yapping & Interaksi Timeline)**, serta manajemen terpadu multi-akun via **Web Dashboard** dan **CLI Standalone**.

---

## 🌟 Fitur Utama

### 1. 🎁 Scraping & Auto-Hunter Giveaway (EVM & Solana)
- **Eksekusi 4 Aksi Wajib Secara Nyata di X**:
  1. **❤️ Auto-Like**: Menyukai tweet target dengan deteksi dan konfirmasi status aktif.
  2. **🔁 Auto-Retweet (Repost)**: Melakukan retweet/repost otomatis.
  3. **👤 Auto-Follow Author**: Mengikuti author giveaway di halaman status tweet atau profil author secara otomatis.
  4. **👛 Auto-Drop Address**: Mengetik alamat wallet murni (*pure address*) secara natural via keyboard & `Control + Enter` ke GraphQL API Twitter tanpa terblokir modal/banner.
- **Deteksi Jaringan Otomatis**: Mendeteksi kebutuhan alamat **EVM (`0x...`)** atau **Solana (Base58)** sesuai isi tweet.
- **Filter Rentang Waktu**: Memindai tweet aktif dalam rentang waktu tertentu (misal: 12 jam terakhir).
- **Anti-Duplikasi**: Seluruh tweet yang sudah pernah dikerjakan dicatat di `results/airdrop_history.json` agar tidak pernah dobel entri.

### 2. 💬 Yapping Random & Account Warmer (Anti-Suspend)
- **Postingan Yapping Santai**: Memposting tweet curhat harian, gosip/opini netizen, dan tips edukasi ringan berbahasa Indonesia dengan variasi template anti-duplikat.
- **5x Like & Smart Comment Timeline**: Menjelajahi timeline *For You*, mendeteksi topik postingan, dan memposting balasan komentar cerdas dan relevan (Bahasa Indonesia / Inggris).

### 3. 🌐 Modern Web Dashboard (Port 5050)
- Tampilan UI responsif dengan **Sidebar Navigasi Kiri**:
  - 🏠 **Dashboard**: Ringkasan status, token, dan aktivitas seluruh akun.
  - 💬 **Yapping Random**: Kontrol pemanasan akun & looping jeda alami (10–30 menit).
  - 🎁 **Scraping Giveaway**: Mulai & hentikan perburuan giveaway per-akun atau semua akun.
  - 👛 **Submit Address**: Form input dan penyimpanan alamat wallet EVM & Solana untuk masing-masing akun.

### 4. ⚡ Standalone Low-RAM Hunter (Mode Mandiri Hemat Memori)
- Menjalankan scraping giveaway secara **berurutan (sequential)** 1 akun pada satu waktu.
- Setiap kali akun selesai, browser otomatis ditutup tuntas sehingga RAM 100% bersih kembali sebelum beralih ke akun berikutnya.
- Cocok untuk laptop/VPS dengan spesifikasi RAM terbatas.

---

## 🛠️ Panduan Instalasi & Persiapan

### 1. Prasyarat Sistem
- **Python 3.10+** terinstal di sistem.
- **Google Chrome** terinstal (Playwright menggunakan channel Chrome).

### 2. Clone Repositori & Masuk Folder
```bash
cd "twitter-scraper-bot"
```

### 3. Install Dependensi & Browser Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## ⚙️ Konfigurasi Akun & Wallet

### 1. Salin File Contoh Konfigurasi
```bash
cp accounts.json.example accounts.json
cp wallets.json.example wallets.json
```

### 2. Mengisi Akun di `accounts.json`
Dapatkan cookie `auth_token` dan `ct0` dari browser kamu (melalui *Inspect Element ➔ Application ➔ Cookies ➔ https://x.com*):
```json
{
  "active_account": "fannettt",
  "accounts": {
    "fannettt": {
      "screen_name": "fannettt",
      "name": "Fannet",
      "auth_token": "ISI_AUTH_TOKEN_AKUN_1",
      "ct0": "ISI_CT0_AKUN_1",
      "evm_address": "0x914d683638BdF964d1ed7a55EC76C32c786C5240",
      "solana_address": "ER8VpGr7psPRsitY1h6HkEZjyiGBo8MFRduwuqGGWF5T"
    },
    "akun_kedua": {
      "screen_name": "akun_kedua",
      "name": "Akun 2",
      "auth_token": "ISI_AUTH_TOKEN_AKUN_2",
      "ct0": "ISI_CT0_AKUN_2",
      "evm_address": "0x779d939E0B4C047E8A546A2D5e3FeA022c296628",
      "solana_address": "47DufCMaJBncLj1NcrExqtseLkGpKmP3sg8bZf6RT2jS"
    }
  }
}
```

---

## 🚀 Cara Menjalankan Bot

### 📌 Pilihan A: Menjalankan Web Dashboard (Rekomendasi UI)
Jalankan server dashboard web:
```bash
python web_dashboard.py
```
Buka browser dan akses:
👉 **[http://localhost:5050](http://localhost:5050)**

Fitur di dashboard:
- Tambah / Hapus akun Twitter dengan `auth_token` dan `ct0`.
- Atur alamat wallet EVM & Solana tiap akun.
- Tombol **Mulai / Hentikan** untuk Yapping Random & Scraping Giveaway secara terpisah per-akun atau global.

---

### 📌 Pilihan B: Menjalankan Mode Mandiri / Low-RAM (Rekomendasi Laptop/VPS)
Jalankan loop perburuan giveaway untuk semua akun secara bergiliran tanpa beban web server:
```bash
# Default: 5 tweet per akun, jeda antar ronde 10-20 menit
python standalone_hunter_loop.py -m 5 --min-delay 10 --max-delay 20

# Khusus memburu giveaway Solana:
python standalone_hunter_loop.py -c SOLANA -m 5

# Khusus memburu giveaway EVM:
python standalone_hunter_loop.py -c EVM -m 5

# Mode browser terlihat (non-headless):
python standalone_hunter_loop.py --visible
```

---

### 📌 Pilihan C: Menjalankan 1x Sesi Cepat via CLI
```bash
# Pemanasan / Yapping 1 akun aktif:
python account_warmer.py -a screen_name

# Scraping giveaway 1 akun aktif:
python browser_hunter.py -c all -m 10 --hours 12.0

# Manajemen akun via CLI:
python accounts_manager.py --list
python accounts_manager.py --switch screen_name
```

---

## 📁 Struktur Folder Proyek

```text
twitter-scraper-bot/
├── web_dashboard.py           # Server & UI Web Command Center (Port 5050)
├── standalone_hunter_loop.py  # Runner mandiri looping multi-akun (Low RAM)
├── browser_hunter.py          # Core engine perburuan giveaway (4 aksi)
├── account_warmer.py          # Core engine yapping & komentar timeline
├── accounts_manager.py        # Modul manajemen multi-akun
├── airdrop_parser.py          # Analisis regex cerdas persyaratan tweet
├── airdrop_actions.py         # Pencatatan riwayat & deduplikasi entri
├── accounts.json              # Data akun & token (Terlindungi oleh .gitignore)
├── accounts.json.example      # Template contoh konfigurasi akun
├── wallets.json               # Konfigurasi default wallet
├── wallets.json.example       # Template contoh wallet
├── requirements.txt           # Dependensi Python
└── results/                   # Folder database riwayat eksekusi JSON
    ├── airdrop_history.json
    └── warmup_history.json
```

---

## 🛡️ Keamanan & Privasi

1. **Anti-Leak Token**: File `accounts.json`, `cookies.json`, `wallets.json`, serta folder `results/` secara otomatis diabaikan oleh `.gitignore`. Jangan pernah mengunggah token pribadi Anda ke publik!
2. **Human-like Delays**: Seluruh modul dilengkapi jeda acak manusiawi dan event keyboard natural untuk meminimalisir risiko shadowban atau rate-limit dari X/Twitter.

---

## 📄 Lisensi
Distributed under the MIT License.
