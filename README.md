# AlphaHunter — Automated Alert System

## Structure
```
alphahunter/
├── config/
│   └── settings.py          # API keys, thresholds, wallet lists
├── core/
│   ├── fetcher.py           # Pulls data from DexScreener / Birdeye / Pump.fun
│   ├── scam_detector.py     # Rejects low-quality tokens
│   ├── wallet_tracker.py    # Tracks smart-money wallets on Solana
│   ├── scorer.py            # Computes Alpha Score 0-100
│   ├── narrative_engine.py  # Detects trending narratives
│   └── engine.py            # Main orchestrator loop
├── alerts/
│   └── telegram_bot.py      # Sends formatted Telegram messages
├── data/
│   └── store.py             # In-memory + JSON state persistence
├── main.py                  # Entry point
└── requirements.txt
```

## Setup
```bash
pip install -r requirements.txt
cp config/settings.py config/settings_local.py  # fill in your keys
python main.py
```
