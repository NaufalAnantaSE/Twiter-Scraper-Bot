import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
COOKIES_FILE = BASE_DIR / "cookies.json"
ACCOUNTS_FILE = BASE_DIR / "accounts.json"

# Buat folder results jika belum ada
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Delay antar request (detik) untuk meminimalisir risiko rate limit
DEFAULT_DELAY_MIN = 1.5
DEFAULT_DELAY_MAX = 3.0

# User agent language
LANGUAGE = "en-US"
