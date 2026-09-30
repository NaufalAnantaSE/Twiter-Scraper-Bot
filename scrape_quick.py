import argparse
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from auth import init_client, load_existing_session
from scraper import (
    scrape_tweets_by_keyword,
    scrape_airdrop_giveaways,
    scrape_user_timeline,
    scrape_tweet_detail_and_replies
)
from exporter import export_data, export_single_tweet_with_replies
from wallet_config import load_wallet_config
from airdrop_actions import execute_airdrop_actions, is_already_entered

async def run():
    parser = argparse.ArgumentParser(description="Twitter / X Scraper & Airdrop Hunter CLI Runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--airdrop", type=str, choices=["all", "evm", "solana"], help="Scrape event airdrop/giveaway (all, evm, solana)")
    group.add_argument("-s", "--search", type=str, help="Cari tweet berdasarkan keyword atau hashtag umum")
    group.add_argument("-u", "--user", type=str, help="Scrape tweet dari profil akun tertentu (username)")
    group.add_argument("-t", "--tweet", type=str, help="Scrape 1 tweet dan replies berdasarkan URL atau Tweet ID")

    parser.add_argument("--filter", type=str, choices=["Latest", "Top"], default="Latest", help="Filter pencarian: Latest (default) atau Top")
    parser.add_argument("--type", type=str, choices=["Tweets", "Replies", "Media"], default="Tweets", help="Tipe timeline user: Tweets (default), Replies, Media")
    parser.add_argument("-m", "--max", type=int, default=20, help="Jumlah maksimal tweet yang diambil (default: 20)")
    parser.add_argument("--auto-enter", action="store_true", help="Otomatis eksekusi Like, RT, Follow, dan Drop Wallet ke airdrop yang ditemukan")

    args = parser.parse_args()

    client = await init_client()
    user_info = await load_existing_session(client)
    if not user_info:
        print("[ERROR] File cookies.json tidak ditemukan atau sesi kadaluarsa.")
        print("Silakan jalankan 'python main.py' terlebih dahulu untuk login/setup cookie.")
        sys.exit(1)

    print(f"[*] Terhubung sebagai @{user_info['screen_name']}")

    if args.airdrop:
        print(f"[*] Mencari giveaway airdrop ({args.airdrop.upper()}, Max: {args.max})...")
        tweets = await scrape_airdrop_giveaways(client, category=args.airdrop.upper(), max_tweets=args.max)
        if tweets:
            csv_path, json_path = export_data(tweets, prefix=f"airdrop_{args.airdrop}")
            print(f"[+] Ditemukan {len(tweets)} tweets.")
            print(f"[+] CSV  : {csv_path}")
            print(f"[+] JSON : {json_path}")

            if args.auto_enter:
                wallet_cfg = load_wallet_config()
                print("[*] Menjalankan Auto-Enter ke giveaway baru...")
                count = 0
                for t in tweets:
                    tid = t["tweet_id"]
                    if is_already_entered(tid):
                        continue
                    req = t.get("_airdrop_req")
                    ok, done = await execute_airdrop_actions(client, tid, t.get("user_id"), t, req, wallet_cfg)
                    if ok:
                        count += 1
                        print(f"  [✓] @{t['username']}: {', '.join(done)}")
                print(f"[+] Selesai! Berhasil mengikuti {count} airdrop.")
        else:
            print("[-] Tidak ada giveaway yang ditemukan.")

    elif args.search:
        print(f"[*] Mencari tweet untuk query: '{args.search}' (Filter: {args.filter}, Max: {args.max})...")
        tweets = await scrape_tweets_by_keyword(client, query=args.search, product=args.filter, max_tweets=args.max)
        if tweets:
            csv_path, json_path = export_data(tweets, prefix=f"search_{args.search}")
            print(f"[+] Berhasil mengambil {len(tweets)} tweets.")
            print(f"[+] CSV  : {csv_path}")
            print(f"[+] JSON : {json_path}")
        else:
            print("[-] Tidak ada tweet yang ditemukan.")

    elif args.user:
        clean_user = args.user.lstrip("@")
        print(f"[*] Mengambil timeline @{clean_user} (Type: {args.type}, Max: {args.max})...")
        info, tweets = await scrape_user_timeline(client, username=clean_user, tweet_type=args.type, max_tweets=args.max)
        print(f"[+] User: @{info['screen_name']} ({info['followers_count']:,} followers)")
        if tweets:
            csv_path, json_path = export_data(tweets, prefix=f"user_{clean_user}_{args.type.lower()}")
            print(f"[+] Berhasil mengambil {len(tweets)} tweets.")
            print(f"[+] CSV  : {csv_path}")
            print(f"[+] JSON : {json_path}")
        else:
            print("[-] Tidak ada postingan yang ditemukan.")

    elif args.tweet:
        print(f"[*] Mengambil tweet dan replies: {args.tweet} (Max replies: {args.max})...")
        main_tweet, replies = await scrape_tweet_detail_and_replies(client, tweet_id_or_url=args.tweet, max_replies=args.max)
        csv_path, json_path = export_single_tweet_with_replies(main_tweet, replies, main_tweet['tweet_id'])
        print(f"[+] Tweet utama: {main_tweet['text'][:80]}...")
        print(f"[+] Total replies diambil: {len(replies)}")
        print(f"[+] CSV  : {csv_path}")
        print(f"[+] JSON : {json_path}")

if __name__ == "__main__":
    asyncio.run(run())
