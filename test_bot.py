"""
test_bot.py — Simple test for Telegram bot command handling.
"""

import asyncio
import aiohttp
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def test_bot():
    """Test bot polling and command handling."""
    print("=" * 60)
    print("🤖 Testing Telegram Bot")
    print("=" * 60)
    
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    
    # Send a test message first
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "⚡ J.A.R.V.I.S. TEST MODE ACTIVE\n\nSend /hello to test command handling.",
        "parse_mode": "HTML"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                print("✅ Test message sent successfully")
            else:
                print(f"❌ Failed to send: {data.get('description')}")
                return
    
    # Now poll for updates
    print("\n🔄 Polling for commands...")
    print("Send /hello or /menu in Telegram now...")
    
    offset = 0
    for i in range(10):  # Poll for 10 iterations
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"offset": offset, "timeout": 10}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                
                if data.get("ok"):
                    result = data.get("result", [])
                    if result:
                        print(f"\n📨 Received {len(result)} update(s)")
                        for update in result:
                            message = update.get("message", {})
                            text = message.get("text", "")
                            from_chat = message.get("chat", {}).get("id")
                            
                            print(f"   Message: {text}")
                            print(f"   From chat: {from_chat}")
                            
                            if str(from_chat) == str(chat_id) and text.startswith("/"):
                                # Handle command
                                if text.lower() in ["/hello", "/start"]:
                                    response = "⚡ J.A.R.V.I.S. PROTOCOL INITIALIZED\n\nGood day, Sir. All systems operational."
                                elif text.lower() in ["/menu", "/help"]:
                                    response = "⚡ J.A.R.V.I.S. COMMAND INTERFACE\n\n/status - System diagnostics\n/menu - Show this menu\n/hello - Initialize protocol"
                                else:
                                    response = f"Unknown command: {text}"
                                
                                # Send response
                                send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                                send_payload = {
                                    "chat_id": chat_id,
                                    "text": response,
                                    "parse_mode": "HTML"
                                }
                                async with session.post(send_url, json=send_payload) as send_resp:
                                    send_data = await send_resp.json()
                                    if send_data.get("ok"):
                                        print("   ✅ Response sent")
                                    else:
                                        print(f"   ❌ Failed to respond: {send_data.get('description')}")
                            
                            offset = update.get("update_id", 0) + 1
                    else:
                        print(".", end="", flush=True)
                else:
                    print(f"❌ Error: {data.get('description')}")
        
        await asyncio.sleep(1)
    
    print("\n\n✅ Test complete")


if __name__ == "__main__":
    asyncio.run(test_bot())
