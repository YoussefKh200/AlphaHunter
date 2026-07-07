"""
core/scam_detector.py — Auto-rejects tokens that fail quality filters.
Returns a list of flags; empty list = passed, non-empty = rejected.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger("scam_detector")


class ScamDetector:
    def __init__(self, config):
        self.cfg = config

    def check(self, token: dict, holder_data: dict = None) -> List[str]:
        """
        Run all scam checks against a token dict.
        Returns list of flag strings. Empty = clean, non-empty = reject.
        """
        flags = []

        # ── Liquidity ─────────────────────────────────────────────────────
        liquidity = token.get("liquidity_usd", 0)
        if liquidity < self.cfg.SCAM_MIN_LIQUIDITY:
            flags.append(f"Low liquidity: ${liquidity:,.0f} (min ${self.cfg.SCAM_MIN_LIQUIDITY:,})")

        # ── Market Cap sanity ─────────────────────────────────────────────
        mcap = token.get("market_cap", 0)
        if mcap == 0:
            flags.append("Zero market cap — likely unlaunched or rug")

        # ── Volume / Transaction activity ─────────────────────────────────
        buys  = token.get("buys_5m", 0)
        sells = token.get("sells_5m", 0)
        total_txns = buys + sells
        if total_txns == 0 and liquidity > 0:
            flags.append("Zero transactions in last 5 min — dead token")

        # ── Extreme sell pressure ─────────────────────────────────────────
        if total_txns > 5 and buys > 0:
            sell_ratio = sells / total_txns
            if sell_ratio > 0.85:
                flags.append(f"Extreme sell pressure: {sell_ratio:.0%} of txns are sells")

        # ── Price change extremes ─────────────────────────────────────────
        change_5m = token.get("price_change_5m", 0)
        if change_5m < -50:
            flags.append(f"Price dump: {change_5m:.1f}% in 5 min — possible rug")

        # ── Holder analysis (requires Birdeye data) ───────────────────────
        if holder_data:
            holders = holder_data.get("holder_count", 0)
            top10   = holder_data.get("top10_pct", 100)

            if holders < self.cfg.SCAM_MIN_HOLDERS:
                flags.append(f"Too few holders: {holders} (min {self.cfg.SCAM_MIN_HOLDERS})")

            if top10 > self.cfg.SCAM_MAX_TOP10_PCT:
                flags.append(f"Top-10 holders own {top10:.1f}% — centralized supply")

        # ── Contract-level risks (from token metadata) ────────────────────
        # These would come from on-chain data if integrated with Helius/Shyft
        mint_risk   = token.get("mint_authority", False)
        freeze_risk = token.get("freeze_authority", False)
        if mint_risk:
            flags.append("Mint authority still active — supply can be inflated")
        if freeze_risk:
            flags.append("Freeze authority active — wallets can be frozen")

        if flags:
            logger.info(f"[scam] REJECTED {token.get('symbol', '?')} — {len(flags)} flags: {flags[0]}")
        else:
            logger.debug(f"[scam] PASSED {token.get('symbol', '?')}")

        return flags

    def is_clean(self, token: dict, holder_data: dict = None) -> bool:
        return len(self.check(token, holder_data)) == 0

    def severity(self, flags: List[str]) -> str:
        """Classify overall scam risk level."""
        n = len(flags)
        if n == 0:
            return "CLEAN"
        elif n == 1:
            return "CAUTION"
        elif n == 2:
            return "WARNING"
        else:
            return "DANGER"
