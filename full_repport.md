AlphaHunter Project — Complete Codebase Analysis
This is a crypto trading bot for Solana memecoin detection that monitors Pump.fun and DexScreener, detects high-potential tokens, identifies scams, and tracks smart-money wallet activity. It sends alerts via Telegram.

DIRECTORY STRUCTURE

alphahunter/
├── config/
│   ├── __init__.py                          # Empty
│   └── settings.py                          # API keys, thresholds, wallet list
├── core/
│   ├── __init__.py                          # Empty
│   ├── engine.py                            # Main orchestration loop (async)
│   ├── fetcher.py                           # Fetches data from DexScreener/Birdeye/Pump.fun
│   ├── scam_detector.py                     # Token quality filters
│   ├── scorer.py                            # Computes Alpha Score (0-100)
│   ├── narrative_engine.py                  # Detects trending narrative categories
│   ├── wallet_tracker.py                    # Tracks Tier-A smart-money wallets
│   └── sub_narrative.py                     # Generates sub-narrative tokens
├── alerts/
│   ├── __init__.py                          # Empty
│   └── telegram_bot.py                      # Sends formatted alerts to Telegram
├── data/
│   ├── __init__.py                          # Empty
│   ├── store.py                             # In-memory store with JSON persistence
│   └── state.json                           # Persisted token state
├── .windsurf/
│   └── workflows/
│       └── wallets.md                       # Windsurf workflow config
├── main.py                                  # Entry point
├── get_chat_id.py                           # Helper script to get Telegram chat ID
├── test_bot.py                              # Test Telegram bot commands
├── requirements.txt                         # Python dependencies
└── README.md                                # Project documentation
KEY FILES
requirements.txt
aiohttp >= 3.9.0 (async HTTP client)
asyncio >= 3.4.3 (async I/O)
config/settings.py (CRITICAL CONFIG)
TELEGRAM_BOT_TOKEN = (loaded from environment variable)
TELEGRAM_CHAT_ID = (loaded from environment variable)
Thresholds:
MIN_ALPHA_SCORE = 60 (min to generate alert)
ENTRY_SIGNAL_SCORE = 70 (full entry alert)
MIN_LIQUIDITY_USD = 10,000
MIN_HOLDERS = 50
MIN_TIER_A_WALLETS = 1
Scam filters:
SCAM_MIN_HOLDERS = 10
SCAM_MAX_TOP10_PCT = 80 (reject if top-10 hold >80%)
SCAM_MIN_LIQUIDITY = 5,000
Loop intervals:
FETCH_INTERVAL = 30s (token polling)
WALLET_CHECK_INTERVAL = 60s (wallet tracking)
TIER_A_WALLETS: List of 10 smart-money wallet addresses to track
NARRATIVE_KEYWORDS: Dict of 7 narrative themes (celebrity, ai, animals, politics, gaming, internet, crypto)
data/state.json (EXAMPLE STATE)
Stores ~35 tracked tokens with:
Address, symbol, name, price, liquidity, volume_24h, market_cap
Holders, 5m buy/sell counts, alpha_score, narrative label
Tier-A wallet activity (buys/sells)
Scam flags, first_seen, last_updated, alert status
Daily stats: date, signals_sent (0), scams_rejected (1943), tokens_scanned (25), tier_a_moves (0)
Signals log (empty in this state)
CORE COMPONENTS
main.py (Entry Point)
Loads config from config/settings.py
Validates Telegram token + chat ID
Warns if TIER_A_WALLETS is empty
Logs to console + file (logs/alphahunter.log)
Runs AlphaHunterEngine async main loop
Graceful shutdown on CTRL+C / SIGTERM
core/engine.py (Orchestration)
Runs 4 concurrent async loops:

_token_loop() (every 30s)

Fetches new tokens from Pump.fun + DexScreener
For each token: fetch enriched data, scam check, narrative detect, score, register with wallet tracker
Sends alerts if score meets thresholds
Stores records in DataStore
_wallet_loop() (every 60s)

Polls all Tier-A + Tier-B wallets for new transactions
Detects buy/sell signals
Checks open positions for exit conditions
_daily_summary_loop() (once per day at configured hour)

Sends daily recap with stats, trending narratives
_persist_loop() (every 5 minutes)

Saves state to data/state.json
Alert logic:

