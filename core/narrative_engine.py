"""
core/narrative_engine.py — Detects trending narrative categories from token metadata.
Assigns a narrative score 0-20 based on keyword matching + trend signals.
"""

import re
import logging
import time
from typing import Tuple, Dict

logger = logging.getLogger("narrative")


class NarrativeEngine:
    def __init__(self, config):
        self.cfg = config
        # narrative → recent detection timestamps (for trend velocity)
        self._trend_hits: Dict[str, list] = {k: [] for k in config.NARRATIVE_KEYWORDS}

    def detect(self, token: dict) -> Tuple[str, float]:
        """
        Returns (narrative_label, score_0_to_20).
        """
        # Build searchable text from all token fields
        text = " ".join([
            str(token.get("symbol", "")),
            str(token.get("name", "")),
            str(token.get("description", "")),
        ]).lower()

        text = re.sub(r"[^a-z0-9\s]", " ", text)
        words = set(text.split())

        best_narrative = "unknown"
        best_score     = 0.0
        best_matches   = 0

        for narrative, keywords in self.cfg.NARRATIVE_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in words or kw in text)
            if matches > best_matches:
                best_matches   = matches
                best_narrative = narrative

        if best_matches == 0:
            return "unknown", 0.0

        # Base score from match strength
        base = min(best_matches, 3) / 3 * 15   # up to 15

        # Trend velocity bonus: if this narrative is hot right now
        velocity_bonus = self._velocity_bonus(best_narrative)
        score = min(base + velocity_bonus, 20.0)

        # Log the hit for trend tracking
        self._record_hit(best_narrative)

        logger.debug(f"[narrative] {token.get('symbol')} → {best_narrative} score={score:.1f}")
        return best_narrative, round(score, 1)

    def _velocity_bonus(self, narrative: str) -> float:
        """Give up to 5 bonus points if this narrative is trending (many hits in last hour)."""
        hits = self._trend_hits.get(narrative, [])
        now  = time.time()
        recent = [h for h in hits if now - h < 3600]   # last 1 hour
        count  = len(recent)
        if count >= 10:
            return 5.0
        elif count >= 5:
            return 3.0
        elif count >= 2:
            return 1.5
        return 0.0

    def _record_hit(self, narrative: str):
        now = time.time()
        if narrative not in self._trend_hits:
            self._trend_hits[narrative] = []
        self._trend_hits[narrative].append(now)
        # Prune old hits
        self._trend_hits[narrative] = [
            h for h in self._trend_hits[narrative]
            if now - h < 7200  # keep last 2h
        ]

    def trending_narratives(self) -> list:
        """Return narratives sorted by recent activity."""
        now = time.time()
        results = []
        for narrative, hits in self._trend_hits.items():
            recent = len([h for h in hits if now - h < 3600])
            if recent > 0:
                results.append((narrative, recent))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:5]

    def narrative_emoji(self, narrative: str) -> str:
        return {
            "celebrity":  "🌟",
            "ai":         "🤖",
            "animals":    "🐸",
            "politics":   "🗳️",
            "gaming":     "🎮",
            "internet":   "🌐",
            "crypto":     "🔗",
            "unknown":    "❓",
        }.get(narrative, "❓")
