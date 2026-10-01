import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class AirdropRequirements:
    is_giveaway: bool
    is_wallet_drop: bool            # Apakah tweet secara spesifik meminta drop address/wallet
    address_only_required: bool     # Apakah host meminta HANYA alamat saja tanpa teks/comment
    reward: str
    requires_like: bool
    requires_rt: bool
    requires_follow: bool
    accounts_to_follow: list[str]
    requires_tag: bool
    tag_count: int
    requires_wallet: bool
    wallet_type: Optional[str]      # 'EVM', 'SOLANA', 'BOTH', 'UNSPECIFIED', or None
    summary_label: str

def parse_reward(text: str) -> str:
    """Ekstrak estimasi reward (misal: 500 $USDT, 10 SOL, WL Spot)."""
    patterns = [
        r'\$\s*\d+[\d,]*(?:\.\d+)?(?:\s*(?:USDT|USDC|USD|SOL|ETH|BNB))?',
        r'\d+[\d,]*(?:\.\d+)?\s*(?:\$|USDT|USDC|SOL|ETH|BNB|MATIC|TON)\b',
        r'\d+x?\s*(?:WL|Whitelist|Spot|NFT|Pass)\b'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return "Reward Giveaway"

def parse_tag_count(text: str) -> int:
    """Deteksi jumlah tag teman yang diminta."""
    match = re.search(r'tag\s+(\d+)\s*(?:friends|buddies|people|frens|pals|mates)?', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    if re.search(r'\btag\b', text, re.IGNORECASE):
        return 3
    return 0

def is_genuine_giveaway_drop(text: str) -> tuple[bool, str]:
    """
    Memvalidasi secara ketat apakah sebuah tweet benar-benar merupakan postingan
    giveaway atau ajakan drop wallet yang sah.
    Mencegah tweet diskusi umum, filosofis, opini, promosi token, atau anti-scam terdeteksi sebagai giveaway.
    """
    clean_text = text.strip()
    if len(clean_text) < 15:
        return False, "Teks terlalu pendek"

    # 1. Negative guard: Tweet peringatan/anti-scam agar tidak direspons
    anti_scam_pattern = r'\b(never|don\'?t|do\s+not|scam|warning|beware|hacked)\s+(drop|send|share|give)\s+(your\s+)?(wallet|address|seed|key|money)\b'
    if re.search(anti_scam_pattern, clean_text, re.IGNORECASE):
        return False, "Bukan giveaway (tweet peringatan scam)"

    # 2. Pola ajakan drop wallet eksplisit
    explicit_drop_patterns = [
        (r'\b(drop|comment|leave|send|reply\s+with)\s+(your\s+)?([a-z0-9$]+\s+)?(address|addresses|wallet|wallets|addr|addrs|addy|addies|0x|sol|solana|eth|phantom|metamask)\b', "Drop Wallet Direct"),
        (r'\b(drop\s+(your\s+)?(0x|sol|solana|eth|\$sol|\$eth|\$usdt|address|addresses|wallet|wallets|addy|addies))\b', "Drop Token/Chain"),
        (r'\b(address|addresses|wallet|wallets|0x|sol|addy|addies)\s+(below|here|down\s+below|in\s+comments|in\s+the\s+comments)\b', "Wallet Location Below"),
        (r'\bdrop\s+your\s+(evm|erc20|bep20|spl)\b', "Drop Chain Type"),
        (r'\b(every\s+(wallet|address)\s+gets|first\s+\d+\s+(wallets|addresses))\b', "Batch Distribution"),
        (r'\b(send\s+(some\s+)?(\$sol|\$eth|sol|eth))\s+to\s+(first|\d+|wallets|addresses)\b', "Sending Crypto Distribution"),
        (r'\b(sending\s+some\s+(\$sol|\$eth|sol|eth))\b', "Sending Crypto"),
        (r'\b(who\s+needs\s+(\$sol|\$eth|\$usdt))\b.*(drop|wallet|wallets|address)', "Who Needs Crypto Drop"),
        (r'\b(dropping\s+(\$sol|\$eth|\$usdt|some\s+sol|some\s+eth))\b', "Dropping Crypto")
    ]

    for p, label in explicit_drop_patterns:
        if re.search(p, clean_text, re.IGNORECASE):
            return True, f"Valid ({label})"

    # 3. Kombinasi kata Giveaway/Airdrop + Kata Kunci Dompet
    giveaway_words = r'\b(giveaway|airdrop|giving\s+away|prize\s+pool|raffle)\b'
    wallet_words = r'\b(wallet|address|addy|addr|0x|\$sol|\$eth|phantom|metamask|drop)\b'

    has_giveaway = bool(re.search(giveaway_words, clean_text, re.IGNORECASE))
    has_wallet = bool(re.search(wallet_words, clean_text, re.IGNORECASE))

    if has_giveaway and has_wallet:
        return True, "Valid (Giveaway + Wallet Keyword)"

    return False, "Bukan giveaway / drop wallet (tidak ada pola drop address atau distribusi reward)"


def analyze_airdrop_tweet(text: str, author_username: str = "") -> AirdropRequirements:
    """
    Menganalisis teks tweet dengan fokus utama pada Drop Address EVM / Solana.
    Mendeteksi:
    - Apakah tweet meminta drop address?
    - Apakah meminta jaringan EVM (0x) atau Solana (SOL)?
    - Apakah meminta HANYA alamat tanpa teks tambahan?
    - Syarat Like, RT, Follow akun siapa saja, dan Tag teman.
    """
    clean_text = text.strip()

    # Cek keabsahan giveaway secara ketat
    is_valid_ga, _ = is_genuine_giveaway_drop(clean_text)

    # 1. Deteksi spesifik "Drop Address / Drop Wallet"
    drop_patterns = [
        r'\b(drop|comment|leave|send|reply\s+with)\s+(your\s+)?([a-z0-9$]+\s+)?(address|addresses|wallet|wallets|addr|addrs|addy|addies|0x|sol|solana|eth|phantom|metamask)\b',
        r'\b(drop\s+(your\s+)?(0x|sol|solana|eth|\$sol|\$eth|\$usdt|address|addresses|wallet|wallets|addy|addies))\b',
        r'\b(address|addresses|wallet|wallets|0x|sol|addy|addies)\s+(below|here|down\s+below|in\s+comments|in\s+the\s+comments)\b',
        r'\bdrop\s+your\s+(evm|erc20|bep20|spl)\b',
        r'\b(every\s+(wallet|address)\s+gets|first\s+\d+\s+(wallets|addresses))\b',
        r'\b(send\s+(some\s+)?(\$sol|\$eth|sol|eth))\s+to\s+(first|\d+|wallets|addresses)\b',
        r'\b(sending\s+some\s+(\$sol|\$eth|sol|eth))\b',
        r'\b(who\s+needs\s+(\$sol|\$eth|\$usdt))\b.*(drop|wallet|wallets|address)',
        r'\b(dropping\s+(\$sol|\$eth|\$usdt|some\s+sol|some\s+eth))\b'
    ]
    is_wallet_drop = is_valid_ga and any(re.search(p, clean_text, re.IGNORECASE) for p in drop_patterns)

    # Deteksi umum giveaway
    giveaway_keywords = [
        r'\bgiveaway\b', r'\bairdrop\b', r'\bwhitelist\b', r'\bwl\s+spot\b',
        r'\bgiving\s+away\b', r'\bwinner\b', r'\bfree\s+mint\b', r'\bprize\s+pool\b'
    ]
    is_giveaway = is_valid_ga and (is_wallet_drop or any(re.search(kw, clean_text, re.IGNORECASE) for kw in giveaway_keywords))

    # 2. Deteksi apakah host meminta HANYA alamat saja tanpa teks/komentar
    # (Banyak bot checker giveaway mendiskualifikasi pemenang jika ada teks selain alamat)
    address_only_patterns = [
        r'\b(address\s+only|wallet\s+only|0x\s+only|sol\s+only|addy\s+only)\b',
        r'\b(only\s+address|only\s+wallet|only\s+0x|only\s+sol|only\s+addy)\b',
        r'\b(no\s+text|just\s+address|just\s+wallet|just\s+your\s+address|just\s+addy)\b'
    ]
    address_only_required = any(re.search(p, clean_text, re.IGNORECASE) for p in address_only_patterns)

    # 3. Cek Syarat Like & RT
    requires_like = bool(re.search(r'\b(like|fav|heart|❤️|drop a like)\b', clean_text, re.IGNORECASE))
    requires_rt = bool(re.search(r'\b(rt|retweet|repost|🔁|quote)\b', clean_text, re.IGNORECASE))

    # 4. Cek Syarat Follow & Ekstrak semua @mention yang wajib di-follow
    requires_follow = bool(re.search(r'\b(follow|flw|ikuti|foll)\b', clean_text, re.IGNORECASE))
    raw_mentions = re.findall(r'@([A-Za-z0-9_]{1,15})', clean_text)
    accounts_to_follow = []

    clean_author = author_username.strip().lstrip('@')
    if clean_author:
        accounts_to_follow.append(clean_author)

    for m in raw_mentions:
        if m.lower() not in [acc.lower() for acc in accounts_to_follow]:
            accounts_to_follow.append(m)

    if not requires_follow and accounts_to_follow and is_wallet_drop:
        # Jika ada mention akun lain di tweet giveaway, biasanya tetap harus difollow
        requires_follow = True

    # 5. Cek Syarat Tag Teman
    tag_count = parse_tag_count(clean_text)
    requires_tag = tag_count > 0 and not address_only_required

    # 6. Klasifikasi Jaringan: EVM vs SOLANA
    # EVM keywords: 0x, evm, eth, ethereum, erc20, metamask, bsc, bnb, base, arb, arbitrum, polygon, matic
    is_evm = bool(re.search(r'\b(evm|0x|eth|ethereum|\$eth|erc20|metamask|bsc|bnb|polygon|matic|arbitrum|arb|base|optimism|avax|bep20)\b', clean_text, re.IGNORECASE))
    # Solana keywords: sol, solana, phantom, backpack, spl
    is_sol = bool(re.search(r'\b(sol|solana|\$sol|phantom|backpack|spl)\b', clean_text, re.IGNORECASE))

    requires_wallet = is_wallet_drop or is_evm or is_sol
    wallet_type = None

    if is_evm and is_sol:
        wallet_type = "BOTH"
    elif is_sol:
        wallet_type = "SOLANA"
    elif is_evm:
        wallet_type = "EVM"
    elif is_wallet_drop:
        wallet_type = "UNSPECIFIED"

    reward = parse_reward(clean_text)

    # Label ringkasan untuk tampilan UI
    labels = []
    if is_wallet_drop:
        labels.append(f"👛 Drop {wallet_type or 'Wallet'}")
    if address_only_required:
        labels.append("⚠️ Address Only")
    if requires_like:
        labels.append("❤️ Like")
    if requires_rt:
        labels.append("🔁 RT")
    if requires_follow:
        labels.append(f"👤 Follow ({len(accounts_to_follow)})")
    if requires_tag:
        labels.append(f"🏷️ Tag {tag_count}")

    summary_label = " | ".join(labels) if labels else "Info / Event"

    return AirdropRequirements(
        is_giveaway=is_giveaway,
        is_wallet_drop=is_wallet_drop,
        address_only_required=address_only_required,
        reward=reward,
        requires_like=requires_like,
        requires_rt=requires_rt,
        requires_follow=requires_follow,
        accounts_to_follow=accounts_to_follow,
        requires_tag=requires_tag,
        tag_count=tag_count,
        requires_wallet=requires_wallet,
        wallet_type=wallet_type,
        summary_label=summary_label
    )