ENTRY SIGNAL (🎯): score ≥ 70 AND liquidity ≥ $10k AND ≥1 Tier-A wallet buying AND buys > sells
NEW TOKEN (🆕): 60 ≤ score < 70
EXIT SIGNAL (🚪): >50% of initial Tier-A buyers have sold OR narrative collapse
SCAM ALERT (⚠️): Fails scam checks
core/fetcher.py (Data Sources)
Uses free APIs (no keys required):

Pump.fun: Latest token launches (get_pumpfun_new_tokens())
DexScreener: New Solana pairs + token info (get_dex_token(), get_dex_new_pairs())
Birdeye: Token holders + holder distribution (requires API key, optional)
Solana public RPC: Wallet transactions + token accounts (free endpoints rotated)
Key methods:

get_pumpfun_new_tokens() → list of newest tokens
get_dex_token(address) → detailed pair data with volume, buy/sell counts, price changes
get_token_largest_accounts(mint) → top 20 holders, concentration %, estimated total holder count
get_wallet_transactions(wallet) → last 10 txns for a wallet
get_token_accounts_for_wallet(wallet) → tokens currently held by a wallet
core/scam_detector.py (Quality Filters)
Returns list of "flag" strings. Empty = passes, non-empty = rejected.

Checks:

Liquidity < $5k
Zero market cap
Zero 5m transactions (dead token)
Sell pressure > 85% in last 5m
Price dump > -50% in 5m
Too few holders (< 10)
Top-10 hold > 80%
Mint/freeze authority active
Severity levels: CLEAN, CAUTION, WARNING, DANGER

core/scorer.py (Alpha Score: 0-100)
Breakdown (6 components):

Wallet Score (0-25): Smart-money activity (Tier-A buys)
Narrative Score (0-20): Trending topic relevance
Liquidity Score (0-15): Pool depth ($5k → 0pts, $500k+ → 15pts)
Volume Score (0-15): Momentum (vol acceleration, buy/sell ratio)
Social Score (0-15): Twitter/Telegram/Website presence, community engagement
Holder Score (0-10): Distribution quality (more holders = better, low top-10% concentration = better)
core/narrative_engine.py (Trend Detection)
Matches token name/symbol/description against 7 keyword categories
Returns (narrative_label, score_0_to_20)
Tracks "trend velocity" — if narrative is hot (many hits in last hour), gives +5 bonus points
Keeps sliding 2-hour window of recent hits per narrative
Returns top-5 trending narratives for daily summary
core/wallet_tracker.py (Smart-Money Tracking)
Tracks Tier-A + Tier-B wallets separately
Detects buys: wallet holds token we're tracking
Detects sells: wallet previously held, now doesn't
Records token addresses wallet interacts with
Methods:

wallet_score(token_address) → 0-25 score based on Tier-A activity
Max 25 at 3+ wallets buying, -4 penalty per seller
count_tier_a_buying(token) → # of Tier-A wallets holding
count_tier_a_selling(token) → # of Tier-A wallets that exited
is_exit_signal(token) → true if >50% of initial buyers have sold
get_recent_tier_a_moves() → last 5 wallet moves across all tracked tokens
core/sub_narrative.py (Sub-Narrative Detection)
Generates thematic token discovery from viral tokens.

Example: If "DOG" token goes viral, generates concepts like:

friend, baby, toy, mom, dad, cousin, brother, sister
puppy, bone, park (for "dog" theme)
Relationship maps for animals, characters, story elements, memes.

Methods:

is_viral(token) → volume ≥ $100k OR liquidity ≥ $50k OR Tier-A buys ≥ 2
generate_sub_narratives(main_token) → list of discovery concepts
score_sub_narrative(token, concept, main_token) → 0-100 score
alerts/telegram_bot.py (Alert System)
Async Telegram bot using polling (getUpdates).

Alert types with formatting:

🆕 NEW_TOKEN: Detected, above threshold

Symbol, name, score bar, market cap, liquidity, volume, buy/sell ratio
Narrative + score breakdown, social links
DexScreener + Pump.fun links
🎯 ENTRY_SIGNAL: All conditions met

"All Entry Conditions Met" checklist (liquidity ✓, holders ✓, Tier-A ✓, momentum ✓, score ✓)
Full market data, narrative, score breakdown
Risk params: 0.5–1% position size, TP1 +50% (25%), TP2 +100% (25%), -20% stop
⚠️ SCAM_ALERT: Rejected token

