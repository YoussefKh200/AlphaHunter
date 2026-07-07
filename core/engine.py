"""
core/engine.py — Main orchestration loop.

Runs two async loops:
  1. Token loop (every FETCH_INTERVAL seconds)
     → Fetch new tokens from Pump.fun + DexScreener
     → Score, scam-check, alert

  2. Wallet loop (every WALLET_CHECK_INTERVAL seconds)
     → Poll Tier-A wallets for new activity
     → Check open signals for exit conditions

  3. Daily summary (once per day at DAILY_SUMMARY_HOUR)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from core.fetcher         import Fetcher
from core.scam_detector   import ScamDetector
from core.wallet_tracker  import WalletTracker
from core.scorer          import Scorer
from core.narrative_engine import NarrativeEngine
from alerts.telegram_bot  import TelegramBot
from data.store           import DataStore, TokenRecord

logger = logging.getLogger("engine")


class AlphaHunterEngine:
    def __init__(self, config):
        self.cfg = config

        # Components
        self.fetcher    = Fetcher()
        self.scam       = ScamDetector(config)
        self.scorer     = Scorer(config)
        self.narrative  = NarrativeEngine(config)
        self.wallet     = WalletTracker(config, self.fetcher)
        self.telegram   = TelegramBot(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, config)
        self.store      = DataStore()
        self.telegram.store = self.store   # let /stats and /alerts read real data

        self._last_daily_summary = None
        self._running = False

    # ── Entry Point ──────────────────────────────────────────────────────────

    async def run(self):
        self._running = True
        logger.info("AlphaHunter engine starting...")

        # Start Telegram command polling
        await self.telegram.start_polling()

        await self.telegram.send_system_status(
            "online",
            "🚀 AlphaHunter is live.\nMonitoring Pump.fun + DexScreener + Wallet tracking active."
        )

        # Run all loops concurrently
        await asyncio.gather(
            self._token_loop(),
            self._wallet_loop(),
            self._daily_summary_loop(),
            self._persist_loop(),
        )

    async def stop(self):
        self._running = False
        await self.fetcher.close()
        await self.telegram.close()
        self.store.save()
        logger.info("Engine stopped, state saved.")

    # ── Token Loop ───────────────────────────────────────────────────────────

    async def _token_loop(self):
        logger.info(f"[token_loop] Starting — polling every {self.cfg.FETCH_INTERVAL}s")
        while self._running:
            try:
                await self._process_new_tokens()
            except Exception as e:
                logger.error(f"[token_loop] Error: {e}", exc_info=True)
            await asyncio.sleep(self.cfg.FETCH_INTERVAL)

    async def _process_new_tokens(self):
        # Fetch from Pump.fun
        pf_tokens = await self.fetcher.get_pumpfun_new_tokens()
        logger.debug(f"[token_loop] Got {len(pf_tokens)} tokens from Pump.fun")

        # Fetch from DexScreener new listings
        dex_tokens = await self.fetcher.get_dex_new_pairs()
        logger.debug(f"[token_loop] Got {len(dex_tokens)} listings from DexScreener")

        # Merge address sets
        seen_in_batch = set()
        all_addresses = []

        for t in pf_tokens:
            addr = t.get("address", "")
            if addr and addr not in seen_in_batch:
                seen_in_batch.add(addr)
                all_addresses.append((addr, t))

        for t in dex_tokens:
            addr = t.get("address", "")
            if addr and addr not in seen_in_batch:
                seen_in_batch.add(addr)
                all_addresses.append((addr, {}))

        # Process each (limit concurrent fetches)
        semaphore = asyncio.Semaphore(5)
        tasks = [
            self._process_one_token(addr, base_data, semaphore)
            for addr, base_data in all_addresses
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_one_token(self, address: str, base_data: dict, sem: asyncio.Semaphore):
        async with sem:
            try:
                await self._evaluate_token(address, base_data)
            except Exception as e:
                logger.debug(f"[token] Error processing {address[:8]}: {e}")

    async def _evaluate_token(self, address: str, base_data: dict):
        # Skip if we've already fully processed + alerted this token recently
        existing = self.store.get_token(address)
        if existing and existing.alerted:
            # But still check for exit signal below
            await self._check_exit(existing)
            return

        # ── 1. Fetch enriched data from DexScreener ────────────────────────
        dex_data = await self.fetcher.get_dex_token(address)
        if not dex_data:
            # Token not yet on DEX — too early, skip
            return

        # Merge base_data (Pump.fun) with dex_data
        token = {**base_data, **dex_data}
        token["address"] = address

        # Skip tokens with no symbol
        if not token.get("symbol"):
            return

        # ── 2. Scam detection ──────────────────────────────────────────────
        holder_data = await self.fetcher.get_token_largest_accounts(address)
        flags = self.scam.check(token, holder_data)

        if flags:
            severity = self.scam.severity(flags)
            self.store.log_scam_rejected()
            # Only alert on WARNING/DANGER to avoid spam
            if severity in ("WARNING", "DANGER"):
                await self.telegram.send_scam_alert(token, flags, severity)
            logger.info(f"[engine] REJECTED {token['symbol']} ({severity}) — {flags[0]}")
            return

        # ── 3. Narrative detection ─────────────────────────────────────────
        narrative_label, narrative_score = self.narrative.detect(token)

        # ── 4. Wallet score ────────────────────────────────────────────────
        w_score     = self.wallet.wallet_score(address)
        tier_a_buys = self.wallet.count_tier_a_buying(address)

        # ── 5. Alpha score ─────────────────────────────────────────────────
        score, breakdown = self.scorer.compute(
            token,
            holder_data=holder_data,
            narrative_score=narrative_score,
            wallet_score=w_score,
        )

        # ── 6. Register token with wallet tracker ────────────────────
        self.wallet._watched_tokens.add(address)

        # ── 7. Store record ────────────────────────────────────────────────
        record = TokenRecord(
            address=address,
            symbol=token.get("symbol", ""),
            name=token.get("name", ""),
            price_usd=token.get("price_usd", 0),
            liquidity_usd=token.get("liquidity_usd", 0),
            volume_24h=token.get("volume_24h", 0),
            market_cap=token.get("market_cap", 0),
            holders=holder_data.get("holder_count", 0) if holder_data else 0,
            buys_5m=token.get("buys_5m", 0),
            sells_5m=token.get("sells_5m", 0),
            alpha_score=score,
            narrative=narrative_label,
            tier_a_buys=tier_a_buys,
            tier_a_sells=0,
            scam_flags=flags,
        )
        self.store.upsert_token(record)

        # ── 7. Decide what to send ─────────────────────────────────────────

        # High-confidence entry signal
        if self._is_entry_signal(token, score, tier_a_buys):
            logger.info(f"[engine] 🎯 ENTRY SIGNAL {token['symbol']} score={score:.0f}")
            await self.telegram.send_entry_signal(
                token, score, breakdown, narrative_label, tier_a_buys, holder_data
            )
            self.store.mark_alerted(address)
            self.store.log_signal("ENTRY", record)

        # Interesting token (above MIN but below ENTRY threshold)
        elif score >= self.cfg.MIN_ALPHA_SCORE:
            logger.info(f"[engine] 🆕 NEW TOKEN {token['symbol']} score={score:.0f}")
            await self.telegram.send_new_token(token, score, breakdown, narrative_label, narrative_score)
            self.store.mark_alerted(address)
            self.store.log_signal("NEW_TOKEN", record)

        else:
            logger.debug(f"[engine] Skip {token.get('symbol', '?')} score={score:.0f} (below threshold)")

    def _is_entry_signal(self, token: dict, score: float, tier_a_buys: int) -> bool:
        """All entry conditions from the spec must be true."""
        return all([
            score >= self.cfg.ENTRY_SIGNAL_SCORE,
            token.get("liquidity_usd", 0) >= self.cfg.MIN_LIQUIDITY_USD,
            tier_a_buys >= self.cfg.MIN_TIER_A_WALLETS,
            token.get("buys_5m", 0) > token.get("sells_5m", 0),  # momentum: buys > sells
        ])

    async def _check_exit(self, record: TokenRecord):
        """Check if an already-alerted token should trigger an exit signal."""
        if record.exit_alerted:
            return

        address = record.address
        reason  = None

        if self.wallet.is_exit_signal(address):
            tier_a_sells = self.wallet.count_tier_a_selling(address)
            reason = f"Tier-A wallets exiting ({tier_a_sells} wallets sold)"
            await self.telegram.send_exit_signal(
                {"symbol": record.symbol, "address": address},
                reason,
                tier_a_sells,
            )
            self.store.mark_exit_alerted(address)
            self.store.log_signal("EXIT", record, reason)
            self.store.log_tier_a_move()

    # ── Wallet Loop ──────────────────────────────────────────────────────────

    async def _wallet_loop(self):
        logger.info(f"[wallet_loop] Starting — polling every {self.cfg.WALLET_CHECK_INTERVAL}s")
        while self._running:
            try:
                await self.wallet.poll_all_wallets()
                # Check all open positions for exit signals
                for record in self.store.get_active_signals():
                    await self._check_exit(record)
            except Exception as e:
                logger.error(f"[wallet_loop] Error: {e}", exc_info=True)
            await asyncio.sleep(self.cfg.WALLET_CHECK_INTERVAL)

    # ── Daily Summary Loop ───────────────────────────────────────────────────

    async def _daily_summary_loop(self):
        logger.info("[summary_loop] Starting")
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                if now.hour == self.cfg.DAILY_SUMMARY_HOUR and now.minute < 2:
                    today_key = now.strftime("%Y-%m-%d")
                    if self._last_daily_summary != today_key:
                        self._last_daily_summary = today_key
                        await self._send_daily_summary()
            except Exception as e:
                logger.error(f"[summary_loop] Error: {e}")
            await asyncio.sleep(60)

    async def _send_daily_summary(self):
        stats    = self.store.get_daily_stats()
        signals  = self.store.get_signals_today()
        trending = self.narrative.trending_narratives()
        logger.info("[engine] Sending daily summary")
        await self.telegram.send_daily_summary(stats, signals, trending)

    # ── Persist Loop ─────────────────────────────────────────────────────────

    async def _persist_loop(self):
        """Save state to disk every 5 minutes."""
        while self._running:
            await asyncio.sleep(300)
            self.store.save()
            logger.debug("[engine] State persisted to disk.")
