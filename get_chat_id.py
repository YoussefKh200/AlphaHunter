"""
get_chat_id.py — Simple script to get your Telegram chat ID.

Usage:
    python get_chat_id.py

Steps:
    1. Run this script
    2. Send a message to your Telegram bot (any message like "hello")
    3. The script will display your chat ID
    4. Copy the chat ID to config/settings.py
"""

import asyncio
import aiohttp
from config.settings import TELEGRAM_BOT_TOKEN


async def get_chat_id():
    """Fetch the latest updates from Telegram to find your chat ID."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set in config/settings.py")
        print("Please set your bot token first, then run this script again.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    print("=" * 60)
    print("🔍 Getting Telegram Chat ID")
    print("=" * 60)
    print(f"\n📱 STEP 1: Open Telegram and search for your bot")
    print(f"   (Your bot name from @BotFather)")
    print(f"\n💬 STEP 2: Start a chat with your bot")
    print(f"   Click 'Start' or send any message like 'hello'")
    print(f"\n⏳ STEP 3: Press Enter here after sending the message...")
    input()
    
    print("\n🔄 Fetching updates from Telegram...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                
                if not data.get("ok"):
                    print(f"❌ Error: {data.get('description')}")
                    if "Unauthorized" in str(data.get('description')):
                        print("\n💡 Your bot token might be invalid.")
                        print("   Check config/settings.py and verify the token.")
                    return
                
                result = data.get("result", [])
                
                if not result:
                    print("❌ No updates found.")
                    print("\n💡 Troubleshooting:")
                    print("   1. Make sure you actually sent a message to your bot")
                    print("   2. Your bot might not be started - try sending /start")
                    print("   3. If using a channel, make sure the bot is added as admin")
                    print("   4. Try sending another message and run this script again")
                    return
                
                # Get the most recent update
                latest = result[-1]
                chat = latest.get("message", {}).get("chat", {})
                chat_id = chat.get("id")
                chat_type = chat.get("type", "unknown")
                username = chat.get("username", "N/A")
                first_name = chat.get("first_name", "N/A")
                
                print("\n" + "=" * 60)
                print("✅ Chat ID Found!")
                print("=" * 60)
                print(f"\n📊 Chat ID: {chat_id}")
                print(f"📝 Type: {chat_type}")
                print(f"👤 Username: @{username}" if username != "N/A" else f"👤 Username: {username}")
                print(f"🏷️  Name: {first_name}")
                print("\n" + "=" * 60)
                print(f"\n📋 Copy this Chat ID to config/settings.py:")
                print(f"   TELEGRAM_CHAT_ID = \"{chat_id}\"")
                print("=" * 60)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            print("\n💡 Make sure you have internet connection and the bot token is correct.")


if __name__ == "__main__":
    asyncio.run(get_chat_id())