Severity level (⚠️/🚨/☠️)
List of flags and counts
🚪 EXIT_SIGNAL: Smart money exiting

Reason + count of Tier-A sellers
Links to check price
📊 DAILY_SUMMARY: End-of-day recap

Tokens scanned, scams blocked, signals sent, Tier-A moves
Entry/exit signals today (up to 5 each)
Top 4 trending narratives
Commands (via /command in Telegram):

/hello or /start → Greeting with system info
/menu or /help → Command list
/status → System diagnostics (all modules running)
/alerts → Recent alert history
/stats → Today's performance stats
/wallets → Tracked Tier-A wallet list
Rate limiting: 1s minimum between messages (Telegram's 429 throttle)

data/store.py (Persistence)
In-memory store with JSON serialization.

Classes:

TokenRecord: address, symbol, name, price, liquidity, volume_24h, market_cap, holders, buys_5m, sells_5m, alpha_score, narrative, tier_a_buys/sells, scam_flags, first_seen, last_updated, alerted, exit_alerted
DailyStats: date, signals_sent, scams_rejected, tokens_scanned, tier_a_moves
Methods:

upsert_token(record) → merge with existing or insert
mark_alerted(address) → set alerted=True
get_active_signals() → tokens with entry alert but no exit yet
log_signal(type, token, reason) → append to signals_log
log_scam_rejected() / log_tier_a_move() → increment counters
save() → serialize to JSON
_load() → load from disk on init
DATA FLOW DIAGRAM

┌─────────────────────────────────────────────────────────────────┐
│                      Main Event Loop                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  FETCH LOOP      │  │  WALLET LOOP     │  │  DAILY LOOP  │  │
│  │  (30s)           │  │  (60s)           │  │  (once/day)  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                      │                   │          │
│  ┌────────▼──────────┐  ┌────────▼────────┐  ┌──────▼─────┐   │
│  │ Pump.fun + Dex    │  │ Poll Tier-A/B   │  │ Aggregate  │   │
│  │ New Tokens        │  │ Wallets         │  │ Stats &    │   │
│  └────────┬──────────┘  └────────┬────────┘  │ Trends     │   │
│           │                      │           └──────┬─────┘    │
│           └──────────┬───────────┘                  │          │
│                      │                             │          │
│              ┌───────▼────────────┐               │          │
│              │ For Each Token:    │               │          │
│              ├────────────────────┤               │          │
│              │ 1. Fetch from DEX  │               │          │
│              │ 2. Scam check      │  ────────────┼──────────┘
│              │ 3. Detect narrative│               │
│              │ 4. Score (0-100)   │               │
│              │ 5. Wallet score    │               │
│              │ 6. Store record    │               │
│              │ 7. Send alerts     │               │
│              └─────┬──────────────┘               │
│                    │                              │
│              ┌─────▼──────────────┐              │
│              │  Check Exit        │              │
│              │  Conditions        │              │
│              └────────────────────┘              │
│                                                  │
│         ┌─────────────────────────┐             │
│         │ Persist to JSON         │             │
│         │ (every 5 min)           │             │
│         └─────────────────────────┘             │
│                                                  │
│  ┌─────────────────────────────────────┐        │
│  │ TELEGRAM BOT POLLING                │        │
│  │ (concurrent)                        │        │
│  │ • Listen for /commands              │        │
│  │ • Send alerts                       │        │
│  └─────────────────────────────────────┘        │
│                                                  │
└─────────────────────────────────────────────────────────────────┘
EXAMPLE ALERT FLOW
Token Discovery (every 30s)

Fetcher gets new tokens from Pump.fun/DexScreener
DexScreener enriches with volume, price changes, liquidity
ScamDetector runs 7 checks → flags any red flags
If flagged, sends ⚠️ SCAM_ALERT and returns
Scoring (if passes scam check)

NarrativeEngine detects category (e.g., "animals")
WalletTracker calculates wallet_score (0-25) based on Tier-A holdings
Scorer aggregates 6 components → alpha_score (0-100)
Record stored in DataStore
Alert Decision

If score ≥ 70 AND liquidity ≥ $10k AND Tier-A wallets buying AND momentum positive → Send 🎯 ENTRY_SIGNAL (high-priority)
Else if score ≥ 60 → Send 🆕 NEW_TOKEN (lower priority)
Else skip (log to debug)
Exit Monitoring (every 60s in wallet loop)

For each open (alerted but not exited) position
Check if >50% of initial Tier-A buyers have sold
Send 🚪 EXIT_SIGNAL if true
HELPER SCRIPTS
get_chat_id.py

Interactive script to retrieve Telegram chat ID
Steps: 1) Verify token set, 2) Prompt user to send message to bot, 3) Fetch getUpdates, 4) Extract + display chat_id
test_bot.py

