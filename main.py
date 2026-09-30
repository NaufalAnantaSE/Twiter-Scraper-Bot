import asyncio
import sys
import os
from pathlib import Path

# Memastikan console Windows mendukung UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from auth import init_client, load_existing_session, save_cookies_from_tokens, login_with_credentials
from scraper import (
    scrape_tweets_by_keyword,
    scrape_airdrop_giveaways,
    scrape_user_timeline,
    scrape_tweet_detail_and_replies
)
from exporter import export_data, export_single_tweet_with_replies
from wallet_config import (
    load_wallet_config,
    save_wallet_config,
    is_valid_evm_address,
    is_valid_solana_address
)
from airdrop_actions import execute_airdrop_actions, is_already_entered, load_history, compose_reply_text
from config import COOKIES_FILE, RESULTS_DIR
from giveaway_templates import generate_solana_giveaway, generate_evm_giveaway
from tweet_poster import post_tweet, GIVEAWAY_LOG_FILE
from auto_giveaway_scheduler import giveaway_scheduler_loop

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

def print_banner():
    banner = f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         TWITTER / X AUTO DROP ADDRESS (EVM & SOLANA)          ║
║      Auto-Detect: Drop 0x/SOL, Like, RT, Follow & Tag         ║
╚═══════════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)

def print_cookie_tutorial():
    print(f"\n{YELLOW}{BOLD}📖 PANDUAN MENGAMBIL COOKIE TWITTER / X (30 Detik):{RESET}")
    print(f"1. Buka browser dan login ke {CYAN}https://x.com{RESET}")
    print(f"2. Tekan tombol {BOLD}F12{RESET} untuk membuka Developer Tools.")
    print(f"3. Masuk ke tab {BOLD}Application{RESET} (atau {BOLD}Storage{RESET} jika di Firefox).")
    print(f"4. Di menu kiri: {BOLD}Cookies -> https://x.com{RESET}")
    print(f"5. Salin nilai dari:")
    print(f"   • {BOLD}auth_token{RESET} (~40 karakter)")
    print(f"   • {BOLD}ct0{RESET} (~160 karakter)\n")

async def setup_auth(client) -> dict:
    while True:
        print(f"\n{BOLD}Pilih Metode Login ke Twitter/X:{RESET}")
        print(f"[{GREEN}1{RESET}] {BOLD}Input Cookie auth_token & ct0{RESET} (Paling Direkomendasikan ⭐)")
        print(f"[{GREEN}2{RESET}] Login menggunakan Username & Password")
        print(f"[{GREEN}3{RESET}] Lihat panduan cara ambil cookie")
        print(f"[{RED}0{RESET}] Batal & Keluar")

        choice = input(f"\nPilihan kamu [1/2/3/0]: ").strip()

        if choice == "1":
            print(f"\n{CYAN}--- Input Cookie Browser ---{RESET}")
            auth_token = input("Masukkan 'auth_token': ").strip()
            ct0 = input("Masukkan 'ct0': ").strip()

            if not auth_token or not ct0:
                print(f"{RED}auth_token dan ct0 tidak boleh kosong!{RESET}")
                continue

            print(f"{YELLOW}Memverifikasi session ke Twitter...{RESET}")
            user_info = await save_cookies_from_tokens(client, auth_token, ct0)
            if user_info:
                print(f"{GREEN}✓ Berhasil login sebagai: @{user_info['screen_name']} ({user_info['name']}){RESET}")
                return user_info
            else:
                print(f"{RED}❌ Cookie tidak valid atau kadaluarsa. Pastikan kamu copy seluruh nilainya.{RESET}")

        elif choice == "2":
            print(f"\n{CYAN}--- Login dengan Kredensial ---{RESET}")
            username = input("Username Twitter (tanpa @): ").strip()
            email = input("Email akun Twitter: ").strip()
            password = input("Password Twitter: ").strip()

            if not username or not password:
                print(f"{RED}Username dan password wajib diisi!{RESET}")
                continue

            print(f"{YELLOW}Sedang mencoba login...{RESET}")
            try:
                user_info = await login_with_credentials(client, username, email, password)
                if user_info:
                    print(f"{GREEN}✓ Berhasil login sebagai: @{user_info['screen_name']} ({user_info['name']}){RESET}")
                    return user_info
                else:
                    print(f"{RED}❌ Gagal login. Gunakan metode 1 (Cookie).{RESET}")
            except Exception as e:
                print(f"{RED}❌ Error login: {e}{RESET}")

        elif choice == "3":
            print_cookie_tutorial()
        elif choice == "0":
            sys.exit(0)

