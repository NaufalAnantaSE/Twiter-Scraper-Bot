import asyncio
import random
import logging
from typing import Callable, Optional
from twikit import Client
from twikit.errors import TooManyRequests, TwitterException, UserNotFound, TweetNotAvailable
from config import DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX
from airdrop_parser import analyze_airdrop_tweet

logger = logging.getLogger(__name__)

def tweet_to_dict(tweet) -> dict:
    """Konversi objek twikit.Tweet ke dictionary dengan analisis mendalam Drop Address EVM / Solana."""
    user = getattr(tweet, 'user', None)
    username = getattr(user, 'screen_name', '') if user else ''
    name = getattr(user, 'name', '') if user else ''
    user_id = getattr(user, 'id', '') if user else ''

    media_urls = []
    if hasattr(tweet, 'media') and tweet.media:
        for m in tweet.media:
            if hasattr(m, 'media_url') and m.media_url:
                media_urls.append(m.media_url)

    created_at_str = ""
    try:
        if hasattr(tweet, 'created_at_datetime') and tweet.created_at_datetime:
            created_at_str = tweet.created_at_datetime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at_str = str(getattr(tweet, 'created_at', ''))
    except Exception:
        created_at_str = str(getattr(tweet, 'created_at', ''))

    tweet_id = str(getattr(tweet, 'id', ''))
    url = f"https://x.com/{username}/status/{tweet_id}" if username else f"https://x.com/i/web/status/{tweet_id}"
    full_text = getattr(tweet, 'full_text', None) or getattr(tweet, 'text', '') or ''

    # Analisis persyaratan Drop Address
    req = analyze_airdrop_tweet(full_text, username)

    return {
        "tweet_id": tweet_id,
        "url": url,
        "created_at": created_at_str,
        "username": username,
        "name": name,
        "user_id": str(user_id),
        "text": full_text,
        "reply_count": getattr(tweet, 'reply_count', 0) or 0,
        "retweet_count": getattr(tweet, 'retweet_count', 0) or 0,
        "favorite_count": getattr(tweet, 'favorite_count', 0) or 0,
        "view_count": getattr(tweet, 'view_count', 0) or 0,
        "quote_count": getattr(tweet, 'quote_count', 0) or 0,
        "bookmark_count": getattr(tweet, 'bookmark_count', 0) or 0,
        "hashtags": ", ".join(getattr(tweet, 'hashtags', []) or []),
        "media_urls": " ; ".join(media_urls),
        "lang": getattr(tweet, 'lang', '') or '',
        "in_reply_to": str(getattr(tweet, 'in_reply_to', '') or ''),
        # Field khusus Drop Address
        "is_wallet_drop": req.is_wallet_drop,
        "wallet_type": req.wallet_type or "",
        "address_only_required": req.address_only_required,
        "reward": req.reward,
        "req_like": req.requires_like,
        "req_rt": req.requires_rt,
        "req_follow": req.requires_follow,
        "accounts_to_follow": ", ".join(req.accounts_to_follow),
        "req_tag": req.requires_tag,
        "tag_count": req.tag_count,
        "summary_label": req.summary_label,
        "_airdrop_req": req
    }

async def scrape_tweets_by_keyword(
    client: Client,
    query: str,
    product: str = "Latest",
    max_tweets: int = 50,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> list[dict]:
    """Pencarian tweet umum dengan pagination dan anti-bot delay."""
    results = []
    seen_ids = set()

    try:
        batch = await client.search_tweet(query=query, product=product, count=20)
    except TooManyRequests:
        logger.warning("Rate limit tercapai saat request pertama.")
        return results
    except Exception as e:
        logger.error(f"Gagal mencari tweet: {e}")
        raise

    while batch and len(results) < max_tweets:
        new_items = 0
        for tweet in batch:
            if tweet.id not in seen_ids:
                seen_ids.add(tweet.id)
                results.append(tweet_to_dict(tweet))
                new_items += 1
                if progress_callback:
                    progress_callback(len(results), max_tweets)
                if len(results) >= max_tweets:
                    break

        if len(results) >= max_tweets or new_items == 0:
            break

        delay = random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX)
        await asyncio.sleep(delay)

        try:
            batch = await batch.next()
            if not batch or len(batch) == 0:
                break
        except TooManyRequests:
            logger.warning("Rate limit tercapai saat pagination.")
            break
        except Exception as e:
            logger.warning(f"Error pagination: {e}")
            break

    return results

