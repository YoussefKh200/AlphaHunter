# ============================================================
# AlphaHunter — Configuration
# ============================================================
# Copy this file, fill in your real values, then run main.py
# Never commit API keys to git.
# ============================================================

# ── TELEGRAM ────────────────────────────────────────────────
# Prefer env vars; fall back to literals so the bot still runs locally.
# ponytail: the token below is already in git history — ROTATE it via @BotFather
# and set TELEGRAM_BOT_TOKEN in your environment instead of editing this file.
import os
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8575869948:AAEJl9qs163x24dsLyRQ-JZVBWKvqnmy-FY")  # from @BotFather
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5392376464")  # your channel or user ID

# ── API KEYS ─────────────────────────────────────────────────
# All APIs are free — no keys needed!
# DexScreener: free, no key
# Pump.fun:    free, no key
# Solana RPC:  free public endpoint

# ── SCORING THRESHOLDS ───────────────────────────────────────
MIN_ALPHA_SCORE        = 60       # minimum score to generate an ENTRY signal (lowered to catch more)
ENTRY_SIGNAL_SCORE     = 70       # score threshold for full entry alert (lowered)
MIN_LIQUIDITY_USD      = 10_000   # entry filter (lowered for early opportunities)
MIN_HOLDERS            = 50       # entry filter (lowered)
MIN_TIER_A_WALLETS     = 1        # minimum smart-money wallets buying (lowered)

# ── SCAM FILTERS ─────────────────────────────────────────────
SCAM_MIN_HOLDERS       = 10       # reject if below (lowered)
SCAM_MAX_TOP10_PCT     = 80       # reject if top-10 holders own more than this % (relaxed)
SCAM_MAX_DEV_PCT       = 20       # reject if dev holds more than this % (relaxed)
SCAM_MIN_LIQUIDITY     = 5_000    # reject if liquidity below this (lowered)

# ── LOOP INTERVALS (seconds) ─────────────────────────────────
FETCH_INTERVAL         = 30       # how often to poll for new tokens
WALLET_CHECK_INTERVAL  = 60       # how often to check wallet activity
DAILY_SUMMARY_HOUR     = 20       # 24h clock hour for daily summary (UTC)

# ── TIER-A SMART WALLETS ─────────────────────────────────────
# Add known profitable Solana wallet addresses here.
# These are the wallets you are tracking for buy/sell signals.
TIER_A_WALLETS = [
    "0x5f94a51948d2376ad34a6fadfa2544e651b74b96",
    "GdLdKs81rMtJZxMsBPb5SzAwvjAF3KxPr1pbiN1oe1qH",
    "0x02ab69F610e34211e749Bee493fD0138fE5c818f",
    "0x4337bF7aFCEef9788a60C4cb98830ed6D8e79Fb1",
    "83tkeM3LfsuaEH68erz71B9UMnuq1ahsrv24q1ScSdyN",
    "ETgTUJX8R6Hpnwv4r4hSTpQq6LhZymxyHfVHFJEDMrp2",
    "gasBidSWW5zmwXs3gn8TG2ijzKkrwpyM7ucwjgDQst6",
    "B7pfBn9jSXpP7tZhkkiwydL2N6JU2aeQEqgG1WPyVf4R",
    "7gAKiGycmoSKtKWwVeSwqWxfmf9qVUtiyXKi6amTRTM6",
    # Add more here — the more you track, the better the signal
]

TIER_B_WALLETS = [
    # "WALLET_ADDRESS_3",
]

# ── NARRATIVE KEYWORDS ───────────────────────────────────────
NARRATIVE_KEYWORDS = {
    "celebrity":  ["elon", "trump", "musk", "kanye", "taylor", "celebrity"],
    "ai":         ["ai", "gpt", "claude", "llm", "artificial", "agent"],
    "animals":    ["dog", "cat", "pepe", "frog", "bear", "bull", "doge", "shib"],
    "politics":   ["vote", "election", "president", "senate", "congress"],
    "gaming":     ["game", "play", "nft", "metaverse", "fortnite", "roblox"],
    "internet":   ["meme", "viral", "based", "chad", "wojak", "sigma"],
    "crypto":     ["sol", "solana", "pump", "moon", "rug", "degen", "ape"],
}

# ── RISK PARAMETERS ──────────────────────────────────────────
MAX_RISK_PER_TRADE_PCT = 1.0      # % of portfolio per trade (for future execution)
DAILY_LOSS_LIMIT_PCT   = 5.0
WEEKLY_LOSS_LIMIT_PCT  = 10.0
MAX_OPEN_POSITIONS     = 10