def render_progress(current: int, total: int):
    pct = int((current / total) * 100) if total > 0 else 0
    bar_length = 20
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "=" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r{CYAN}[{bar}] {current}/{total} tweets ({pct}%){RESET}")
    sys.stdout.flush()

async def handle_airdrop_hunter(client):
    """Fitur utama: Pencarian dan eksekusi Drop Address EVM & Solana."""
    print(f"\n{MAGENTA}{BOLD}🚀 === AUTO DROP ADDRESS (EVM & SOLANA) === 🚀{RESET}")
    wallet_cfg = load_wallet_config()

    evm_valid = is_valid_evm_address(wallet_cfg.get("evm_address", ""))
    sol_valid = is_valid_solana_address(wallet_cfg.get("solana_address", ""))

    print(f"Status Wallet:")
    if evm_valid:
        print(f"  • EVM (0x...)    : {GREEN}{wallet_cfg['evm_address']} [VALID ✓]{RESET}")
    else:
        print(f"  • EVM (0x...)    : {RED}[BELUM DIISI / TIDAK VALID]{RESET}")

    if sol_valid:
        print(f"  • Solana         : {GREEN}{wallet_cfg['solana_address']} [VALID ✓]{RESET}")
    else:
        print(f"  • Solana         : {RED}[BELUM DIISI / TIDAK VALID]{RESET}")

    print(f"  • Mode Balasan   : {YELLOW}{wallet_cfg.get('reply_mode', 'smart')}{RESET} (Alamat selalu di baris ke-1)")

    if not evm_valid and not sol_valid:
        print(f"\n{RED}⚠️ PERINGATAN: Kamu belum mengisi alamat EVM maupun Solana!{RESET}")
        print(f"Silakan atur terlebih dahulu di menu [2] Pengaturan Wallet.")
        return

    print(f"\nPilih Target Jaringan Drop Address:")
    print(f"[{GREEN}1{RESET}] Khusus EVM (0x / Ethereum / BSC / Base / Arbitrum / Polygon)")
    print(f"[{GREEN}2{RESET}] Khusus Solana (SOL / Phantom / Backpack)")
    print(f"[{GREEN}3{RESET}] Semua Jaringan (EVM + Solana)")
    print(f"[{GREEN}4{RESET}] Custom Query Pencarian")

    cat_choice = input("Pilihan [1/2/3/4]: ").strip()
    category = "ALL"
    custom_query = None

    if cat_choice == "1":
        category = "EVM"
        if not evm_valid:
            print(f"{RED}Alamat EVM kamu belum valid! Masukkan dulu di menu [2].{RESET}")
            return
    elif cat_choice == "2":
        category = "SOLANA"
        if not sol_valid:
            print(f"{RED}Alamat Solana kamu belum valid! Masukkan dulu di menu [2].{RESET}")
            return
    elif cat_choice == "3":
        category = "ALL"
    elif cat_choice == "4":
        custom_query = input("Masukkan custom query: ").strip()

    limit_str = input("Target jumlah tweet drop address [default: 20]: ").strip()
    max_tweets = int(limit_str) if limit_str.isdigit() and int(limit_str) > 0 else 20

    print(f"\n{YELLOW}🔍 Memindai tweet 'Drop Address' ({category})...{RESET}")
    print(f"{YELLOW}Menyaring spam dan duplikasi (-filter:replies -filter:retweets)...{RESET}\n")

    if custom_query:
        tweets = await scrape_tweets_by_keyword(client, custom_query, product="Latest", max_tweets=max_tweets, progress_callback=render_progress)
    else:
        tweets = await scrape_airdrop_giveaways(client, category=category, max_tweets=max_tweets, progress_callback=render_progress)
    print("\n")

    if not tweets:
        print(f"{YELLOW}Tidak ada tweet drop address yang ditemukan saat ini.{RESET}")
        return

    print(f"{GREEN}✓ Berhasil mengumpulkan {len(tweets)} tweet.{RESET}")

    # Simpan database ke CSV & JSON
    csv_file, json_file = export_data(tweets, prefix=f"drop_address_{category.lower()}")
    print(f"📁 Database tersimpan di:")
    print(f"   • CSV  : {csv_file}")
    print(f"   • JSON : {json_file}")

    print(f"\n{BOLD}Pilih Metode Eksekusi Drop Address:{RESET}")
    print(f"[{GREEN}1{RESET}] Review satu per satu (Tinjau & pilih sebelum drop)")
    print(f"[{GREEN}2{RESET}] Auto-Drop SEMUA yang belum pernah diikuti (Dengan jeda acak aman)")
    print(f"[{RED}0{RESET}] Lewati (Hanya simpan data)")

    exec_choice = input("Pilihan [1/2/0]: ").strip()

    if exec_choice == "1":
        # Mode Review Interaktif
        for i, t in enumerate(tweets, 1):
            t_id = t["tweet_id"]
            already = is_already_entered(t_id)

            print(f"\n{CYAN}------------------------------------------------------------{RESET}")
            print(f"{BOLD}[{i}/{len(tweets)}] @{t['username']} - {t['created_at']}{RESET}")
            if already:
                print(f"{YELLOW}⚠️ PERINGATAN: Tweet ini SUDAH PERNAH kamu ikuti!{RESET}")

            clean_text = t['text'].replace('\n', ' ')
            print(f"Teks   : \"{clean_text}\"")
            print(f"Syarat : {BOLD}{t['summary_label']}{RESET}")
            print(f"Link   : {t['url']}")

            req = t.get("_airdrop_req")
            preview_reply = compose_reply_text(req, wallet_cfg) if req else ""
            if preview_reply:
                print(f"Draft Balasan (Drop):")
                print(f"{CYAN}{preview_reply}{RESET}")

            action_input = input(f"\nDrop wallet ke tweet ini? [{GREEN}Y{RESET}=Drop / {YELLOW}S{RESET}=Skip / {RED}Q{RESET}=Selesai]: ").strip().lower()

            if action_input == "y":
                print(f"{YELLOW}Menjalankan Like, RT, Follow & Drop Wallet...{RESET}")
                ok, done = await execute_airdrop_actions(
                    client=client,
                    tweet_id=t_id,
                    author_id=t.get("user_id"),
                    tweet_info=t,
                    req=req,
                    wallet_config=wallet_cfg,
                    force_all_tasks=True
                )
                if ok:
                    print(f"{GREEN}✓ Berhasil dieksekusi: {', '.join(done)}{RESET}")
                else:
                    print(f"{RED}❌ Gagal mengeksekusi.{RESET}")
            elif action_input == "q":
                break

    elif exec_choice == "2":
        # Mode Auto-Drop Batch
        print(f"\n{YELLOW}Memulai auto-drop... Jeda acak {wallet_cfg.get('action_delay_min', 5)}-{wallet_cfg.get('action_delay_max', 12)} detik diterapkan.{RESET}")
        count_success = 0
        for i, t in enumerate(tweets, 1):
            t_id = t["tweet_id"]
            if is_already_entered(t_id):
                print(f"[{i}/{len(tweets)}] Skip @{t['username']} (Sudah pernah didrop)")
                continue

            req = t.get("_airdrop_req")
            print(f"\n[{i}/{len(tweets)}] Memproses @{t['username']} ({t['summary_label']})...")
            ok, done = await execute_airdrop_actions(
                client=client,
                tweet_id=t_id,
                author_id=t.get("user_id"),
                tweet_info=t,
                req=req,
                wallet_config=wallet_cfg,
                force_all_tasks=True
            )
            if ok:
                count_success += 1
                print(f"{GREEN}✓ Berhasil: {', '.join(done)}{RESET}")
            else:
                print(f"{YELLOW}- Dilewati.{RESET}")

        print(f"\n{GREEN}✓ Selesai! Berhasil melakukan drop wallet ke {count_success} tweet.{RESET}")