Tests Telegram bot message sending + polling
Sends test message, polls for commands (/hello, /menu, /status)
Responds to commands, validates round-trip
STATE PERSISTENCE (state.json)
The data/state.json file stores:

tokens: Dictionary of 35+ tracked tokens with full metadata
daily_stats: Today's aggregate numbers
signals_log: Last 500 signals sent (NEW_TOKEN, ENTRY, EXIT)
On startup, DataStore loads this file. Every 5 minutes, engine.py saves updated state.

SECURITY & API KEYS
Telegram Bot Token: Loaded from TELEGRAM_BOT_TOKEN environment variable
Telegram Chat ID: Loaded from TELEGRAM_CHAT_ID environment variable
Birdeye API Key: Optional (can be left blank for free tier)
Solana RPC: Public endpoints (no auth required)
Pump.fun / DexScreener: Free, no keys needed
✅ All secrets now loaded from environment variables (see .env.example)

ASYNC ARCHITECTURE
asyncio.gather() in engine.py runs 4 loops concurrently
Semaphore(5) limits concurrent token processing to 5
aiohttp.ClientSession reused for HTTP pooling
Telegram bot uses blocking getUpdates (long-polling, not webhooks)
SCORING ALGORITHM BREAKDOWN
Component	Min	Max	Calculation
Wallet	0	25	Tier-A buys (max 3 → 25pts) - (sells × 4)
Narrative	0	20	Keyword matches (up to 15) + trend velocity bonus (up to 5)
Liquidity	0	15	Curve: $5k→0, $20k→5, $50k→10, $100k→13, $500k+→15
Volume	0	15	Vol size (6pts) + buy/sell ratio (5pts) + acceleration (4pts)
Social	0	15	Twitter (4) + Telegram (4) + Website (3) + Replies (0-4)
Holders	0	10	Count bonus (0-5) + distribution bonus (0-5)
TOTAL	0	100	Sum of all (capped at 100)
CONFIGURATION THRESHOLDS
Setting	Value	Purpose
MIN_ALPHA_SCORE	60	Minimum score to trigger any alert
ENTRY_SIGNAL_SCORE	70	Threshold for 🎯 ENTRY_SIGNAL
MIN_LIQUIDITY_USD	$10k	Minimum pool depth to trade
MIN_HOLDERS	50	Reject if too few hodlers
SCAM_MAX_TOP10_PCT	80	Reject if top-10 hold >80%
FETCH_INTERVAL	30s	How often to poll for new tokens
WALLET_CHECK_INTERVAL	60s	How often to check smart wallets
DAILY_SUMMARY_HOUR	20	24h UTC hour for daily recap (8pm)
NARRATIVE CATEGORIES (7 themes)
celebrity: elon, trump, musk, kanye, taylor, celebrity
ai: ai, gpt, claude, llm, artificial, agent
animals: dog, cat, pepe, frog, bear, bull, doge, shib
politics: vote, election, president, senate, congress
gaming: game, play, nft, metaverse, fortnite, roblox
internet: meme, viral, based, chad, wojak, sigma
crypto: sol, solana, pump, moon, rug, degen, ape
This is a production-ready memecoin hunter with sophisticated scoring, scam filtering, smart-money tracking, and Telegram alerting. It's designed to run 24/7 and scale to thousands of tokens across Solana.

The exploration is complete. Now I'll write the consolidated report to persistent memory.

Globpattern: "**/*"
No files found
Write C:\Users\youss\.claude\projects\c--Users-youss\memory\project_alphahunter.md
225 lines
---
name: project-alphahunter
description: Full architecture report for AlphaHunter — Solana memecoin hunting bot with smart-money tracking, scam filtering, scoring, and Telegram alerts. Reference before any code changes.
metadata:
  type: project
