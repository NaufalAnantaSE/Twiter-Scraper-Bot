import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from twikit import Client
from twikit.errors import TwitterException, TooManyRequests, DuplicateTweet
from config import RESULTS_DIR
from airdrop_parser import AirdropRequirements

logger = logging.getLogger(__name__)

HISTORY_FILE = RESULTS_DIR / "airdrop_history.json"

def load_history() -> dict:
    """Memuat daftar ID tweet airdrop yang sudah pernah diikuti."""
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_history(history: dict) -> None:
    """Menyimpan riwayat entri ke file JSON."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def is_already_entered(tweet_id: str, account: str = "") -> bool:
    """Mengecek apakah tweet giveaway ini sudah pernah dikerjakan oleh akun tertentu."""
    history = load_history()
    sid = str(tweet_id)
    if not account:
        return sid in history
    clean_acc = account.strip().lstrip("@").lower()
    if f"{clean_acc}_{sid}" in history:
        return True
    if sid in history and history[sid].get("account", "").strip().lstrip("@").lower() == clean_acc:
        return True
    return False

def record_entry(tweet_id: str, tweet_info: dict, actions_done: list[str], account: str = "") -> None:
    """Mencatat giveaway yang telah berhasil dieksekusi oleh akun tertentu."""
    history = load_history()
    sid = str(tweet_id)
    clean_acc = account.strip().lstrip("@")
    key = f"{clean_acc.lower()}_{sid}" if clean_acc else sid
    history[key] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": clean_acc or tweet_info.get("account", "unknown"),
        "author": tweet_info.get("username", tweet_info.get("author", "")),
        "text": tweet_info.get("text", "")[:120],
        "url": tweet_info.get("url", f"https://x.com/{tweet_info.get('username')}/status/{sid}"),
        "wallet_type": tweet_info.get("wallet_type", ""),
        "actions_done": actions_done
    }
    save_history(history)

def determine_target_wallet(req: AirdropRequirements, wallet_config: dict) -> tuple[str, str]:
    """
    Menentukan alamat wallet mana yang harus didrop:
    Mengembalikan tuple (network_name, wallet_address).
    """
    evm = wallet_config.get("evm_address", "").strip()
    sol = wallet_config.get("solana_address", "").strip()

    if req.wallet_type == "SOLANA":
        return "SOLANA", sol
    elif req.wallet_type == "EVM":
        return "EVM", evm
    elif req.wallet_type == "BOTH":
        if evm and sol:
            return "BOTH", f"{evm}\n{sol}"
        return ("EVM", evm) if evm else ("SOLANA", sol)
    else:  # UNSPECIFIED
        unspec = wallet_config.get("unspecified_default", "EVM").upper()
        if unspec == "SOLANA":
            return "SOLANA", sol or evm
        elif unspec == "BOTH" and evm and sol:
            return "BOTH", f"{evm}\n{sol}"
        else:
            return "EVM", evm or sol

def compose_reply_text(req: AirdropRequirements, wallet_config: dict) -> tuple[str, str, str]:
    """
    Menyusun teks balasan khusus Drop Address:
    Mengembalikan (full_reply_text, network_used, address_used).
    """
    network_used, target_addr = determine_target_wallet(req, wallet_config)

    if not target_addr:
        return "", network_used, ""

    reply_mode = wallet_config.get("reply_mode", "smart")

    # Mode pure address atau host minta address only
    if reply_mode == "pure_address" or req.address_only_required:
        return target_addr, network_used, target_addr

    lines = [target_addr]

    # Tag teman jika diminta
    if req.requires_tag and wallet_config.get("tag_friends"):
        count = req.tag_count if req.tag_count > 0 else 3
        friends = wallet_config.get("tag_friends", [])
        tags = [f if f.startswith('@') else f"@{f}" for f in friends[:count]]
        if tags:
            lines.append(" ".join(tags))

    # Komentar pendukung
    if reply_mode == "full" or (reply_mode == "smart" and not req.requires_tag):
        comment = wallet_config.get("default_comment", "").strip()
        if comment:
            lines.append(comment)

    full_text = "\n".join(lines)
    if len(full_text) > 280:
        full_text = target_addr

    return full_text.strip(), network_used, target_addr

async def execute_airdrop_actions(
    client: Client,
    tweet_id: str,
    author_id: str,
    tweet_info: dict,
    req: AirdropRequirements,
    wallet_config: dict,
    step_callback: Optional[Callable[[str, bool, str], None]] = None,
    force_all_tasks: bool = True
) -> tuple[bool, list[str]]:
    """
    Eksekusi 4 tugas airdrop secara berurutan:
    1. Like tweet
    2. Retweet
    3. Follow akun pembuat & akun kolaborator yang dimention
    4. Kirim balasan Drop Address EVM / Solana sesuai kebutuhan tweet
    """
    actions_done = []
    delay_min = wallet_config.get("action_delay_min", 4)
    delay_max = wallet_config.get("action_delay_max", 9)

    # 1. LIKE
    do_like = (req.requires_like or force_all_tasks) and wallet_config.get("auto_like", True)
    if do_like:
        try:
            await client.favorite_tweet(tweet_id)
            actions_done.append("Like ❤️")
            if step_callback: step_callback("LIKE", True, "Liked ❤️")
            await asyncio.sleep(random.uniform(delay_min, delay_max))
        except TwitterException as e:
            if step_callback: step_callback("LIKE", False, str(e))
            logger.warning(f"Gagal like {tweet_id}: {e}")

    # 2. RETWEET
    do_rt = (req.requires_rt or force_all_tasks) and wallet_config.get("auto_retweet", True)
    if do_rt:
        try:
            await client.retweet(tweet_id)
            actions_done.append("Retweet 🔁")
            if step_callback: step_callback("RETWEET", True, "Retweeted 🔁")
            await asyncio.sleep(random.uniform(delay_min, delay_max))
        except TwitterException as e:
            if step_callback: step_callback("RETWEET", False, str(e))
            logger.warning(f"Gagal retweet {tweet_id}: {e}")

    # 3. FOLLOW (Author + Mentioned accounts)
    do_follow = (req.requires_follow or force_all_tasks) and wallet_config.get("auto_follow", True)
    if do_follow:
        followed_names = []
        if author_id:
            try:
                await client.follow_user(author_id)
                followed_names.append(f"@{tweet_info.get('username')}")
                await asyncio.sleep(random.uniform(delay_min, delay_max))
            except TwitterException as e:
                logger.warning(f"Gagal follow author: {e}")

        # Follow partner/kolaborator jika ada
        for mention in req.accounts_to_follow[:2]:
            if mention.lower() == tweet_info.get("username", "").lower():
                continue
            try:
                target_user = await client.get_user_by_screen_name(mention)
                if target_user and target_user.id:
                    await client.follow_user(target_user.id)
                    followed_names.append(f"@{mention}")
                    await asyncio.sleep(random.uniform(delay_min, delay_max))
            except Exception as e:
                logger.warning(f"Gagal follow @{mention}: {e}")

        if followed_names:
            msg = f"Follow {', '.join(followed_names)} 👤"
            actions_done.append(msg)
            if step_callback: step_callback("FOLLOW", True, msg)
        else:
            if step_callback: step_callback("FOLLOW", False, "Tidak ada akun di-follow")

    # 4. DROP WALLET / REPLY ADDRESS
    if wallet_config.get("auto_reply_wallet", True):
        reply_body, net_used, addr_used = compose_reply_text(req, wallet_config)
        if reply_body:
            try:
                await client.create_tweet(text=reply_body, reply_to=tweet_id)
                drop_msg = f"Drop {net_used} ({addr_used[:6]}...{addr_used[-4:] if len(addr_used) > 10 else ''}) 👛"
                actions_done.append(drop_msg)
                if step_callback: step_callback("DROP_WALLET", True, drop_msg)
                await asyncio.sleep(random.uniform(delay_min, delay_max))
            except DuplicateTweet:
                if step_callback: step_callback("DROP_WALLET", False, "Reply terdeteksi duplikat")
            except TwitterException as e:
                if step_callback: step_callback("DROP_WALLET", False, str(e))
                logger.warning(f"Gagal kirim reply: {e}")
        else:
            if step_callback: step_callback("DROP_WALLET", False, f"Alamat {net_used} belum disetting")

    success = len(actions_done) > 0
    if success:
        record_entry(tweet_id, tweet_info, actions_done)

    return success, actions_done