def handle_wallet_settings():
    """Menu konfigurasi alamat wallet EVM / Solana & preferensi drop."""
    cfg = load_wallet_config()

    while True:
        evm_val = cfg.get('evm_address', '')
        sol_val = cfg.get('solana_address', '')

        evm_status = f"{GREEN}{evm_val} [VALID ✓]{RESET}" if is_valid_evm_address(evm_val) else (f"{RED}{evm_val} [TIDAK VALID ❌]{RESET}" if evm_val else f"{RED}[KOSONG]{RESET}")
        sol_status = f"{GREEN}{sol_val} [VALID ✓]{RESET}" if is_valid_solana_address(sol_val) else (f"{RED}{sol_val} [TIDAK VALID ❌]{RESET}" if sol_val else f"{RED}[KOSONG]{RESET}")

        print(f"\n{CYAN}{BOLD}--- ⚙️ PENGATURAN WALLET (EVM & SOLANA) ---{RESET}")
        print(f"1. Alamat EVM (0x...)     : {evm_status}")
        print(f"2. Alamat Solana (Base58) : {sol_status}")
        print(f"3. Mode Format Balasan    : {YELLOW}{cfg.get('reply_mode', 'smart')}{RESET} (smart / pure_address / full)")
        print(f"4. Tag Teman              : {YELLOW + ', '.join(cfg.get('tag_friends', [])) + RESET if cfg.get('tag_friends') else '[Kosong]'}")
        print(f"5. Pesan Pendukung        : {cfg.get('default_comment', '')}")
        print(f"6. Jaringan Default       : {cfg.get('unspecified_default', 'EVM')} (Jika tweet hanya bilang 'drop wallet')")
        print(f"7. Toggle Auto-Like       : {'[ON]' if cfg.get('auto_like') else '[OFF]'}")
        print(f"8. Toggle Auto-Retweet    : {'[ON]' if cfg.get('auto_retweet') else '[OFF]'}")
        print(f"9. Toggle Auto-Follow     : {'[ON]' if cfg.get('auto_follow') else '[OFF]'}")
        print(f"0. Selesai & Kembali ke Menu Utama")

        choice = input("\nPilih opsi yang ingin diubah [0-9]: ").strip()

        if choice == "1":
            val = input("Masukkan alamat EVM (Metamask / TrustWallet / 0x...): ").strip()
            if not is_valid_evm_address(val):
                print(f"{YELLOW}⚠️ Peringatan: Format alamat EVM harus berawalan 0x dan 42 karakter.{RESET}")
            cfg["evm_address"] = val
            save_wallet_config(cfg)
            print(f"{GREEN}✓ Alamat EVM disimpan.{RESET}")
        elif choice == "2":
            val = input("Masukkan alamat Solana (Phantom / Solflare): ").strip()
            if not is_valid_solana_address(val):
                print(f"{YELLOW}⚠️ Peringatan: Format alamat Solana harus Base58 (32-44 karakter).{RESET}")
            cfg["solana_address"] = val
            save_wallet_config(cfg)
            print(f"{GREEN}✓ Alamat Solana disimpan.{RESET}")
        elif choice == "3":
            print("\nPilih Format Teks saat Drop Wallet:")
            print("1. 'smart'        : Alamat di baris 1, tag teman jika diminta (Rekomendasi ⭐)")
            print("2. 'pure_address' : HANYA alamat wallet saja, tanpa teks atau tag (Paling aman)")
            print("3. 'full'         : Alamat + komentar pendukung + tag teman")
            m = input("Pilihan mode [1/2/3]: ").strip()
            if m == "2": cfg["reply_mode"] = "pure_address"
            elif m == "3": cfg["reply_mode"] = "full"
            else: cfg["reply_mode"] = "smart"
            save_wallet_config(cfg)
            print(f"{GREEN}✓ Mode balasan diubah ke: {cfg['reply_mode']}{RESET}")
        elif choice == "4":
            print("Masukkan username teman untuk di-tag, pisahkan dengan spasi/koma.")
            print("Contoh: @crypto_fren @sol_hunter @defi_bro")
            raw = input("Username teman: ").strip()
            tags = [x.strip() if x.strip().startswith('@') else f"@{x.strip()}" for x in raw.replace(',', ' ').split() if x.strip()]
            cfg["tag_friends"] = tags
            save_wallet_config(cfg)
            print(f"{GREEN}✓ Tag teman disimpan ({len(tags)} akun).{RESET}")
        elif choice == "5":
            val = input("Masukkan teks komentar pendukung: ").strip()
            if val:
                cfg["default_comment"] = val
                save_wallet_config(cfg)
                print(f"{GREEN}✓ Pesan disimpan.{RESET}")
        elif choice == "6":
            print("Pilih jaringan default jika host tidak menentukan (hanya bilang 'drop wallet'):")
            print("1. EVM (0x)")
            print("2. SOLANA")
            print("3. BOTH (Kirim keduanya)")
            net = input("Pilihan [1/2/3]: ").strip()
            if net == "2": cfg["unspecified_default"] = "SOLANA"
            elif net == "3": cfg["unspecified_default"] = "BOTH"
            else: cfg["unspecified_default"] = "EVM"
            save_wallet_config(cfg)
            print(f"{GREEN}✓ Default jaringan diubah ke: {cfg['unspecified_default']}{RESET}")
        elif choice == "7":
            cfg["auto_like"] = not cfg.get("auto_like", True)
            save_wallet_config(cfg)
        elif choice == "8":
            cfg["auto_retweet"] = not cfg.get("auto_retweet", True)
            save_wallet_config(cfg)
        elif choice == "9":
            cfg["auto_follow"] = not cfg.get("auto_follow", True)
            save_wallet_config(cfg)
        elif choice == "0":
            break