---

# AlphaHunter — Project Architecture Report
**Generated:** 2026-06-29  
**Path:** `c:\Users\youss\OneDrive\Documents\alphahunter`  
**Language:** Python 3 (async/await)  
**Purpose:** 24/7 Solana memecoin detection bot — scans Pump.fun + DexScreener, scores tokens (0–100), filters scams, tracks smart-money wallets, sends Telegram alerts.

---

## Directory Structure

```
alphahunter/
├── config/settings.py         # All API keys, thresholds, wallet addresses, narrative keywords
├── core/
│   ├── engine.py              # Main orchestration — 4 concurrent async loops
│   ├── fetcher.py             # HTTP data layer: Pump.fun, DexScreener, Birdeye, Solana RPC
│   ├── scam_detector.py       # 7-check quality filter, returns list of flag strings
│   ├── scorer.py              # Alpha Score (0–100) from 6 weighted components
│   ├── narrative_engine.py    # Keyword-based trend categorization + velocity tracking
│   ├── wallet_tracker.py      # Tier-A/B smart-money wallet buy/sell detection
│   └── sub_narrative.py       # Generates thematic discovery tokens from viral tokens
├── alerts/telegram_bot.py     # Async Telegram bot (polling), 5 alert types, 7 /commands
├── data/
│   ├── store.py               # In-memory store + JSON persistence (TokenRecord, DailyStats)
│   └── state.json             # Persisted state (~35 tokens, daily stats, signals log)
├── main.py                    # Entry point — logging, validation, runs engine
├── get_chat_id.py             # Helper: retrieve Telegram chat_id
├── test_bot.py                # Manual test: send message + poll /commands
└── requirements.txt           # aiohttp>=3.9.0, asyncio>=3.4.3
```

---

## Key Workflows & Data Pipelines

### 1. Token Detection Loop (every 30s — `engine._token_loop`)
```
Pump.fun + DexScreener new tokens
  → fetcher.get_pumpfun_new_tokens() + fetcher.get_dex_new_pairs()
  → fetcher.get_dex_token(address)          # Enrich with volume/price/liquidity
  → scam_detector.check(token)              # 7 checks → flags list
  → IF flagged: send ⚠️ SCAM_ALERT, increment scams_rejected, skip
  → narrative_engine.detect(name/symbol)    # Returns (label, score 0–20)
  → scorer.score(token)                     # Aggregates 6 components → 0–100
  → wallet_tracker.register(token)
  → store.upsert_token(record)
  → IF score≥70 AND liq≥$10k AND Tier-A buying AND buys>sells → 🎯 ENTRY_SIGNAL
  → ELIF score≥60 → 🆕 NEW_TOKEN
```

### 2. Wallet Monitoring Loop (every 60s — `engine._wallet_loop`)
```
For each Tier-A + Tier-B wallet:
  → fetcher.get_wallet_transactions(wallet)
  → fetcher.get_token_accounts_for_wallet(wallet)
  → wallet_tracker.update(wallet, transactions, holdings)
  → Detect buy: wallet now holds tracked token
  → Detect sell: wallet no longer holds tracked token
For each open (alerted, not exited) position:
  → wallet_tracker.is_exit_signal(token)    # >50% of initial Tier-A buyers sold
  → IF true → send 🚪 EXIT_SIGNAL
```

### 3. Daily Summary Loop (once at 20:00 UTC — `engine._daily_summary_loop`)
```
store.get_daily_stats() → aggregate numbers
narrative_engine.get_trending() → top-4 narratives
telegram_bot.send_daily_summary() → 📊 DAILY_SUMMARY
```

### 4. Persist Loop (every 5 min — `engine._persist_loop`)
```
store.save() → serialize all tokens + stats to data/state.json
```

---

## Scoring Algorithm (scorer.py)

| Component    | Weight | Key Logic |
|--------------|--------|-----------|
| Wallet       | 0–25   | Tier-A buys×8 (max 3→25) minus sells×4 |
| Narrative    | 0–20   | Keyword match score (up to 15) + trend velocity bonus (up to 5) |
| Liquidity    | 0–15   | Curve: $5k→0, $20k→5, $50k→10, $100k→13, $500k+→15 |
| Volume       | 0–15   | Size 6pts + buy/sell ratio 5pts + acceleration 4pts |
| Social       | 0–15   | Twitter 4 + Telegram 4 + Website 3 + Replies 0–4 |
| Holder       | 0–10   | Count bonus 0–5 + concentration bonus 0–5 |
| **TOTAL**    | **0–100** | Capped at 100 |

