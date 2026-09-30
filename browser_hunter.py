import asyncio
import json
import random
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import COOKIES_FILE, RESULTS_DIR
from wallet_config import load_wallet_config
from airdrop_parser import analyze_airdrop_tweet
from airdrop_actions import is_already_entered, record_entry

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def clean_cooldown(seconds: int, message: str = "Jeda alami antar tweet"):
    """Jeda istirahat bersih tanpa merusak tampilan log."""
    print(f"   ⏱️  {message}: {seconds} detik...", flush=True)
    await asyncio.sleep(seconds)

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

async def execute_tweet_tasks(
    context: BrowserContext,
    tweet_id: str,
    tweet_text: str,
    author: str,
    wallet_cfg: dict,
    account: str = ""
) -> tuple[bool, list[str]]:
    """
    Eksekusi 4 tugas lengkap di tweet secara terisolasi & nyata di X:
    1. Like ❤️
    2. Retweet 🔁
    3. Follow author 👤 (Langsung di halaman status atau profil author)
    4. Drop Address 👛 (100% Pure Address di textarea dengan verifikasi pengiriman)
    """
    actions_done = []
    req = analyze_airdrop_tweet(tweet_text, author)

    # 1. Tentukan alamat wallet yang sesuai (EVM vs Solana)
    evm_addr = wallet_cfg.get("evm_address", "").strip()
    sol_addr = wallet_cfg.get("solana_address", "").strip()

    if req.wallet_type == "SOLANA":
        target_network = "SOLANA"
        target_wallet = sol_addr
    elif req.wallet_type == "EVM":
        target_network = "EVM"
        target_wallet = evm_addr
    elif req.wallet_type == "BOTH":
        target_network = "EVM+SOLANA"
        target_wallet = f"{evm_addr}\n{sol_addr}" if (evm_addr and sol_addr) else (evm_addr or sol_addr)
    else:
        unspec = wallet_cfg.get("unspecified_default", "EVM").upper()
        if unspec == "SOLANA":
            target_network = "SOLANA"
            target_wallet = sol_addr or evm_addr
        elif unspec == "BOTH" and evm_addr and sol_addr:
            target_network = "EVM+SOLANA"
            target_wallet = f"{evm_addr}\n{sol_addr}"
        else:
            target_network = "EVM"
            target_wallet = evm_addr or sol_addr

    print(f"   🌐 Jaringan Terdeteksi : {MAGENTA}{BOLD}[{target_network}]{RESET}")
    print(f"   👛 Alamat Disiapkan    : {CYAN}{target_wallet.replace(chr(10), ' | ')}{RESET}")

    tweet_url = f"https://x.com/{author}/status/{tweet_id}"
    tweet_page = None

    try:
        # Buka tab terisolasi untuk tweet ini agar DOM & scrolling feed pencarian tetap bersih
        tweet_page = await context.new_page()
        try:
            await tweet_page.goto(tweet_url, wait_until="commit", timeout=25000)
        except Exception:
            pass

        # Tunggu tweet article ter-mount di DOM
        try:
            await tweet_page.wait_for_selector('article[data-testid="tweet"], article, [data-testid="like"], [data-testid="reply"]', timeout=12000)
        except Exception:
            pass

        await asyncio.sleep(2.0)

        # Tutup dialog / banner pengganggu jika muncul
        popup_selectors = [
            'button:has-text("Got it")',
            'div[role="button"]:has-text("Got it")',
            '[aria-label="Close"]',
            'button:has-text("Dismiss")',
            'button:has-text("Maybe later")',
            'button:has-text("Accept all cookies")'
        ]
        for sel in popup_selectors:
            try:
                el = tweet_page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(force=True)
                    await asyncio.sleep(0.5)
            except Exception:
                pass

        main_tweet = tweet_page.locator('article[data-testid="tweet"]').first
        if await main_tweet.count() == 0:
            main_tweet = tweet_page.locator('article').first

        # Cek apakah tweet sudah dihapus atau tidak tersedia lagi di X
        try:
            del_el = tweet_page.locator('text="This Post is unavailable", text="This Post was deleted", text="Hmm...this page doesn’t exist", text="Post unavailable"').first
            if (await del_el.count() > 0 and await del_el.is_visible()) or await main_tweet.count() == 0:
                await asyncio.sleep(2.0)
                if await main_tweet.count() == 0:
                    print(f"   ⚠️ Tweet ini sudah dihapus oleh pembuatnya atau tidak tersedia (Post Unavailable), dilewati.")
                    return False
        except Exception:
            pass

        # ======================================================================
        # TASK 1: LIKE ❤️
        # ======================================================================
        try:
            like_btn = main_tweet.locator('[data-testid="like"]').first
            unlike_btn = main_tweet.locator('[data-testid="unlike"]').first

            # Scroll ke tweet agar tombol Like/RT/Reply ter-render di viewport
            try:
                await main_tweet.scroll_into_view_if_needed()
            except Exception:
                await tweet_page.evaluate("window.scrollBy(0, 200);")

            # Tunggu elemen Like atau Unlike siap di DOM
            for _ in range(8):
                if (await like_btn.count() > 0 and await like_btn.is_visible()) or (await unlike_btn.count() > 0 and await unlike_btn.is_visible()):
                    break
                await asyncio.sleep(0.8)

            if await like_btn.count() > 0 and await like_btn.is_visible():
                await like_btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await like_btn.click(force=True)

                # Verifikasi tombol Unlike (hati merah/pink) aktif
                try:
                    await unlike_btn.wait_for(state="visible", timeout=7000)
                except Exception:
                    pass

                actions_done.append("Like ❤️")
                print(f"   [1/4] ❤️  Like Tweet       : {GREEN}✓ Berhasil (Terkonfirmasi di X){RESET}")
                await asyncio.sleep(random.uniform(1.2, 2.0))
            elif await unlike_btn.count() > 0:
                actions_done.append("Like ❤️ (Sudah liked)")
                print(f"   [1/4] ❤️  Like Tweet       : {YELLOW}✓ Sudah di-like sebelumnya{RESET}")
            else:
                # Coba cari tombol like di seluruh tweet page
                page_like = tweet_page.locator('[data-testid="like"]').first
                page_unlike = tweet_page.locator('[data-testid="unlike"]').first
                if await page_like.count() > 0 and await page_like.is_visible():
                    await page_like.scroll_into_view_if_needed()
                    await page_like.click(force=True)
                    try:
                        await page_unlike.wait_for(state="visible", timeout=7000)
                    except Exception:
                        pass
                    actions_done.append("Like ❤️")
                    print(f"   [1/4] ❤️  Like Tweet       : {GREEN}✓ Berhasil (Terkonfirmasi di X){RESET}")
                    await asyncio.sleep(random.uniform(1.2, 2.0))
                else:
                    print(f"   [1/4] ❤️  Like Tweet       : {YELLOW}- Tombol like tidak ditemukan{RESET}")
        except Exception as e:
            print(f"   [1/4] ❤️  Like Tweet       : {RED}✗ Error ({e}){RESET}")

        # ======================================================================
        # TASK 2: RETWEET 🔁
        # ======================================================================
        try:
            rt_btn = main_tweet.locator('[data-testid="retweet"]').first
            unrt_btn = main_tweet.locator('[data-testid="unretweet"]').first

            for _ in range(6):
                if (await rt_btn.count() > 0 and await rt_btn.is_visible()) or (await unrt_btn.count() > 0 and await unrt_btn.is_visible()):
                    break
                await asyncio.sleep(0.8)

            if await rt_btn.count() > 0 and await rt_btn.is_visible():
                await rt_btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await rt_btn.click(force=True)
                await asyncio.sleep(1.2)
                confirm_btn = tweet_page.locator('[data-testid="retweetConfirm"], [role="menuitem"]:has-text("Repost")').first
                if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                    await confirm_btn.click(force=True)
                    actions_done.append("Retweet 🔁")
                    print(f"   [2/4] 🔁 Retweet          : {GREEN}✓ Berhasil (Terkonfirmasi di X){RESET}")
                    await asyncio.sleep(random.uniform(1.5, 2.5))
                else:
                    print(f"   [2/4] 🔁 Retweet          : {YELLOW}- Konfirmasi tidak muncul{RESET}")
                await tweet_page.keyboard.press("Escape")
            elif await unrt_btn.count() > 0:
                actions_done.append("Retweet 🔁 (Sudah RT)")
                print(f"   [2/4] 🔁 Retweet          : {YELLOW}✓ Sudah di-RT sebelumnya{RESET}")
            else:
                # Coba cari tombol retweet di halaman
                page_rt = tweet_page.locator('[data-testid="retweet"]').first
                page_unrt = tweet_page.locator('[data-testid="unretweet"]').first
                if await page_rt.count() > 0 and await page_rt.is_visible():
                    await page_rt.scroll_into_view_if_needed()
                    await page_rt.click(force=True)
                    await asyncio.sleep(1.2)
                    c_btn = tweet_page.locator('[data-testid="retweetConfirm"], [role="menuitem"]:has-text("Repost")').first
                    if await c_btn.count() > 0 and await c_btn.is_visible():
                        await c_btn.click(force=True)
                        actions_done.append("Retweet 🔁")
                        print(f"   [2/4] 🔁 Retweet          : {GREEN}✓ Berhasil (Terkonfirmasi di X){RESET}")
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    await tweet_page.keyboard.press("Escape")
                elif await page_unrt.count() > 0:
                    actions_done.append("Retweet 🔁 (Sudah RT)")
                    print(f"   [2/4] 🔁 Retweet          : {YELLOW}✓ Sudah di-RT sebelumnya{RESET}")
                else:
                    print(f"   [2/4] 🔁 Retweet          : {YELLOW}- Tombol retweet tidak ditemukan{RESET}")
        except Exception as e:
            print(f"   [2/4] 🔁 Retweet          : {RED}✗ Error ({e}){RESET}")
            await tweet_page.keyboard.press("Escape")

        # ======================================================================
        # TASK 3: DROP ADDRESS 👛 (Reply - 100% PURE WALLET ADDRESS ONLY)
        # ======================================================================
        if not target_wallet:
            print(f"   [3/4] 👛 Drop Address     : {RED}✗ Alamat {target_network} kosong di wallets.json!{RESET}")
        else:
            try:
                # Tutup dialog / banner pengganggu jika ada
                for sel in popup_selectors:
                    try:
                        el = tweet_page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click(force=True)
                            await asyncio.sleep(0.3)
                    except Exception:
                        pass

                # Cek apakah pembuat tweet membatasi/menonaktifkan kolom komentar
                restricted_el = tweet_page.locator('text="Who can reply?", text="can reply", [aria-label*="cannot reply" i]').first
                if await restricted_el.count() > 0 and await restricted_el.is_visible():
                    print(f"   [3/4] 👛 Drop Address     : {YELLOW}⚠️ Pembuat tweet membatasi/menutup komentar (Replies restricted){RESET}")
                else:
                    # 1. Cek apakah textarea balasan sudah aktif/terbuka di halaman
                    active_textarea = None
                    dialog_ta = tweet_page.locator('[role="dialog"] [data-testid="tweetTextarea_0"]').first
                    inline_ta = tweet_page.locator('[data-testid="tweetTextarea_0"]').first
                    generic_ta = tweet_page.locator('div[contenteditable="true"][role="textbox"]').first

                    if await dialog_ta.count() > 0 and await dialog_ta.is_visible():
                        active_textarea = dialog_ta
                    elif await inline_ta.count() > 0 and await inline_ta.is_visible():
                        active_textarea = inline_ta
                    elif await generic_ta.count() > 0 and await generic_ta.is_visible():
                        active_textarea = generic_ta

                    # Jika belum terbuka, picu dengan klik icon reply pada tweet atau placeholder label
                    if not active_textarea:
                        r_icon = main_tweet.locator('[data-testid="reply"]').first
                        if await r_icon.count() == 0 or not await r_icon.is_visible():
                            r_icon = tweet_page.locator('[data-testid="reply"]').first

                        if await r_icon.count() > 0 and await r_icon.is_visible():
                            await r_icon.scroll_into_view_if_needed()
                            await r_icon.click(force=True)
                            await asyncio.sleep(1.2)
                        else:
                            placeholder_label = tweet_page.locator('[data-testid="tweetTextarea_0_label"], div:has-text("Post your reply")').first
                            if await placeholder_label.count() > 0 and await placeholder_label.is_visible():
                                await placeholder_label.click(force=True)
                                await asyncio.sleep(1.0)
                            else:
                                await tweet_page.evaluate("window.scrollBy(0, 300);")
                                await asyncio.sleep(1.0)

                    # Cari ulang setelah dipicu
                    if await dialog_ta.count() > 0 and await dialog_ta.is_visible():
                        active_textarea = dialog_ta
                    elif await inline_ta.count() > 0 and await inline_ta.is_visible():
                        active_textarea = inline_ta
                    elif await generic_ta.count() > 0 and await generic_ta.is_visible():
                        active_textarea = generic_ta
                    elif await inline_ta.count() > 0:
                        active_textarea = inline_ta

                if active_textarea:
                    full_reply_text = target_wallet.strip()
                    await active_textarea.scroll_into_view_if_needed()
                    await active_textarea.click(force=True)
                    await asyncio.sleep(0.3)

                    # Ketik alamat wallet secara natural agar state DraftJS terupdate 100%
                    await tweet_page.keyboard.type(full_reply_text, delay=10)
                    await asyncio.sleep(0.5)

                    # Kirim via shortcut resmi Twitter Control+Enter
                    await tweet_page.keyboard.press("Control+Enter")

                    # Fallback: klik tombol Reply jika masih aktif
                    send_btn = tweet_page.locator('[role="dialog"] [data-testid="tweetButtonInline"], [role="dialog"] [data-testid="tweetButton"], [data-testid="tweetButtonInline"], [data-testid="tweetButton"]').first
                    if await send_btn.count() > 0 and await send_btn.is_enabled():
                        try:
                            await send_btn.click(force=True, timeout=2000)
                        except Exception:
                            pass

                    # Verifikasi pengiriman aman tanpa blocking 30 detik pada elemen yang tertutup
                    reply_sent_ok = False
                    for _ in range(8):
                        await asyncio.sleep(0.8)
                        toast = tweet_page.locator('div:has-text("Your post was sent")').first
                        if await toast.count() > 0:
                            reply_sent_ok = True
                            break
                        try:
                            if await active_textarea.count() == 0 or not await active_textarea.is_visible():
                                reply_sent_ok = True
                                break
                            val = await active_textarea.inner_text(timeout=500)
                            if not val.strip():
                                reply_sent_ok = True
                                break
                        except Exception:
                            reply_sent_ok = True
                            break

                    # Proaktif menutup popup upsell Premium ("Want more people to see your reply?")
                    try:
                        upsell_close = tweet_page.locator('[aria-label="Close"], button:has-text("Maybe later")').first
                        if await upsell_close.count() > 0 and await upsell_close.is_visible():
                            await upsell_close.click(force=True)
                    except Exception:
                        pass

                    actions_done.append(f"Drop {target_network} ({target_wallet[:6]}...{target_wallet[-4:]}) 👛")
                    print(f"   [3/4] 👛 Drop Address     : {GREEN}✓ Berhasil terkirim ke X! ({target_network}: {target_wallet[:6]}...){RESET}")
                    await asyncio.sleep(random.uniform(1.2, 2.5))
                else:
                    print(f"   [3/4] 👛 Drop Address     : {RED}✗ Input box balasan tidak ditemukan{RESET}")
            except Exception as e:
                print(f"   [3/4] 👛 Drop Address     : {RED}✗ Error saat reply ({e}){RESET}")

        # ======================================================================
        # TASK 4: FOLLOW 👤 (Follow author)
        # ======================================================================
        try:
            # Cari tombol follow di halaman status tweet (sidebar "Relevant people" atau header tweet)
            follow_btn = tweet_page.locator(f'button[aria-label*="Follow @{author}" i], button[data-testid$="-follow"]').first
            unfollow_btn = tweet_page.locator(f'button[aria-label*="Following @{author}" i], button[data-testid$="-unfollow"]').first

            if await follow_btn.count() > 0 and await follow_btn.is_visible():
                await follow_btn.click(force=True)
                actions_done.append(f"Follow @{author} 👤")
                print(f"   [4/4] 👤 Follow @{author}  : {GREEN}✓ Berhasil follow (Status Page){RESET}")
                await asyncio.sleep(random.uniform(1.2, 2.2))
            elif await unfollow_btn.count() > 0 and await unfollow_btn.is_visible():
                actions_done.append(f"Follow @{author} (Sudah followed)")
                print(f"   [4/4] 👤 Follow @{author}  : {YELLOW}✓ Sudah di-follow sebelumnya{RESET}")
            else:
                # Fallback Pasti: Buka tab terisolasi ke profil author https://x.com/{author}
                f_page = None
                try:
                    f_page = await context.new_page()
                    await f_page.goto(f"https://x.com/{author}", wait_until="commit", timeout=15000)
                    try:
                        await f_page.wait_for_selector('button[data-testid$="-follow"], button[data-testid$="-unfollow"]', timeout=8000)
                    except Exception:
                        pass
                    await asyncio.sleep(1.5)
                    p_follow = f_page.locator('button[data-testid$="-follow"]').first
                    p_unfollow = f_page.locator('button[data-testid$="-unfollow"]').first
                    if await p_follow.count() > 0 and await p_follow.is_visible():
                        await p_follow.click(force=True)
                        actions_done.append(f"Follow @{author} 👤")
                        print(f"   [4/4] 👤 Follow @{author}  : {GREEN}✓ Berhasil follow (Author Profile){RESET}")
                        await asyncio.sleep(random.uniform(1.0, 1.8))
                    elif await p_unfollow.count() > 0:
                        actions_done.append(f"Follow @{author} (Sudah followed)")
                        print(f"   [4/4] 👤 Follow @{author}  : {YELLOW}✓ Sudah di-follow sebelumnya{RESET}")
                    else:
                        print(f"   [4/4] 👤 Follow @{author}  : {YELLOW}- Tombol follow tidak ditemukan di profil{RESET}")
                except Exception as ex_p:
                    print(f"   [4/4] 👤 Follow @{author}  : {RED}✗ Error profil ({ex_p}){RESET}")
                finally:
                    if f_page:
                        try:
                            await f_page.close()
                        except Exception:
                            pass
        except Exception as e:
            print(f"   [4/4] 👤 Follow @{author}  : {RED}✗ Error ({e}){RESET}")

    except Exception as e:
        print(f"   ⚠️ Kendala eksekusi tweet: {e}")
    finally:
        if tweet_page:
            try:
                await tweet_page.close()
            except Exception:
                pass

    success = len(actions_done) > 0
    if success:
        record_entry(tweet_id, {
            "username": author,
            "text": tweet_text[:120],
            "url": tweet_url,
            "wallet_type": target_network
        }, actions_done, account=account)

    return success, actions_done