def handle_view_history():
    history = load_history()
    print(f"\n{CYAN}{BOLD}--- 📜 RIWAYAT DROP ADDRESS ({len(history)} Total) ---{RESET}")

    if not history:
        print(f"{YELLOW}Belum ada riwayat drop address yang dieksekusi.{RESET}")
        return

    items = list(history.items())[-15:]
    for i, (tid, data) in enumerate(reversed(items), 1):
        print(f"{BOLD}{i}. @{data.get('author', 'Unknown')} ({data.get('timestamp')}){RESET}")
        print(f"   Aksi : {GREEN}{', '.join(data.get('actions_done', []))}{RESET}")
        print(f"   Teks : \"{data.get('text', '')}...\"")
        print(f"   Link : {data.get('url', '')}\n")

async def handle_search_keyword(client):
    print(f"\n{CYAN}{BOLD}--- Scrape Tweet Umum berdasarkan Keyword / Hashtag ---{RESET}")
    query = input("Masukkan kata kunci pencarian (contoh: 'AI' atau '#crypto'): ").strip()
    if not query:
        return

    filter_choice = input("Pilih filter: [1] Latest (Terbaru) / [2] Top (Populer) [default: 1]: ").strip()
    product = "Top" if filter_choice == "2" else "Latest"
    max_str = input("Jumlah tweet [default: 30]: ").strip()
    max_tweets = int(max_str) if max_str.isdigit() and int(max_str) > 0 else 30

    print(f"\n{YELLOW}Memulai scraping...{RESET}\n")
    tweets = await scrape_tweets_by_keyword(client, query, product=product, max_tweets=max_tweets, progress_callback=render_progress)
    print("\n")

    if tweets:
        csv_file, json_file = export_data(tweets, prefix=f"search_{query}")
        print(f"{GREEN}✓ Berhasil mengambil {len(tweets)} tweet.{RESET}")
        print(f"📁 CSV  : {csv_file}")
        print(f"📁 JSON : {json_file}")
    else:
        print(f"{YELLOW}Tidak ada data ditemukan.{RESET}")

