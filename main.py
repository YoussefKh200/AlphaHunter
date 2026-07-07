"""
main.py — AlphaHunter entry point.

Usage:
    python main.py

Before running:
    1. Fill in config/settings.py with your Telegram bot token + chat ID
    2. Optionally add your Birdeye API key for holder data
    3. Add Tier-A wallet addresses you want to track
    4. pip install -r requirements.txt
"""

import asyncio
import logging
import signal
import sys
import os

# ── Logging setup ────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/alphahunter.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ── Config validation ────────────────────────────────────────────────────────
def load_config():
    """Load settings and validate required fields."""
    try:
        import config.settings as cfg
    except ImportError:
        logger.error("config/settings.py not found. Copy the template and fill in your values.")
        sys.exit(1)

    errors = []
    if cfg.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append("TELEGRAM_BOT_TOKEN not set in config/settings.py")
    if cfg.TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        errors.append("TELEGRAM_CHAT_ID not set in config/settings.py")

    if errors:
        for e in errors:
            logger.error(f"Config error: {e}")
        logger.error("\n" + "="*50)
        logger.error("HOW TO GET YOUR TELEGRAM BOT TOKEN:")
        logger.error("  1. Open Telegram → search @BotFather")
        logger.error("  2. Send /newbot → follow prompts")
        logger.error("  3. Copy the token → paste in config/settings.py")
        logger.error("\nHOW TO GET YOUR CHAT ID:")
        logger.error("  1. Start your bot or add it to a channel")
        logger.error("  2. Send a message, then visit:")
        logger.error("     https://api.telegram.org/bot<TOKEN>/getUpdates")
        logger.error("  3. Find 'chat' → 'id' in the response")
        logger.error("="*50)
        sys.exit(1)

    if not cfg.TIER_A_WALLETS:
        logger.warning(
            "⚠️  TIER_A_WALLETS is empty in config/settings.py. "
            "Wallet tracking won't work — add profitable Solana wallet addresses."
        )

    return cfg


# ── Main ─────────────────────────────────────────────────────────────────────
async def main():
    cfg = load_config()

    from core.engine import AlphaHunterEngine
    engine = AlphaHunterEngine(cfg)

    # Graceful shutdown on CTRL+C / SIGTERM
    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Shutdown signal received...")
        asyncio.create_task(engine.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows

    logger.info("="*50)
    logger.info("  AlphaHunter — Memecoin Alpha Detection System")
    logger.info("  Monitoring: Pump.fun + DexScreener + Solana Wallets")
    logger.info(f"  Entry threshold: Score > {cfg.ENTRY_SIGNAL_SCORE}")
    logger.info(f"  Alert threshold: Score > {cfg.MIN_ALPHA_SCORE}")
    logger.info(f"  Fetch interval:  {cfg.FETCH_INTERVAL}s")
    logger.info(f"  Tier-A wallets:  {len(cfg.TIER_A_WALLETS)}")
    logger.info("="*50)

    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