---

## Scam Detector Checks (scam_detector.py)

1. Liquidity < $5k → flag
2. Zero market cap → flag
3. Zero 5m transactions → flag (dead token)
4. Sell pressure > 85% in 5m → flag
5. Price dump > -50% in 5m → flag
6. Holders < 10 → flag
7. Top-10 holders > 80% concentration → flag
8. Mint/freeze authority active → flag

Returns list of flag strings; empty = CLEAN. Severity: CLEAN → CAUTION → WARNING → DANGER.

---

## Configuration Thresholds (config/settings.py)

| Setting | Value |
|---------|-------|
| MIN_ALPHA_SCORE | 60 |
| ENTRY_SIGNAL_SCORE | 70 |
| MIN_LIQUIDITY_USD | $10,000 |
| MIN_HOLDERS | 50 |
| SCAM_MIN_HOLDERS | 10 |
| SCAM_MAX_TOP10_PCT | 80% |
| SCAM_MIN_LIQUIDITY | $5,000 |
| FETCH_INTERVAL | 30s |
| WALLET_CHECK_INTERVAL | 60s |
| DAILY_SUMMARY_HOUR | 20 (8pm UTC) |

---

## Narrative Categories (narrative_engine.py)

7 themes tracked with keyword lists:
- **celebrity**: elon, trump, musk, kanye, taylor, celebrity
- **ai**: ai, gpt, claude, llm, artificial, agent
- **animals**: dog, cat, pepe, frog, bear, bull, doge, shib
- **politics**: vote, election, president, senate, congress
- **gaming**: game, play, nft, metaverse, fortnite, roblox
- **internet**: meme, viral, based, chad, wojak, sigma
- **crypto**: sol, solana, pump, moon, rug, degen, ape

Velocity: counts hits in a 2-hour sliding window; hot narratives get +5 score bonus.

---

## Telegram Alerts (alerts/telegram_bot.py)

| Alert | Trigger | Emoji |
|-------|---------|-------|
| NEW_TOKEN | score 60–69 | 🆕 |
| ENTRY_SIGNAL | score≥70 + liq≥$10k + Tier-A buying + buys>sells | 🎯 |
| SCAM_ALERT | any scam flag | ⚠️ |
| EXIT_SIGNAL | >50% Tier-A sellers | 🚪 |
| DAILY_SUMMARY | 8pm UTC | 📊 |

Bot commands: `/hello`, `/start`, `/menu`, `/help`, `/status`, `/alerts`, `/stats`, `/wallets`

Rate limit: 1s minimum between messages.

---

## External APIs

| Source | Auth | Endpoint |
|--------|------|----------|
| Pump.fun | None (free) | Latest token launches |
| DexScreener | None (free) | New Solana pairs, token enrichment |
| Birdeye | Optional API key | Token holders + distribution |
| Solana Public RPC | None (free, rotated) | Wallet txns, token accounts |

---

## Known Issues & Recommended Fixes (Priority Order)

### CRITICAL
1. **API keys hardcoded in settings.py** — Telegram bot token + chat ID are plaintext in source.
   - Fix: Move to `.env` file, load with `python-dotenv`. Add `.env` to `.gitignore`.

2. **No error recovery in loops** — if `_token_loop` throws unhandled exception, the loop dies silently.
   - Fix: Wrap inner loop bodies in `try/except Exception as e: logger.error(...)` with continue.

### HIGH
3. **Telegram bot uses polling** — `getUpdates` long-polling is fragile and slow vs webhooks.
   - Fix: Switch to `aiohttp` webhook handler or use `python-telegram-bot` library for robustness.

4. **Semaphore limit is 5 concurrent tokens** — at scale (100s of new tokens/minute from Pump.fun), the 30s loop may fall behind.
   - Fix: Increase semaphore to 10–20, or add a token queue with priority.

5. **`data/state.json` grows unbounded** — tokens are never pruned; signals_log grows to 500.
   - Fix: Evict tokens older than 24h with no alerts. Cap signals_log more aggressively.