async def handle_user_timeline(client):
    print(f"\n{CYAN}{BOLD}--- Scrape Tweet dari Akun / Profile Tertentu ---{RESET}")
    username = input("Username Twitter (tanpa @): ").strip().lstrip("@")
    if not username:
        return

    max_str = input("Jumlah tweet [default: 30]: ").strip()
    max_tweets = int(max_str) if max_str.isdigit() and int(max_str) > 0 else 30

    try:
        user_info, tweets = await scrape_user_timeline(client, username, max_tweets=max_tweets, progress_callback=render_progress)
        print("\n")
        print(f"{GREEN}👤 Profil: @{user_info['screen_name']} ({user_info['name']}) - {user_info['followers_count']:,} Followers{RESET}")
        if tweets:
            csv_file, json_file = export_data(tweets, prefix=f"user_{username}")
            print(f"📁 CSV  : {csv_file}")
            print(f"📁 JSON : {json_file}")
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")

async def handle_tweet_replies(client):
    print(f"\n{CYAN}{BOLD}--- Scrape Detail Tweet & Komentar (Replies) ---{RESET}")
    raw_input = input("Masukkan URL Tweet atau Tweet ID: ").strip()
    if not raw_input:
        return

    max_str = input("Maksimal replies [default: 30]: ").strip()
    max_replies = int(max_str) if max_str.isdigit() and int(max_str) > 0 else 30

    try:
        main_tweet, replies = await scrape_tweet_detail_and_replies(client, raw_input, max_replies=max_replies, progress_callback=render_progress)
        print("\n")
        print(f"{GREEN}📌 Tweet: @{main_tweet['username']} - \"{main_tweet['text'][:90]}...\"{RESET}")
        print(f"💬 Total replies terkumpul: {len(replies)}")
        if replies:
            csv_file, json_file = export_single_tweet_with_replies(main_tweet, replies, main_tweet['tweet_id'])
            print(f"📁 CSV  : {csv_file}")
            print(f"📁 JSON : {json_file}")
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")

