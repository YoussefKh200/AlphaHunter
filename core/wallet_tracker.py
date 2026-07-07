"""
core/wallet_tracker.py — Tracks Tier-A smart-money wallets.
Detects when known wallets buy or sell a token and assigns wallet scores.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger("wallet_tracker")


class WalletTracker:
    def __init__(self, config, fetcher):
        self.cfg     = config
        self.fetcher = fetcher

        # wallet_address → list of {token, action, time, tx}
        self.activity: Dict[str, List[dict]] = defaultdict(list)

        # token_address → {wallet_address → "buy"/"sell"}
        self.token_wallet_map: Dict[str, Dict[str, str]] = defaultdict(dict)

        # Last seen tx signature per wallet (to detect new activity)
        self.last_sig: Dict[str, str] = {}

        # Set of token addresses we are actively scoring (populated by engine)
        self._watched_tokens: set = set()

        # Tier classification
        self.tier_map: Dict[str, str] = {}
        self._build_tier_map()

    def _build_tier_map(self):
        for addr in self.cfg.TIER_A_WALLETS:
            self.tier_map[addr] = "A"
        for addr in self.cfg.TIER_B_WALLETS:
            self.tier_map[addr] = "B"

    def get_tier(self, wallet: str) -> str:
        return self.tier_map.get(wallet, "unknown")

    async def poll_all_wallets(self):
        """Check all tracked wallets for new transactions."""
        all_wallets = list(self.cfg.TIER_A_WALLETS) + list(self.cfg.TIER_B_WALLETS)
        if not all_wallets:
            logger.warning("[wallet] No wallets configured in TIER_A_WALLETS / TIER_B_WALLETS")
            return

        tasks = [self._poll_wallet(w) for w in all_wallets]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_wallet(self, wallet: str):
        """
        Fetch latest txns + current token holdings for one wallet.
        Uses two free RPC calls:
          1. getSignaturesForAddress  → detect new activity
          2. getTokenAccountsByOwner → see what tokens wallet currently holds
        Any token the wallet holds that we are tracking → record as buy.
        Any token we tracked as buy but wallet no longer holds → record as sell.
        """
        txns = await self.fetcher.get_wallet_transactions(wallet)
        if not txns:
            return

        latest_sig = txns[0]["signature"] if txns else None
        if not latest_sig:
            return

        if self.last_sig.get(wallet) == latest_sig:
            return  # Nothing new since last poll

        self.last_sig[wallet] = latest_sig
        tier = self.get_tier(wallet)
        logger.info(f"[wallet] Tier-{tier} {wallet[:8]}... new tx detected")

        # ── Snapshot current token holdings ───────────────────────────────
        held_tokens = await self.fetcher.get_token_accounts_for_wallet(wallet)
        held_mints  = {t["mint"] for t in held_tokens}

        # Previously tracked as buy → now gone from wallet = sold
        prev_buys = {
            token_addr
            for token_addr, wallets in self.token_wallet_map.items()
            if wallets.get(wallet) == "buy"
        }
        for token_addr in prev_buys:
            if token_addr not in held_mints:
                self.record_token_sell(wallet, token_addr)
                logger.info(f"[wallet] Tier-{tier} {wallet[:8]}... SOLD {token_addr[:8]}")

        # Newly held tokens that we are actively tracking → buy signal
        for mint in held_mints:
            if mint in self.token_wallet_map or mint in self._watched_tokens:
                if self.token_wallet_map.get(mint, {}).get(wallet) != "buy":
                    self.record_token_buy(wallet, mint)
                    logger.info(f"[wallet] Tier-{tier} {wallet[:8]}... HOLDS {mint[:8]}")

        # Record raw tx activity
        for tx in txns[:3]:
            self.activity[wallet].append({
                "signature": tx["signature"],
                "slot":      tx.get("slot"),
                "time":      time.time(),
                "tier":      tier,
            })
        if len(self.activity[wallet]) > 100:
            self.activity[wallet] = self.activity[wallet][-100:]

    def record_token_buy(self, wallet: str, token_address: str):
        """Manually record when we detect a wallet bought a token."""
        self.token_wallet_map[token_address][wallet] = "buy"
        self.activity[wallet].append({
            "action": "buy", "token": token_address, "time": time.time()
        })

    def record_token_sell(self, wallet: str, token_address: str):
        """Manually record when we detect a wallet sold a token."""
        self.token_wallet_map[token_address][wallet] = "sell"
        self.activity[wallet].append({
            "action": "sell", "token": token_address, "time": time.time()
        })

    def get_tier_a_buys(self, token_address: str) -> List[str]:
        """Return list of Tier-A wallets currently holding (bought) this token."""
        wallet_actions = self.token_wallet_map.get(token_address, {})
        return [
            w for w, action in wallet_actions.items()
            if action == "buy" and self.tier_map.get(w) == "A"
        ]

    def get_tier_a_sells(self, token_address: str) -> List[str]:
        """Return list of Tier-A wallets that sold this token."""
        wallet_actions = self.token_wallet_map.get(token_address, {})
        return [
            w for w, action in wallet_actions.items()
            if action == "sell" and self.tier_map.get(w) == "A"
        ]

    def count_tier_a_buying(self, token_address: str) -> int:
        return len(self.get_tier_a_buys(token_address))

    def count_tier_a_selling(self, token_address: str) -> int:
        return len(self.get_tier_a_sells(token_address))

    def is_exit_signal(self, token_address: str) -> bool:
        """True if enough Tier-A wallets have exited to trigger emergency exit."""
        sells = self.count_tier_a_selling(token_address)
        buys  = self.count_tier_a_buying(token_address)
        if buys == 0:
            return False
        # Exit signal if >50% of initial buyers have sold
        return sells >= max(2, buys // 2)

    def get_recent_tier_a_moves(self, limit: int = 5) -> List[dict]:
        """Return the most recent Tier-A wallet activities across all wallets."""
        moves = []
        for wallet in self.cfg.TIER_A_WALLETS:
            for act in self.activity.get(wallet, []):
                moves.append({**act, "wallet": wallet[:8] + "..."})
        moves.sort(key=lambda x: x.get("time", 0), reverse=True)
        return moves[:limit]

    def wallet_score(self, token_address: str) -> float:
        """
        Score 0-25 based on Tier-A wallet activity.
        25 = 3+ Tier-A wallets buying, no sells.
        """
        buys  = self.count_tier_a_buying(token_address)
        sells = self.count_tier_a_selling(token_address)

        if buys == 0:
            return 0.0
        base = min(buys, 3) / 3 * 25  # max 25 at 3+ buys
        penalty = sells * 4
        return max(0.0, base - penalty)