### MEDIUM
6. **`sub_narrative.py` is not wired into scoring pipeline** — generates sub-narrative concepts but engine.py never calls it.
   - Fix: Either integrate into `_token_loop` or remove to reduce confusion.

7. **`wallet_tracker.py` tier scoring is asymmetric** — 3 Tier-A buys = max 25pts but each sell subtracts only 4pts, so 3 buyers + 3 sellers = 13pts (still positive).
   - Fix: Recalibrate: if sellers > buyers, score should go negative or zero.

8. **`narrative_engine` trend velocity window** — 2-hour window may be too short for slow narratives; all trend velocity resets on restart.
   - Fix: Persist narrative velocity counts in `state.json`.

9. **`get_token_largest_accounts` estimates holder count** — divides top-20 holdings by assumed 5% average, which is inaccurate.
   - Fix: Use Birdeye API (already supported) for accurate holder counts, or Solana `getProgramAccounts`.

### LOW
10. **No logging of individual HTTP failures** — `fetcher.py` returns `None` on exceptions; callers don't log which token/wallet failed.
    - Fix: Add per-call logging with token address and error type.

11. **`score` bar in Telegram messages** uses filled/empty blocks — not accessible in all Telegram clients.
    - Fix: Add numeric score alongside bar: `████░░ 68/100`.

12. **Inconsistent naming**: `tier_a_buys` (snake_case field) vs `count_tier_a_buying()` (method); `get_dex_token` vs `get_pumpfun_new_tokens` (inconsistent prefix convention).
    - Fix: Standardize to `get_` prefix for all fetcher methods; use consistent field names.

---

## Architecture Observations

- **Strengths**: Clean separation of concerns (fetch / detect / score / alert), async throughout, free-API only, graceful shutdown, JSON persistence.
- **Weaknesses**: Single-process, no message queue, no database (JSON file only), no retry logic, no rate-limit handling on Solana RPC, secrets in code.
- **Scalability ceiling**: Current design handles ~50–100 new tokens/30s comfortably. Beyond that, needs Redis + task queue (Celery/RQ) or a proper message broker.

**Why:** This is a solo/small-team trading tool built for speed-to-market. The JSON persistence and hardcoded keys are deliberate simplicity trade-offs, not oversight — but they become risks if the repo goes public or the tool is shared.
**How to apply:** When suggesting changes, favor minimal, non-breaking additions. Don't propose full rewrites unless the user explicitly asks.
Write C:\Users\youss\.claude\projects\c--Users-youss\memory\MEMORY.md
4 lines
# Memory Index

- [AlphaHunter Project Report](project_alphahunter.md) — Full architecture, scoring logic, data pipelines, issues & fix priority list for the Solana memecoin hunter bot
Report saved to persistent memory. Here's the summary:

AlphaHunter — Project Report
What it is: A 24/7 Solana memecoin scanner that polls Pump.fun + DexScreener every 30s, scores tokens 0–100, filters scams, tracks smart-money wallets, and fires Telegram alerts.

Module Map
Module	Role
core/engine.py	4 concurrent async loops (token, wallet, daily summary, persist)
core/fetcher.py	HTTP layer — Pump.fun, DexScreener, Birdeye, Solana RPC
core/scorer.py	6-component score: Wallet(25) + Narrative(20) + Liquidity(15) + Volume(15) + Social(15) + Holders(10)
core/scam_detector.py	7 red-flag checks; returns flag list
core/narrative_engine.py	Keyword → 7 themes, velocity-weighted
core/wallet_tracker.py	Tier-A/B smart-money buy/sell detection
alerts/telegram_bot.py	5 alert types, 7 slash commands, 1s rate limit
data/store.py	In-memory + JSON persistence
Top Issues (Priority Order)
CRITICAL — API keys hardcoded in config/settings.py → move to .env
CRITICAL — No try/except in async loops → silent death on any exception
HIGH — Telegram uses polling instead of webhooks → fragile at scale
HIGH — state.json grows unbounded → need token eviction after 24h
MEDIUM — sub_narrative.py is written but never called from engine.py
MEDIUM — Wallet score asymmetry: 3 sellers only subtract 12pts from a 25pt score
MEDIUM — Narrative velocity resets on every restart (not persisted)