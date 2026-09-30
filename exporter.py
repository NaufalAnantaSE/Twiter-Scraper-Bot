import csv
import json
import re
from datetime import datetime
from pathlib import Path
from config import RESULTS_DIR

def sanitize_filename(name: str) -> str:
    """Membersihkan karakter ilegal untuk nama file di Windows."""
    clean = re.sub(r'[\\/*?:"<>|#@\s]+', '_', name)
    return clean[:40].strip('_')

def export_data(data: list[dict], prefix: str = "twitter_data") -> tuple[str, str]:
    """
    Mengekspor list dictionary ke format CSV dan JSON sekaligus.
    Mengabaikan key internal yang diawali tanda underscore '_'.
    Mengembalikan path (csv_path, json_path).
    """
    if not data:
        return "", ""

    clean_data = [{k: v for k, v in item.items() if not k.startswith('_')} for item in data]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_prefix = sanitize_filename(prefix)
    base_name = f"{clean_prefix}_{timestamp}"

    csv_path = RESULTS_DIR / f"{base_name}.csv"
    json_path = RESULTS_DIR / f"{base_name}.json"

    # Export ke CSV (utf-8-sig agar kompatibel dengan Microsoft Excel di Windows)
    fieldnames = list(clean_data[0].keys())
    with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_data)

    # Export ke JSON
    with open(json_path, mode="w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    return str(csv_path), str(json_path)

def export_single_tweet_with_replies(main_tweet: dict, replies: list[dict], tweet_id: str) -> tuple[str, str]:
    """Ekspor detail 1 tweet beserta semua replies-nya."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"tweet_{tweet_id}_replies_{timestamp}"

    csv_path = RESULTS_DIR / f"{base_name}.csv"
    json_path = RESULTS_DIR / f"{base_name}.json"

    clean_main = {k: v for k, v in main_tweet.items() if not k.startswith('_')}
    clean_replies = [{k: v for k, v in item.items() if not k.startswith('_')} for item in replies]
    all_data = [clean_main] + clean_replies

    fieldnames = list(clean_main.keys())
    with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)

    full_structure = {
        "tweet": clean_main,
        "replies_count": len(clean_replies),
        "replies": clean_replies
    }
    with open(json_path, mode="w", encoding="utf-8") as f:
        json.dump(full_structure, f, ensure_ascii=False, indent=2)

    return str(csv_path), str(json_path)
