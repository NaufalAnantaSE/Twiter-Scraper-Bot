import random
import sys
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Koleksi template komponen untuk menghasilkan tweet giveaway unik & natural
# Mencegah deteksi spam/duplicate oleh Twitter

HOOKS = [
    "🎁 $AMOUNT $SOL GIVEAWAY 🎁",
    "⚡ FLASH GIVEAWAY: $AMOUNT IN $SOL ⚡",
    "🚀 $AMOUNT $SOL TO $WINNERS WINNERS 🚀",
    "💎 SPECIAL AIRDROP: $AMOUNT IN $SOL 💎",
    "🔥 GIVING AWAY $AMOUNT IN $SOL TODAY 🔥",
    "💰 $AMOUNT SOLANA COMMUNITY GIVEAWAY 💰",
    "🌟 WEEKEND SPECIAL: $AMOUNT $SOL GIVEAWAY 🌟",
    "🚨 QUICK $AMOUNT $SOL AIRDROP 🚨",
    "✨ SENDING $AMOUNT $SOL TO MY FOLLOWERS ✨"
]

RULES_TEMPLATES = [
    [
        "1. Follow @{username}",
        "2. Like & Repost (RT)",
        "3. Drop your $SOL wallet address 👇"
    ],
    [
        "• Follow @{username}",
        "• Like & Retweet this post",
        "• Drop your Solana / Phantom address below 💳"
    ],
    [
        "➜ Follow @{username} 👤",
        "➜ Like + RT 🔁",
        "➜ Comment your $SOL address 👛",
        "➜ Turn notifications ON 🔔"
    ],
    [
        "✅ Follow @{username}",
        "✅ RT & Like",
        "✅ Drop your $SOL addy"
    ],
    [
        "1️⃣ Follow @{username}",
        "2️⃣ Retweet & Like ❤️",
        "3️⃣ Drop your SOLANA address below 👇"
    ]
]

CLOSINGS = [
    "⏱️ Picking winners in $HOURS hours! Good luck! 🍀",
    "⏰ Ends in $HOURS Hours. Don't miss out! 🚀",
    "🔔 Turn on post notifications! Winners in $HOURS H. 🏆",
    "⏳ 24 Hours only! Drop your address now! 💥",
    "🎉 Winners announced right here in $HOURS hours! 🥳",
    "🍀 Good luck everyone! Check notifications! 🚀"
]

HASHTAGS = [
    "#Solana #Airdrop #Giveaway #SOL #SolanaGiveaway",
    "#Solana #Crypto #Giveaway #Airdrop #Memecoin",
    "#SOL #SolanaCommunity #CryptoAirdrop #Giveaway",
    "#Solana #GiveawayAlert #Airdrop #CryptoGiveaway",
    "#SOL #SolanaGiveaway #Crypto #SolanaSummer"
]

AMOUNTS = ["$50", "$100", "$150", "$200", "$250", "$500"]
WINNERS = ["2", "3", "5", "10"]
HOURS = ["12", "24", "48"]

def generate_solana_giveaway(username: str = "fannettt", custom_amount: Optional[str] = None) -> str:
    amount = custom_amount or random.choice(AMOUNTS)
    winners = random.choice(WINNERS)
    duration = random.choice(HOURS)
    
    # Pilih hook & ganti placeholder
    hook = random.choice(HOOKS).replace("$AMOUNT", amount).replace("$WINNERS", winners)
    
    # Pilih rules
    rules_pattern = random.choice(RULES_TEMPLATES)
    rules_text = "\n".join([r.format(username=username) for r in rules_pattern])
    
    # Pilih closing
    closing = random.choice(CLOSINGS).replace("$HOURS", duration)
    
    # Pilih hashtag
    hashtags = random.choice(HASHTAGS)
    
    tweet = f"{hook}\n\n{rules_text}\n\n{closing}\n\n{hashtags}"
    return tweet

def generate_evm_giveaway(username: str = "fannettt", custom_amount: Optional[str] = None) -> str:
    amount = custom_amount or random.choice(AMOUNTS)
    winners = random.choice(WINNERS)
    duration = random.choice(HOURS)

    hook = f"🎁 {amount} $ETH / EVM GIVEAWAY 🎁"
    rules = (
        f"1. Follow @{username}\n"
        f"2. Like & Repost (RT)\n"
        f"3. Drop your 0x / EVM address below 👇"
    )
    closing = f"⏱️ Picking winners in {duration} hours! Good luck! 🚀"
    hashtags = "#Ethereum #EVM #Giveaway #Airdrop #Crypto"

    return f"{hook}\n\n{rules}\n\n{closing}\n\n{hashtags}"

if __name__ == "__main__":
    print("--- CONTOH GENERATED SOLANA GIVEAWAY ---")
    print(generate_solana_giveaway())
    print("\n----------------------------------------\n")
    print("--- CONTOH 2 ---")
    print(generate_solana_giveaway())
