import json
import re
from pathlib import Path
from config import BASE_DIR

WALLET_CONFIG_FILE = BASE_DIR / "wallets.json"

DEFAULT_WALLET_CONFIG = {
    "evm_address": "",           # Alamat 0x... (Metamask/TrustWallet)
    "solana_address": "",        # Alamat Base58 (Phantom/Solflare)
    "tag_friends": [],           # List username teman, contoh: ["@crypto_bro", "@airdrop_hunter"]
    "default_comment": "",
    "reply_mode": "pure_address",       # Pilihan: 'pure_address', 'smart', 'full'
    "unspecified_default": "EVM",# Pilihan: 'EVM', 'SOLANA', atau 'BOTH' jika host tidak menyebutkan jaringan
    "auto_like": True,
    "auto_retweet": True,
    "auto_follow": True,
    "auto_reply_wallet": True,
    "action_delay_min": 6,       # Jeda minimal antar aksi (detik)
    "action_delay_max": 14       # Jeda maksimal antar aksi (detik)
}

def is_valid_evm_address(address: str) -> bool:
    """Validasi format alamat EVM (0x diikuti 40 karakter heksadesimal)."""
    if not address:
        return False
    return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address.strip()))

def is_valid_solana_address(address: str) -> bool:
    """Validasi format alamat Solana (Base58, panjang 32-44 karakter)."""
    if not address:
        return False
    return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address.strip()))

def load_wallet_config() -> dict:
    """Memuat konfigurasi wallet dan preferensi airdrop."""
    if not WALLET_CONFIG_FILE.exists():
        save_wallet_config(DEFAULT_WALLET_CONFIG)
        return DEFAULT_WALLET_CONFIG.copy()

    try:
        with open(WALLET_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_WALLET_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_WALLET_CONFIG.copy()

def save_wallet_config(config: dict) -> None:
    """Menyimpan konfigurasi wallet ke wallets.json."""
    with open(WALLET_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