async def handle_auto_tweet_giveaway(client, current_user):
    username = current_user.get("screen_name", "fannettt") if current_user else "fannettt"
    while True:
        print(f"\n{CYAN}{BOLD}╔═══════════════════════════════════════════════════════╗{RESET}")
        print(f"{CYAN}{BOLD}║         AUTO TWEET GIVEAWAY (SOLANA / EVM)            ║{RESET}")
        print(f"{CYAN}{BOLD}╚═══════════════════════════════════════════════════════╝{RESET}")
        print(f"  Akun Twitter: {GREEN}@{username}{RESET}")
        print(f"  [{GREEN}1{RESET}] 🚀 Post 1x Tweet Giveaway Solana Sekarang")
        print(f"  [{GREEN}2{RESET}] 🚀 Post 1x Tweet Giveaway EVM / Ethereum Sekarang")
        print(f"  [{GREEN}3{RESET}] ⏰ Jalankan Auto Tweet Giveaway Terjadwal (Loop 24/7)")
        print(f"  [{GREEN}4{RESET}] 📜 Lihat Riwayat Tweet Giveaway yang Sudah Diposting")
        print(f"  [{RED}0{RESET}] Kembali ke Menu Utama")

        sub_choice = input("\nPilih menu [0-4]: ").strip()
        if sub_choice == "1":
            custom_amt = input("Nominal hadiah (kosongkan untuk acak, contoh: $100): ").strip() or None
            tweet_text = generate_solana_giveaway(username=username, custom_amount=custom_amt)
            print(f"\n{YELLOW}Pratinjau Tweet Solana:{RESET}")
            print(f"{CYAN}----------------------------------------{RESET}")
            print(tweet_text)
            print(f"{CYAN}----------------------------------------{RESET}")
            confirm = input("Kirim tweet ini sekarang? (y/n) [default: y]: ").strip().lower()
            if confirm in ["", "y", "ya", "yes"]:
                ok, url, err = await post_tweet(tweet_text, network="SOLANA", headless=True)
                if ok:
                    print(f"{GREEN}✓ Berhasil diposting! Link: {url}{RESET}")
                else:
                    print(f"{RED}✗ Gagal: {err}{RESET}")
        elif sub_choice == "2":
            custom_amt = input("Nominal hadiah (kosongkan untuk acak, contoh: $100): ").strip() or None
            tweet_text = generate_evm_giveaway(username=username, custom_amount=custom_amt)
            print(f"\n{YELLOW}Pratinjau Tweet EVM:{RESET}")
            print(f"{CYAN}----------------------------------------{RESET}")
            print(tweet_text)
            print(f"{CYAN}----------------------------------------{RESET}")
            confirm = input("Kirim tweet ini sekarang? (y/n) [default: y]: ").strip().lower()
            if confirm in ["", "y", "ya", "yes"]:
                ok, url, err = await post_tweet(tweet_text, network="EVM", headless=True)
                if ok:
                    print(f"{GREEN}✓ Berhasil diposting! Link: {url}{RESET}")
                else:
                    print(f"{RED}✗ Gagal: {err}{RESET}")
        elif sub_choice == "3":
            net = input("Jaringan (solana/evm) [default: solana]: ").strip().lower() or "solana"
            min_str = input("Jeda minimal dalam menit [default: 30]: ").strip() or "30"
            max_str = input("Jeda maksimal dalam menit [default: 60]: ").strip() or "60"
            try:
                min_m = int(min_str)
                max_m = int(max_str)
            except ValueError:
                min_m, max_m = 30, 60
            print(f"\n{GREEN}Memulai scheduler giveaway dengan jeda acak {min_m}-{max_m} menit... Tekan Ctrl+C untuk berhenti.{RESET}")
            try:
                await giveaway_scheduler_loop(min_minutes=min_m, max_minutes=max_m, network=net, headless=True)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print(f"\n{YELLOW}Scheduler dihentikan.{RESET}")
        elif sub_choice == "4":
            if not GIVEAWAY_LOG_FILE.exists():
                print(f"{YELLOW}Belum ada riwayat giveaway yang diposting.{RESET}")
            else:
                try:
                    import json
                    with open(GIVEAWAY_LOG_FILE, "r", encoding="utf-8") as f:
                        hist = json.load(f)
                    print(f"\n{CYAN}{BOLD}=== RIWAYAT POSTINGAN GIVEAWAY ({len(hist)} Tweet) ==={RESET}")
                    for tid, data in list(hist.items())[-10:]:
                        print(f"• [{data.get('timestamp')}] {BOLD}{data.get('network')}{RESET} - {CYAN}{data.get('url')}{RESET}")
                        print(f"  \"{data.get('text', '').splitlines()[0]}...\"")
                except Exception as e:
                    print(f"{RED}Gagal membaca riwayat: {e}{RESET}")
        elif sub_choice == "0":
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")

