import json
import logging
from pathlib import Path
from twikit import Client
from twikit.errors import Unauthorized, TwitterException
from config import COOKIES_FILE, LANGUAGE

logger = logging.getLogger(__name__)

async def verify_client(client: Client) -> dict | None:
    """
    Memverifikasi apakah cookie yang ada masih valid dengan mengambil profil user.
    Mengembalikan dict user info jika valid, atau None jika tidak valid.
    """
    try:
        user = await client.user()
        return {
            "id": user.id,
            "name": user.name,
            "screen_name": user.screen_name,
            "followers_count": user.followers_count
        }
    except Unauthorized:
        return None
    except Exception as e:
        logger.warning(f"Gagal verifikasi session: {e}")
        return None

async def init_client() -> Client:
    """Inisialisasi Client Twikit."""
    return Client(LANGUAGE)

async def load_existing_session(client: Client) -> dict | None:
    """
    Mencoba memuat cookies dari cookies.json jika ada.
    Mengembalikan data user jika valid, atau None.
    """
    if not COOKIES_FILE.exists():
        return None

    try:
        client.load_cookies(str(COOKIES_FILE))
        user_info = await verify_client(client)
        return user_info
    except Exception as e:
        logger.error(f"Error memuat file cookies: {e}")
        return None

async def save_cookies_from_tokens(client: Client, auth_token: str, ct0: str) -> dict | None:
    """
    Menyimpan cookie dari auth_token dan ct0 (didapat dari DevTools browser).
    Ini metode paling stabil karena terhindar dari CAPTCHA / 2FA login prompt.
    """
    auth_token = auth_token.strip().replace('"', '').replace("'", "")
    ct0 = ct0.strip().replace('"', '').replace("'", "")

    cookies = {
        "auth_token": auth_token,
        "ct0": ct0
    }

    client.set_cookies(cookies)
    user_info = await verify_client(client)

    if user_info:
        # Simpan ke cookies.json
        client.save_cookies(str(COOKIES_FILE))
        return user_info
    else:
        return None

async def login_with_credentials(client: Client, username: str, email: str, password: str, totp_secret: str = None) -> dict | None:
    """
    Login otomatis menggunakan kredensial akun Twitter.
    """
    try:
        await client.login(
            auth_info_1=username.strip(),
            auth_info_2=email.strip() if email else None,
            password=password.strip(),
            totp_secret=totp_secret.strip() if totp_secret else None
        )
        client.save_cookies(str(COOKIES_FILE))
        user_info = await verify_client(client)
        return user_info
    except TwitterException as e:
        logger.error(f"Twitter login error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise
