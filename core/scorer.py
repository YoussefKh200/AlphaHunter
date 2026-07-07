"""
core/scorer.py — Computes the Alpha Score (0-100) for each token.

Score breakdown:
  Wallet Score      0-25  (smart money activity)
  Narrative Score   0-20  (trend detection)
  Liquidity Score   0-15  (pool depth)
  Volume Score      0-15  (momentum)
  Social Score      0-15  (community signals)
  Holder Score      0-10  (distribution quality)
  ─────────────────────
  TOTAL             0-100
"""

import math
import logging
from typing import Tuple

logger = logging.getLogger("scorer")


class Scorer:
    def __init__(self, config):
        self.cfg = config

    def compute(
        self,
        token: dict,
        holder_data: dict = None,
        narrative_score: float = 0.0,
        wallet_score: float = 0.0,
    ) -> Tuple[float, dict]:
        """
        Returns (total_score, breakdown_dict).
        """
        breakdown = {}

        # ── 1. Wallet Score (0-25) ────────────────────────────────────────
        breakdown["wallet"] = round(wallet_score, 1)

        # ── 2. Narrative Score (0-20) ─────────────────────────────────────
        breakdown["narrative"] = round(min(narrative_score, 20.0), 1)

        # ── 3. Liquidity Score (0-15) ─────────────────────────────────────
        liq = token.get("liquidity_usd", 0)
        breakdown["liquidity"] = self._liq_score(liq)

        # ── 4. Volume Score (0-15) ────────────────────────────────────────
        vol_5m  = token.get("volume_5m", 0)
        vol_1h  = token.get("volume_1h", 0)
        vol_24h = token.get("volume_24h", 0)
        buys    = token.get("buys_5m", 0)
        sells   = token.get("sells_5m", 0)
        breakdown["volume"] = self._vol_score(vol_5m, vol_1h, vol_24h, buys, sells)

        # ── 5. Social Score (0-15) ────────────────────────────────────────
        socials = token.get("socials", {})
        has_twitter  = "twitter" in socials or bool(token.get("twitter"))
        has_telegram = "telegram" in socials or bool(token.get("telegram"))
        has_website  = bool(token.get("websites")) or bool(token.get("website"))
        reply_count  = token.get("reply_count", 0)
        breakdown["social"] = self._social_score(has_twitter, has_telegram, has_website, reply_count)

        # ── 6. Holder Score (0-10) ────────────────────────────────────────
        if holder_data:
            holders  = holder_data.get("holder_count", 0)
            top10    = holder_data.get("top10_pct", 100)
            breakdown["holders"] = self._holder_score(holders, top10)
        else:
            breakdown["holders"] = 3.0  # neutral default when no data

        # ── Total ─────────────────────────────────────────────────────────
        total = sum(breakdown.values())
        total = round(min(total, 100.0), 1)

        logger.debug(
            f"[scorer] {token.get('symbol', '?')} → {total} "
            f"(W:{breakdown['wallet']} N:{breakdown['narrative']} "
            f"L:{breakdown['liquidity']} V:{breakdown['volume']} "
            f"S:{breakdown['social']} H:{breakdown['holders']})"
        )
        return total, breakdown

    # ── Sub-scorers ──────────────────────────────────────────────────────────

    def _liq_score(self, liq_usd: float) -> float:
        """
        0  → < $20k
        5  → $20k
        10 → $50k
        13 → $100k
        15 → $500k+
        """
        if liq_usd < 20_000:   return 0.0
        if liq_usd < 50_000:   return 5.0 + (liq_usd - 20_000) / 30_000 * 5
        if liq_usd < 100_000:  return 10.0 + (liq_usd - 50_000) / 50_000 * 3
        if liq_usd < 500_000:  return 13.0 + (liq_usd - 100_000) / 400_000 * 2
        return 15.0

    def _vol_score(
        self,
        vol_5m: float,
        vol_1h: float,
        vol_24h: float,
        buys: int,
        sells: int,
    ) -> float:
        """Reward momentum (high buy volume, acceleration)."""
        score = 0.0

        # Volume absolute
        if vol_5m > 50_000:    score += 6.0
        elif vol_5m > 10_000:  score += 4.0
        elif vol_5m > 1_000:   score += 2.0

        # Buy/sell ratio
        total = buys + sells
        if total > 0:
            buy_ratio = buys / total
            if buy_ratio > 0.7:   score += 5.0
            elif buy_ratio > 0.5: score += 3.0
            elif buy_ratio > 0.3: score += 1.0

        # Volume acceleration (5m momentum vs 1h average)
        if vol_1h > 0:
            pace_1h = vol_1h / 12   # expected 5m vol if constant
            if vol_5m > pace_1h * 2:
                score += 4.0   # accelerating

        return round(min(score, 15.0), 1)

    def _social_score(
        self,
        has_twitter: bool,
        has_telegram: bool,
        has_website: bool,
        reply_count: int,
    ) -> float:
        score = 0.0
        if has_twitter:   score += 4.0
        if has_telegram:  score += 4.0
        if has_website:   score += 3.0
        # Community engagement
        if reply_count > 100:  score += 4.0
        elif reply_count > 20: score += 2.0
        elif reply_count > 5:  score += 1.0
        return round(min(score, 15.0), 1)

    def _holder_score(self, holder_count: int, top10_pct: float) -> float:
        """
        Rewards well-distributed supply with many holders.
        """
        score = 0.0
        # Holder count
        if holder_count > 1000:  score += 5.0
        elif holder_count > 500: score += 4.0
        elif holder_count > 200: score += 3.0
        elif holder_count > 100: score += 2.0
        elif holder_count > 50:  score += 1.0

        # Concentration penalty
        if top10_pct < 40:   score += 5.0
        elif top10_pct < 55: score += 3.0
        elif top10_pct < 70: score += 1.0
        # top10 >= 70% → no bonus (also flagged by scam detector)

        return round(min(score, 10.0), 1)

    def momentum_label(self, score: float) -> str:
        if score >= 85: return "🔥 ULTRA HIGH"
        if score >= 70: return "⚡ HIGH"
        if score >= 55: return "📈 MODERATE"
        if score >= 40: return "📊 LOW"
        return "😴 WEAK"