async def handle_account_management(client):
    from accounts_manager import interactive_account_menu, get_active_account
    await interactive_account_menu()
    active_acc = get_active_account()
    if active_acc:
        return {
            "screen_name": active_acc.get("screen_name", "unknown"),
            "name": active_acc.get("name", "User"),
            "followers_count": 0
        }
    return None

async def handle_unfollow_menu():
    from unfollow_bot import run_unfollow_bot
    print(f"\n{CYAN}{BOLD}--- 🧹 AUTO UNFOLLOW (METODE 2: FOLLOWING LIST) ---{RESET}")
    print("Bot akan memindai daftar following akun Anda, menyaring akun whitelist,")
    print("dan meng-unfollow akun non-follower secara aman.")
    print("1. Jalankan Unfollow (Target 20 akun)")
    print("2. Tentukan jumlah akun sendiri")
    print("3. Mode Simulasi (Dry-Run / Cek Saja)")
    print("0. Batal")

    c = input("\nPilihan [1/2/3/0]: ").strip()
    if c == "1":
        await run_unfollow_bot(target_count=20, keep_followers=True, dry_run=False)
    elif c == "2":
        cnt = input("Masukkan target jumlah akun: ").strip()
        target = int(cnt) if cnt.isdigit() and int(cnt) > 0 else 20
        await run_unfollow_bot(target_count=target, keep_followers=True, dry_run=False)
    elif c == "3":
        await run_unfollow_bot(target_count=10, keep_followers=True, dry_run=True)

async def handle_comment_hijack_menu():
    from comment_hijacker import run_comment_hijacker, hijack_continuous_loop
    print(f"\n{CYAN}{BOLD}--- 💬 COMMENT HIJACKING (VIRAL ACCOUNTS BOOSTER) ---{RESET}")
    print("Bot memantau tweet baru dari akun-akun crypto raksasa (Solana, Binance, dll.)")
    print("dan langsung drop komentar cerdas di menit awal untuk menjaring followers.")
    print("1. Jalankan 1 Sesi (Komentari 5 tweet segar)")
    print("2. Tentukan target jumlah komentar sendiri")
    print("3. Jalankan Mode Pemantauan Terus-menerus (Loop Otomatis)")
    print("0. Batal")

    c = input("\nPilihan [1/2/3/0]: ").strip()
    if c == "1":
        await run_comment_hijacker(max_replies=5, max_age_minutes=120.0, headless=True)
    elif c == "2":
        cnt = input("Target jumlah komentar: ").strip()
        target = int(cnt) if cnt.isdigit() and int(cnt) > 0 else 5
        await run_comment_hijacker(max_replies=target, max_age_minutes=120.0, headless=True)
    elif c == "3":
        await hijack_continuous_loop(interval_minutes=15, max_per_cycle=3, headless=True)

async def handle_account_warmer_menu():
    from account_warmer import run_warming_cycle, run_warming_loop, run_warming_parallel
    print(f"\n{CYAN}{BOLD}--- 🔥 ACCOUNT WARMER & YAPPING BOT (ANTI-SUSPEND) ---{RESET}")
    print("Memanaskan ke-7 akun farm agar aktif, natural, dan aman dari suspend:")
    print("1. ⚡ Jalankan Semua Akun Sekaligus (Paralel / Simultan)")
    print("2. 🕒 Jalankan Mode Otomatis Terjadwal 24/7 (Paralel 10-30 Menit, Post 1-2 Jam)")
    print("3. Jalankan Mode Sekuensial (Satu per satu bergantian)")
    print("4. Mode Simulasi (Dry-Run)")
    print("0. Batal")

    c = input("\nPilihan [1/2/3/4/0]: ").strip()
    if c == "1":
        await run_warming_parallel(do_post=True, do_interaction=True, comments_per_cycle=5, headless=True, dry_run=False)
    elif c == "2":
        await run_warming_loop(interval_min_minutes=10.0, interval_max_minutes=30.0, comments_per_cycle=5, parallel=True, do_post=True, do_interaction=True, headless=True, dry_run=False)
    elif c == "3":
        await run_warming_cycle(do_post=True, do_interaction=True, comments_per_cycle=5, headless=True, dry_run=False)
    elif c == "4":
        await run_warming_parallel(do_post=True, do_interaction=True, comments_per_cycle=5, headless=True, dry_run=True)