async def scrape_airdrop_giveaways(
    client: Client,
    category: str = "ALL",  # "EVM", "SOLANA", "ALL"
    max_tweets: int = 30,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> list[dict]:
    """
    Pencarian khusus tweet 'Drop Address' EVM / Solana dengan query presisi tinggi.
    Menyingkirkan reply orang lain (-filter:replies) dan retweet (-filter:retweets).
    """
    cat = category.upper()
    if cat == "EVM":
        query = '("drop your 0x" OR "drop 0x" OR "drop your evm" OR "drop evm" OR "drop your eth" OR "drop your metamask" OR "drop your bsc") (RT OR Retweet OR Like) -filter:replies -filter:retweets'
    elif cat == "SOLANA":
        query = '("drop your sol" OR "drop sol" OR "drop your solana" OR "drop solana" OR "drop your phantom" OR "drop phantom") (RT OR Retweet OR Like) -filter:replies -filter:retweets'
    else:
        query = '("drop your 0x" OR "drop 0x" OR "drop your sol" OR "drop sol" OR "drop your address" OR "drop your wallet" OR "drop address below" OR "drop wallet below") (RT OR Retweet OR Like) -filter:replies -filter:retweets'

    raw_results = await scrape_tweets_by_keyword(
        client=client,
        query=query,
        product="Latest",
        max_tweets=max_tweets * 2,  # Ambil cadangan untuk filter kualitas
        progress_callback=progress_callback
    )

    # Prioritaskan tweet yang terbukti meminta drop address
    filtered = []
    for t in raw_results:
        req = t.get("_airdrop_req")
        if req and req.is_wallet_drop:
            filtered.append(t)
        if len(filtered) >= max_tweets:
            break

    # Jika hasil filter sedikit, sertakan juga hasil relevan lainnya
    if len(filtered) < max_tweets:
        for t in raw_results:
            if t not in filtered:
                filtered.append(t)
            if len(filtered) >= max_tweets:
                break

    return filtered

async def scrape_user_timeline(
    client: Client,
    username: str,
    tweet_type: str = "Tweets",
    max_tweets: int = 50,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> tuple[dict, list[dict]]:
    """Scrape timeline profil user."""
    clean_username = username.strip().lstrip('@')

    try:
        user = await client.get_user_by_screen_name(clean_username)
    except UserNotFound:
        raise ValueError(f"Akun @{clean_username} tidak ditemukan.")
    except Exception as e:
        raise RuntimeError(f"Gagal mengambil profil @{clean_username}: {e}")

    user_info = {
        "id": user.id,
        "name": user.name,
        "screen_name": user.screen_name,
        "description": user.description,
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "statuses_count": user.statuses_count,
        "verified": user.verified or user.is_blue_verified
    }

    results = []
    seen_ids = set()

    try:
        batch = await client.get_user_tweets(user.id, tweet_type=tweet_type, count=20)
    except TooManyRequests:
        logger.warning("Rate limit tercapai saat request pertama.")
        return user_info, results
    except Exception as e:
        logger.error(f"Gagal mengambil timeline: {e}")
        raise

    while batch and len(results) < max_tweets:
        new_items = 0
        for tweet in batch:
            if tweet.id not in seen_ids:
                seen_ids.add(tweet.id)
                results.append(tweet_to_dict(tweet))
                new_items += 1
                if progress_callback:
                    progress_callback(len(results), max_tweets)
                if len(results) >= max_tweets:
                    break

        if len(results) >= max_tweets or new_items == 0:
            break

        delay = random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX)
        await asyncio.sleep(delay)

        try:
            batch = await batch.next()
            if not batch or len(batch) == 0:
                break
        except TooManyRequests:
            logger.warning("Rate limit tercapai saat pagination.")
            break
        except Exception as e:
            logger.warning(f"Error pagination: {e}")
            break

    return user_info, results

async def scrape_tweet_detail_and_replies(
    client: Client,
    tweet_id_or_url: str,
    max_replies: int = 30,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> tuple[dict, list[dict]]:
    """Scrape detail tweet beserta komentar / replies-nya."""
    tweet_id = tweet_id_or_url.strip().split("?")[0].rstrip("/").split("/")[-1]

    try:
        tweet = await client.get_tweet_by_id(tweet_id)
    except TweetNotAvailable:
        raise ValueError(f"Tweet {tweet_id} tidak ditemukan atau privat.")
    except Exception as e:
        raise RuntimeError(f"Gagal mengambil detail tweet: {e}")

    main_tweet_data = tweet_to_dict(tweet)
    replies_data = []
    seen_ids = set()

    replies = tweet.replies
    while replies and len(replies_data) < max_replies:
        new_items = 0
        for reply in replies:
            if reply.id not in seen_ids and reply.id != tweet.id:
                seen_ids.add(reply.id)
                replies_data.append(tweet_to_dict(reply))
                new_items += 1
                if progress_callback:
                    progress_callback(len(replies_data), max_replies)
                if len(replies_data) >= max_replies:
                    break

        if len(replies_data) >= max_replies or new_items == 0:
            break

        delay = random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX)
        await asyncio.sleep(delay)

        try:
            replies = await replies.next()
            if not replies or len(replies) == 0:
                break
        except TooManyRequests:
            break
        except Exception as e:
            logger.warning(f"Error pagination replies: {e}")
            break

    return main_tweet_data, replies_data
