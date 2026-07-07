"""
data/store.py — In-memory state store with JSON persistence.
Tracks seen tokens, wallet activity, open signals, and daily stats.
"""

import json
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TokenRecord:
    address: str
    symbol: str
    name: str
    price_usd: float
    liquidity_usd: float
    volume_24h: float
    market_cap: float
    holders: int
    buys_5m: int
    sells_5m: int
    alpha_score: float
    narrative: str
    tier_a_buys: int
    tier_a_sells: int
    scam_flags: List[str]
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    alerted: bool = False           # True once an entry alert was sent
    exit_alerted: bool = False


@dataclass
class DailyStats:
    date: str
    signals_sent: int = 0
    scams_rejected: int = 0
    tokens_scanned: int = 0
    tier_a_moves: int = 0


class DataStore:
    """Central in-memory store. Persists to JSON on disk periodically."""

    PERSIST_PATH = "data/state.json"
    MAX_TOKEN_AGE = 86400   # drop tokens older than 24h (unless still an active signal)

    def __init__(self):
        self.tokens: Dict[str, TokenRecord] = {}       # address → TokenRecord
        self.wallet_activity: Dict[str, List[dict]] = {}  # wallet → [tx, ...]
        self.daily_stats: DailyStats = DailyStats(date=self._today())
        self.signals_log: List[dict] = []
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    def upsert_token(self, record: TokenRecord):
        existing = self.tokens.get(record.address)
        if existing:
            record.first_seen = existing.first_seen
            record.alerted = existing.alerted
            record.exit_alerted = existing.exit_alerted
        self.tokens[record.address] = record
        self.daily_stats.tokens_scanned = len(self.tokens)

    def get_token(self, address: str) -> Optional[TokenRecord]:
        return self.tokens.get(address)

    def mark_alerted(self, address: str):
        if address in self.tokens:
            self.tokens[address].alerted = True

    def mark_exit_alerted(self, address: str):
        if address in self.tokens:
            self.tokens[address].exit_alerted = True

    def get_active_signals(self) -> List[TokenRecord]:
        """Tokens that got an entry alert but no exit yet."""
        return [t for t in self.tokens.values() if t.alerted and not t.exit_alerted]

    def log_signal(self, signal_type: str, token: TokenRecord, reason: str = ""):
        self.signals_log.append({
            "type": signal_type,
            "symbol": token.symbol,
            "address": token.address,
            "score": token.alpha_score,
            "time": time.time(),
            "reason": reason,
        })
        self.daily_stats.signals_sent += 1

    def log_scam_rejected(self):
        self.daily_stats.scams_rejected += 1

    def log_tier_a_move(self):
        self.daily_stats.tier_a_moves += 1

    def get_daily_stats(self) -> DailyStats:
        today = self._today()
        if self.daily_stats.date != today:
            self.daily_stats = DailyStats(date=today)
        return self.daily_stats

    def get_signals_today(self) -> List[dict]:
        cutoff = time.time() - 86400
        return [s for s in self.signals_log if s["time"] > cutoff]

    # ── Persistence ─────────────────────────────────────────────────────────

    def _prune_tokens(self):
        """Evict stale tokens so the store (and state.json) can't grow forever.
        Keeps anything alerted-but-not-exited (an open position) regardless of age."""
        cutoff = time.time() - self.MAX_TOKEN_AGE
        self.tokens = {
            addr: t for addr, t in self.tokens.items()
            if t.last_updated > cutoff or (t.alerted and not t.exit_alerted)
        }

    def save(self):
        self._prune_tokens()
        os.makedirs("data", exist_ok=True)
        payload = {
            "tokens": {k: asdict(v) for k, v in self.tokens.items()},
            "daily_stats": asdict(self.daily_stats),
            "signals_log": self.signals_log[-500:],   # keep last 500
        }
        with open(self.PERSIST_PATH, "w") as f:
            json.dump(payload, f, indent=2)

    def _load(self):
        if not os.path.exists(self.PERSIST_PATH):
            return
        try:
            with open(self.PERSIST_PATH) as f:
                payload = json.load(f)
            for addr, data in payload.get("tokens", {}).items():
                self.tokens[addr] = TokenRecord(**data)
            stats = payload.get("daily_stats", {})
            if stats.get("date") == self._today():
                self.daily_stats = DailyStats(**stats)
            self.signals_log = payload.get("signals_log", [])
            print(f"[store] Loaded {len(self.tokens)} tokens from disk.")
        except Exception as e:
            print(f"[store] Could not load state: {e}")

    @staticmethod
    def _today() -> str:
        from datetime import date
        return date.today().isoformat()