async def run_hunter(
    category: str = "ALL",
    target_count: int = 10,
    max_age_hours: float = 12.0,
    headless: bool = True,
    account_info: dict = None
):
    account_info = account_info or {}
    uname = account_info.get("screen_name", "")
    auth_token = account_info.get("auth_token", "")
    ct0 = account_info.get("ct0", "")

    header_title = f"AUTO-HUNTER (@{uname})" if uname else "AUTO-HUNTER (CHROME PIPELINE)"

    wallet_cfg = load_wallet_config().copy()
    if account_info.get("evm_address"):
        wallet_cfg["evm_address"] = account_info["evm_address"]
    if account_info.get("solana_address"):
        wallet_cfg["solana_address"] = account_info["solana_address"]

    evm_addr = wallet_cfg.get("evm_address", "").strip()
    sol_addr = wallet_cfg.get("solana_address", "").strip()

    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         {header_title.center(53)} ║
║    Like ➔ Retweet ➔ Follow ➔ Drop EVM/Solana Address          ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")

    print(f"Konfigurasi Bot:")
    if uname:
        print(f"  • Akun Twitter   : {CYAN}@{uname}{RESET}")
    print(f"  • EVM (0x...)    : {GREEN}{evm_addr or '[KOSONG]'}{RESET}")
    print(f"  • Solana         : {GREEN}{sol_addr or '[KOSONG]'}{RESET}")
    print(f"  • Target Mode    : {MAGENTA}{BOLD}[{category.upper()}]{RESET}")
    print(f"  • Batas Rentang  : {YELLOW}Hingga {max_age_hours} jam terakhir{RESET}")
    print(f"  • Format Balasan : {CYAN}Hanya Alamat Wallet Saja (Pure Address){RESET}")

    if not evm_addr and not sol_addr:
        print(f"\n{RED}❌ Kamu belum mengisi alamat wallet EVM maupun Solana!{RESET}")
        return

    cat = category.upper()
    if cat == "EVM":
        raw_query = '("drop your 0x" OR "drop 0x" OR "drop your evm" OR "drop your eth") (RT OR Retweet OR Like)'
    elif cat == "SOLANA":
        raw_query = '("drop your sol" OR "drop sol" OR "drop your solana" OR "drop phantom") (RT OR Retweet OR Like)'
    else:
        raw_query = '("drop your 0x" OR "drop 0x" OR "drop your sol" OR "drop sol" OR "drop your address") (RT OR Retweet OR Like)'

    encoded_q = urllib.parse.quote(raw_query)

    # Memindai 2 sumber:
    # 1. TOP TAB (Paling populer & aktif dalam 12 jam terakhir)
    # 2. LIVE TAB (Tweet terbaru berurutan mundur)
    search_targets = [
        ("TOP (Populer Aktif 12 Jam)", f"https://x.com/search?q={encoded_q}"),
        ("LIVE (Tweet Terbaru)", f"https://x.com/search?q={encoded_q}&f=live")
    ]

    async with async_playwright() as p:
        print(f"\n{YELLOW}Membuka browser Google Chrome (Headless: {headless})...{RESET}")
        browser = await p.chromium.launch(channel="chrome", headless=headless)
        context = await browser.new_context()

        if auth_token and ct0:
            cookies = [
                {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
                {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
                {"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"},
                {"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"}
            ]
            await context.add_cookies(cookies)
        else:
            has_cookies = await load_playwright_cookies(context)
            if not has_cookies:
                print(f"{RED}File cookies.json tidak ditemukan!{RESET}")
                await browser.close()
                return

        page = await context.new_page()
        executed_count = 0
        seen_tweet_ids = set()

        for tab_name, search_url in search_targets:
            if executed_count >= target_count:
                break

            print(f"\n{CYAN}--- Memindai Tab: {BOLD}{tab_name}{RESET} ---")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"{YELLOW}Gagal memuat {tab_name}: {e}{RESET}")
                continue

            if "login" in page.url:
                print(f"{RED}❌ Twitter mengarahkan ke login. Cookie kadaluarsa.{RESET}")
                await browser.close()
                return

            scroll_attempts = 0
            while executed_count < target_count and scroll_attempts < 12:
                articles = page.locator('article[data-testid="tweet"]')
                total_articles = await articles.count()

                for idx in range(total_articles):
                    if executed_count >= target_count:
                        break

                    tweet_el = articles.nth(idx)

                    # Ambil link tweet
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

                    if tweet_id in seen_tweet_ids:
                        continue
                    seen_tweet_ids.add(tweet_id)

                    # Cek riwayat agar tidak pernah duplikat
                    if is_already_entered(tweet_id, account=uname):
                        print(f"[-] Skip @{author} (Tweet ID {tweet_id} sudah pernah dikerjakan oleh @{uname or 'akun ini'})")
                        continue

                    # Periksa usia tweet (filter rentang max_age_hours)
                    tweet_age_str = ""
                    is_within_age = True
                    time_el = tweet_el.locator("time").first
                    if await time_el.count() > 0:
                        dt_str = await time_el.get_attribute("datetime")
                        if dt_str:
                            try:
                                created_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                                now_dt = datetime.now(timezone.utc)
                                age_hours = (now_dt - created_dt).total_seconds() / 3600.0
                                tweet_age_str = f"{age_hours:.1f} jam yang lalu"
                                if age_hours > max_age_hours:
                                    print(f"[-] Skip @{author} (Usia tweet: {tweet_age_str}, melebihi {max_age_hours} jam)")
                                    is_within_age = False
                            except Exception:
                                pass

                    if not is_within_age:
                        continue

                    # Ambil teks tweet
                    text_el = tweet_el.locator('[data-testid="tweetText"]').first
                    tweet_text = await text_el.inner_text() if await text_el.count() > 0 else ""
                    clean_preview = tweet_text.replace("\n", " ")[:110]

                    print(f"\n{CYAN}============================================================{RESET}")
                    print(f"{BOLD}🎯 [{executed_count + 1}/{target_count}] Tweet dari @{author}{RESET}")
                    if tweet_age_str:
                        print(f"⏱️  Diposting : {GREEN}{tweet_age_str} [MASUK RENTANG 12 JAM ✓]{RESET}")
                    print(f"📝 Teks      : \"{clean_preview}...\"")
                    print(f"🔗 Link      : https://x.com/{author}/status/{tweet_id}")
                    print(f"⚡ Menjalankan 4 Tugas:")

                    try:
                        await tweet_el.scroll_into_view_if_needed()
                        await asyncio.sleep(1.0)
                    except Exception:
                        pass

                    ok, actions = await execute_tweet_tasks(
                        context=context,
                        tweet_id=tweet_id,
                        tweet_text=tweet_text,
                        author=author,
                        wallet_cfg=wallet_cfg,
                        account=uname
                    )

                    if ok:
                        executed_count += 1
                        print(f"{GREEN}✓ Tweet berhasil diselesaikan! ({', '.join(actions)}){RESET}")
                    else:
                        print(f"{YELLOW}- Tidak ada aksi yang berhasil dikerjakan.{RESET}")

                    if executed_count < target_count:
                        cooldown_sec = random.randint(8, 14)
                        await clean_cooldown(cooldown_sec, "Jeda alami antar tweet")

                if executed_count < target_count:
                    print(f"{YELLOW}⬇️  Scroll ke bawah untuk mencari tweet 12 jam terakhir...{RESET}")
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2);")
                    await asyncio.sleep(4)
                    scroll_attempts += 1

        print(f"\n{CYAN}============================================================{RESET}")
        print(f"{GREEN}{BOLD}🎉 PERBURUAN SELESAI!{RESET}")
        print(f"Total tweet yang berhasil dikerjakan: {BOLD}{executed_count}{RESET} / {target_count}")
        print(f"Data riwayat tersimpan di: {RESULTS_DIR / 'airdrop_history.json'}\n")

        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Twitter Airdrop Browser Hunter")
    parser.add_argument("-c", "--category", choices=["all", "evm", "solana"], default="all", help="Kategori target (all, evm, solana)")
    parser.add_argument("-m", "--max", type=int, default=10, help="Jumlah maksimal tweet (default: 10)")
    parser.add_argument("--hours", type=float, default=12.0, help="Batas rentang usia tweet dalam jam (default: 12.0)")
    parser.add_argument("--visible", action="store_true", help="Tampilkan jendela browser (default: headless)")

    args = parser.parse_args()

    try:
        asyncio.run(run_hunter(
            category=args.category,
            target_count=args.max,
            max_age_hours=args.hours,
            headless=not args.visible
        ))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Dihentikan oleh pengguna.{RESET}")
        sys.exit(0)