async def handle_dashboard_menu():
    import webbrowser
    url = "http://localhost:5050"
    print(f"\n{CYAN}{BOLD}--- 🌐 WEB DASHBOARD MONITORING (COMMAND CENTER) ---{RESET}")
    print(f"Dashboard berjalan di: {GREEN}{url}{RESET}")
    print("Membuka browser otomatis...")
    try:
        webbrowser.open(url)
    except Exception:
        print(f"Silakan buka manual di browser: {url}")

async def main():
    print_banner()

    client = await init_client()

    from accounts_manager import get_active_account
    active_acc = get_active_account()
    if active_acc:
        current_user = {
            "screen_name": active_acc.get("screen_name", "unknown"),
            "name": active_acc.get("name", "User"),
            "followers_count": 0
        }
        print(f"{GREEN}✓ Akun Aktif: @{current_user['screen_name']} ({current_user['name']}){RESET}")
    else:
        print(f"{YELLOW}Memeriksa sesi login tersimpan...{RESET}")
        current_user = await load_existing_session(client)
        if not current_user:
            print(f"{YELLOW}Belum ada sesi login aktif. Silakan login terlebih dahulu.{RESET}")
            current_user = await setup_auth(client)
        else:
            print(f"{GREEN}✓ Terhubung sebagai: @{current_user['screen_name']} ({current_user['name']}){RESET}")

    while True:
        print(f"\n{CYAN}╔══════════════════════ MENU UTAMA ══════════════════════╗{RESET}")
        print(f"  Akun Aktif: {GREEN}@{current_user['screen_name']}{RESET}")
        print(f"  [{GREEN}1{RESET}] 🚀 {BOLD}Auto Drop Address (EVM / Solana){RESET} ⭐")
        print(f"  [{GREEN}2{RESET}] ⚙️  Pengaturan Wallet (EVM, Solana, Mode Balasan)")
        print(f"  [{GREEN}3{RESET}] 📜 Riwayat Drop Address yang Sudah Diikuti")
        print(f"  [{GREEN}4{RESET}] 🎁 {BOLD}Auto Tweet Giveaway (Post / Jadwalkan){RESET} ⭐")
        print(f"  [{GREEN}5{RESET}] 🔍 Scrape Tweet Umum (Keyword / Hashtag)")
        print(f"  [{GREEN}6{RESET}] 👤 Scrape Timeline Profil Akun")
        print(f"  [{GREEN}7{RESET}] 💬 Scrape Detail Tweet & Replies")
        print(f"  [{GREEN}8{RESET}] 🔑 Kelola Akun / Ganti Cookie")
        print(f"  [{GREEN}9{RESET}] 🧹 {BOLD}Auto Unfollow (Following List){RESET} ⭐")
        print(f"  [{GREEN}10{RESET}] 💬 {BOLD}Comment Hijacking (Followers Booster){RESET} ⭐")
        print(f"  [{GREEN}11{RESET}] 🔥 {BOLD}Account Warmer & Yapping Bot (7 Akun Farm){RESET} ⭐")
        print(f"  [{GREEN}12{RESET}] 🌐 {BOLD}Web Dashboard Monitoring (Port 5050){RESET} ⭐")
        print(f"  [{RED}0{RESET}] 🚪 Keluar")
        print(f"{CYAN}╚════════════════════════════════════════════════════════╝{RESET}")

        choice = input("Pilih menu [0-12]: ").strip()

        if choice == "1":
            await handle_airdrop_hunter(client)
        elif choice == "2":
            handle_wallet_settings()
        elif choice == "3":
            handle_view_history()
        elif choice == "4":
            await handle_auto_tweet_giveaway(client, current_user)
        elif choice == "5":
            await handle_search_keyword(client)
        elif choice == "6":
            await handle_user_timeline(client)
        elif choice == "7":
            await handle_tweet_replies(client)
        elif choice == "8":
            res = await handle_account_management(client)
            if res:
                current_user = res
        elif choice == "9":
            await handle_unfollow_menu()
        elif choice == "10":
            await handle_comment_hijack_menu()
        elif choice == "11":
            await handle_account_warmer_menu()
        elif choice == "12":
            await handle_dashboard_menu()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah menggunakan bot! Sukses selalu bro 🚀{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Program dihentikan.{RESET}")
        sys.exit(0)
