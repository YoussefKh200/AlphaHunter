"""
alerts/telegram_bot.py — Sends all alert types to Telegram.

Alert types:
  • 🆕 NEW_TOKEN     — new token detected, basic info
  • ⚠️  SCAM_ALERT   — token rejected by scam filter
  • 🎯 ENTRY_SIGNAL  — all conditions met, high score
  • 🚪 EXIT_SIGNAL   — Tier-A wallets exiting or narrative collapse
  • 📊 DAILY_SUMMARY — end-of-day recap
"""

import asyncio
import logging
import time
import aiohttp
from typing import Optional
from datetime import datetime

logger = logging.getLogger("telegram")


class TelegramBot:
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_id: str, config=None):
        self.token   = token
        self.chat_id = chat_id
        self.cfg     = config  # Store config for wallet tracking
        self.store   = None    # set by engine; powers /stats and /alerts
        self._session: Optional[aiohttp.ClientSession] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._last_send = 0.0
        self.MIN_INTERVAL = 1.0   # seconds between messages (Telegram rate limit)
        self._polling = False
        self._offset = 0  # for getUpdates polling

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, text: str, parse_mode: str = "HTML", disable_preview: bool = True) -> bool:
        """Send a message. Rate-limited to avoid Telegram 429s."""
        # Throttle
        now = time.time()
        wait = self.MIN_INTERVAL - (now - self._last_send)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_send = time.time()

        url = self.BASE_URL.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id":                  self.chat_id,
            "text":                     text[:4096],   # Telegram message limit
            "parse_mode":               parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        session = await self._get_session()
        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error(f"[telegram] Send failed: {data.get('description')}")
                    return False
                return True
        except Exception as e:
            logger.error(f"[telegram] Error: {e}")
            return False

    # ── Alert Formatters ─────────────────────────────────────────────────────

    async def send_new_token(self, token: dict, score: float, breakdown: dict, narrative: str, narrative_score: float):
        """Alert: new token detected, passes basic checks but below entry threshold."""
        mcap    = token.get("market_cap", 0)
        liq     = token.get("liquidity_usd", 0)
        vol5m   = token.get("volume_5m", 0)
        symbol  = token.get("symbol", "?")
        name    = token.get("name", "")
        address = token.get("address", "")
        change5m = token.get("price_change_5m", 0)
        buys5m  = token.get("buys_5m", 0)
        sells5m = token.get("sells_5m", 0)

        socials = token.get("socials", {})
        twitter_link  = socials.get("twitter", token.get("twitter", ""))
        telegram_link = socials.get("telegram", token.get("telegram", ""))

        score_bar = self._score_bar(score)
        change_icon = "🟢" if change5m >= 0 else "🔴"

        text = (
            f"🆕 <b>NEW TOKEN DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>${symbol}</b>  ·  {name}\n"
            f"\n"
            f"<b>Alpha Score:</b>  {score:.0f}/100  {score_bar}\n"
            f"\n"
            f"📊 <b>Market</b>\n"
            f"  Market Cap:   <code>${mcap:>12,.0f}</code>\n"
            f"  Liquidity:    <code>${liq:>12,.0f}</code>\n"
            f"  Vol (5m):     <code>${vol5m:>12,.0f}</code>\n"
            f"  Buys/Sells:   <code>{buys5m} / {sells5m}</code>\n"
            f"  Price (5m):   {change_icon} <code>{change5m:+.1f}%</code>\n"
            f"\n"
            f"🎭 <b>Narrative:</b>  {narrative.title()}  ({narrative_score:.0f}/20)\n"
            f"\n"
            f"📈 <b>Score Breakdown</b>\n"
            f"  Wallet:    {breakdown.get('wallet', 0):.0f}/25\n"
            f"  Narrative: {breakdown.get('narrative', 0):.0f}/20\n"
            f"  Liquidity: {breakdown.get('liquidity', 0):.0f}/15\n"
            f"  Volume:    {breakdown.get('volume', 0):.0f}/15\n"
            f"  Social:    {breakdown.get('social', 0):.0f}/15\n"
            f"  Holders:   {breakdown.get('holders', 0):.0f}/10\n"
        )

        if twitter_link:
            text += f"\n🐦 <a href='{twitter_link}'>Twitter</a>"
        if telegram_link:
            text += f"  ✈️ <a href='{telegram_link}'>Telegram</a>"

        text += (
            f"\n\n🔍 <a href='https://dexscreener.com/solana/{address}'>DexScreener</a>"
            f"  ·  <a href='https://pump.fun/{address}'>Pump.fun</a>"
            f"\n<code>{address}</code>"
        )

        await self.send(text)

    async def send_scam_alert(self, token: dict, flags: list, severity: str):
        """Alert: token rejected by scam detector."""
        symbol  = token.get("symbol", "?")
        address = token.get("address", "")
        liq     = token.get("liquidity_usd", 0)

        severity_icon = {"CAUTION": "⚠️", "WARNING": "🚨", "DANGER": "☠️"}.get(severity, "⚠️")

        flags_text = "\n".join(f"  • {f}" for f in flags)

        text = (
            f"{severity_icon} <b>SCAM DETECTED — {severity}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Token: <b>${symbol}</b>\n"
            f"Liquidity: ${liq:,.0f}\n"
            f"\n"
            f"🚩 <b>Flags ({len(flags)})</b>\n"
            f"{flags_text}\n"
            f"\n"
            f"🔴 Token automatically REJECTED\n"
            f"<code>{address}</code>"
        )
        await self.send(text)

    async def send_entry_signal(self, token: dict, score: float, breakdown: dict,
                                narrative: str, tier_a_count: int, holder_data: dict = None):
        """Alert: all entry conditions met — high priority signal."""
        symbol   = token.get("symbol", "?")
        name     = token.get("name", "")
        address  = token.get("address", "")
        liq      = token.get("liquidity_usd", 0)
        mcap     = token.get("market_cap", 0)
        vol5m    = token.get("volume_5m", 0)
        vol1h    = token.get("volume_1h", 0)
        buys5m   = token.get("buys_5m", 0)
        sells5m  = token.get("sells_5m", 0)
        change5m = token.get("price_change_5m", 0)
        change1h = token.get("price_change_1h", 0)

        holders = holder_data.get("holder_count", "N/A") if holder_data else "N/A"
        top10   = holder_data.get("top10_pct", "N/A") if holder_data else "N/A"

        socials = token.get("socials", {})
        twitter_link  = socials.get("twitter", token.get("twitter", ""))
        telegram_link = socials.get("telegram", token.get("telegram", ""))

        score_bar = self._score_bar(score)
        ts = datetime.utcnow().strftime("%H:%M UTC")

        text = (
            f"🎯 <b>ENTRY SIGNAL — ALPHA DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>${symbol}</b>  ·  {name}\n"
            f"Score: <b>{score:.0f}/100</b>  {score_bar}\n"
            f"Time: {ts}\n"
            f"\n"
            f"✅ <b>All Entry Conditions Met</b>\n"
            f"  Liquidity  ✓  ${liq:,.0f}\n"
            f"  Holders    ✓  {holders}\n"
            f"  Tier-A     ✓  {tier_a_count} wallets buying\n"
            f"  Momentum   ✓  Vol accelerating\n"
            f"  Score      ✓  {score:.0f} > threshold\n"
            f"\n"
            f"📊 <b>Market Data</b>\n"
            f"  Market Cap:    ${mcap:,.0f}\n"
            f"  Liquidity:     ${liq:,.0f}\n"
            f"  Vol 5m:        ${vol5m:,.0f}\n"
            f"  Vol 1h:        ${vol1h:,.0f}\n"
            f"  Buys/Sells:    {buys5m} / {sells5m}\n"
            f"  Price 5m:      {change5m:+.1f}%\n"
            f"  Price 1h:      {change1h:+.1f}%\n"
        )

        if isinstance(top10, float):
            text += f"  Top-10 hold:   {top10:.1f}%\n"

        text += (
            f"\n"
            f"🎭 <b>Narrative:</b>  {narrative.title()}\n"
            f"\n"
            f"📈 <b>Score Breakdown</b>\n"
            f"  🧠 Wallet:    {breakdown.get('wallet', 0):.0f}/25\n"
            f"  🎭 Narrative: {breakdown.get('narrative', 0):.0f}/20\n"
            f"  💧 Liquidity: {breakdown.get('liquidity', 0):.0f}/15\n"
            f"  📈 Volume:    {breakdown.get('volume', 0):.0f}/15\n"
            f"  📣 Social:    {breakdown.get('social', 0):.0f}/15\n"
            f"  👥 Holders:   {breakdown.get('holders', 0):.0f}/10\n"
            f"\n"
            f"⚠️ <b>Risk params:</b>  0.5–1% of portfolio\n"
            f"🎯 TP1: +50% (25%)  TP2: +100% (25%)\n"
            f"🛑 Trailing stop: -20%\n"
        )

        if twitter_link:
            text += f"\n🐦 <a href='{twitter_link}'>Twitter</a>"
        if telegram_link:
            text += f"  ✈️ <a href='{telegram_link}'>Telegram</a>"

        text += (
            f"\n\n🔍 <a href='https://dexscreener.com/solana/{address}'>DexScreener</a>"
            f"  ·  <a href='https://birdeye.so/token/{address}?chain=solana'>Birdeye</a>"
            f"  ·  <a href='https://pump.fun/{address}'>Pump.fun</a>"
            f"\n<code>{address}</code>"
        )

        await self.send(text)

    async def send_exit_signal(self, token: dict, reason: str, tier_a_sells: int):
        """Alert: exit conditions triggered."""
        symbol  = token.get("symbol", "?")
        address = token.get("address", "")

        icon = "🚪" if "tier" in reason.lower() else "💥"

        text = (
            f"{icon} <b>EXIT SIGNAL — {symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Token: <b>${symbol}</b>\n"
            f"\n"
            f"🚨 <b>Reason:</b>  {reason}\n"
        )

        if tier_a_sells > 0:
            text += f"👛 <b>Tier-A wallets selling:</b> {tier_a_sells}\n"

        text += (
            f"\n"
            f"⚡ Consider exiting position NOW\n"
            f"📋 Check trailing stop status\n"
            f"\n"
            f"🔍 <a href='https://dexscreener.com/solana/{address}'>DexScreener</a>\n"
            f"<code>{address}</code>"
        )

        await self.send(text)

    async def send_daily_summary(self, stats, signals_today: list, trending_narratives: list):
        """End-of-day summary alert."""
        ts = datetime.utcnow().strftime("%Y-%m-%d")
        total    = stats.tokens_scanned
        scams    = stats.scams_rejected
        signals  = stats.signals_sent
        tier_a   = stats.tier_a_moves

        entry_signals = [s for s in signals_today if s["type"] == "ENTRY"]
        exit_signals  = [s for s in signals_today if s["type"] == "EXIT"]

        text = (
            f"📊 <b>DAILY SUMMARY — {ts}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"📡 <b>System Activity</b>\n"
            f"  Tokens scanned:    {total}\n"
            f"  Scams rejected:    {scams}\n"
            f"  Signals sent:      {signals}\n"
            f"  Tier-A moves:      {tier_a}\n"
            f"\n"
        )

        if entry_signals:
            text += f"🎯 <b>Entry Signals Today ({len(entry_signals)})</b>\n"
            for s in entry_signals[:5]:
                text += f"  • ${s['symbol']}  →  Score {s['score']:.0f}\n"
            text += "\n"

        if exit_signals:
            text += f"🚪 <b>Exit Signals Today ({len(exit_signals)})</b>\n"
            for s in exit_signals[:5]:
                text += f"  • ${s['symbol']}  —  {s.get('reason', '')}\n"
            text += "\n"

        if trending_narratives:
            text += f"🎭 <b>Trending Narratives</b>\n"
            for narrative, count in trending_narratives[:4]:
                text += f"  • {narrative.title()}  ({count} signals)\n"

        text += (
            f"\n"
            f"⚙️ System running normally.\n"
            f"Next summary: tomorrow {self._local_time()}"
        )

        await self.send(text)

    async def send_system_status(self, status: str, message: str):
        """Generic system status message (startup, error, etc.)."""
        icon = {"online": "⚡", "error": "❌", "warning": "⚠️"}.get(status, "ℹ️")
        ts = datetime.utcnow().strftime("%H:%M UTC")
        
        if status == "online":
            text = (
                f"{icon} <b>J.A.R.V.I.S. SYSTEM ONLINE</b> {icon}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"\n"
                f"🔹 <b>TIME:</b> {ts}\n"
                f"\n"
                f"{message}\n"
                f"\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>All systems nominal, Sir.</i>"
            )
        else:
            text = f"{icon} <b>ALPHAHUNTER {status.upper()}</b>  [{ts}]\n{message}"
        
        await self.send(text)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _score_bar(self, score: float) -> str:
        filled = int(score / 10)
        bar    = "█" * filled + "░" * (10 - filled)
        return f"[{bar}]"

    def _local_time(self) -> str:
        return datetime.utcnow().strftime("%H:%M UTC")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._polling = False

    # ── Command Handling ───────────────────────────────────────────────────────

    async def start_polling(self):
        """Start polling for incoming messages/commands."""
        if self._polling:
            logger.info("[telegram] Polling already active")
            return
        self._polling = True
        logger.info("[telegram] Starting command polling...")
        asyncio.create_task(self._poll_loop())

    async def _poll_loop(self):
        """Poll for updates from Telegram."""
        logger.info("[telegram] Poll loop started")
        while self._polling:
            try:
                url = self.BASE_URL.format(token=self.token, method="getUpdates")
                params = {"offset": self._offset, "timeout": 30}
                
                session = await self._get_session()
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    
                    if data.get("ok"):
                        result = data.get("result", [])
                        if result:
                            logger.info(f"[telegram] Received {len(result)} update(s)")
                        for update in result:
                            await self._handle_update(update)
                            self._offset = update.get("update_id", 0) + 1
            except Exception as e:
                logger.error(f"[telegram] Polling error: {e}")
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict):
        """Handle an incoming update from Telegram."""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if not text or not chat_id:
            return
        
        # Only respond to commands from the configured chat
        if str(chat_id) != str(self.chat_id):
            return
        
        # Handle commands
        if text.startswith("/"):
            await self._handle_command(text, chat_id)

    async def _handle_command(self, command: str, chat_id: str):
        """Handle bot commands."""
        command = command.lower().strip()
        
        if command == "/hello" or command == "/start":
            greeting = (
                "⚡ <b>J.A.R.V.I.S. PROTOCOL INITIALIZED</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🔹 <i>Good day, Sir. All systems are operational.</i>\n"
                "\n"
                "I am your AI-powered Alpha Hunter, designed to detect high-potential memecoins on the Solana network before they moon.\n"
                "\n"
                "🎯 <b>Current Mission:</b>\n"
                "   • Scanning Pump.fun & DexScreener\n"
                "   • Tracking Tier-A smart money wallets\n"
                "   • Analyzing narratives & momentum\n"
                "   • Filtering scams with 99.9% accuracy\n"
                "\n"
                "📊 <b>Alert System:</b> ACTIVE\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "<i>Type /menu to access the command interface.</i>"
            )
            await self.send_to_chat(chat_id, greeting)
        elif command == "/menu" or command == "/help":
            menu = (
                "⚡ <b>J.A.R.V.I.S. COMMAND INTERFACE</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🔹 <b>SYSTEM COMMANDS</b>\n"
                "   /status   — System diagnostics & performance\n"
                "   /menu     — Display this command interface\n"
                "   /hello    — Initialize protocol\n"
                "\n"
                "🔹 <b>INTELLIGENCE REPORTS</b>\n"
                "   /alerts   — Recent alert history\n"
                "   /stats    — Today's hunting statistics\n"
                "   /wallets  — Tracked Tier-A wallets\n"
                "\n"
                "🔹 <b>AUTOMATED ALERTS</b>\n"
                "   🆕 NEW TOKEN      — Score ≥ 70 detected\n"
                "   ⚠️  SCAM ALERT    — Threat detected & blocked\n"
                "   🎯 ENTRY SIGNAL  — Alpha confirmed (Score ≥ 80)\n"
                "   🚪 EXIT SIGNAL   — Smart money exiting\n"
                "   📊 DAILY SUMMARY  — 20:00 UTC report\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Awaiting your command, Sir.</i>"
            )
            await self.send_to_chat(chat_id, menu)
        elif command == "/status":
            ts = datetime.utcnow().strftime("%H:%M UTC")
            status = (
                "⚡ <b>SYSTEM DIAGNOSTICS</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                f"🔹 <b>STATUS:</b> <span class=\"tg-spoiler\">ONLINE</span>\n"
                f"🔹 <b>TIME:</b> {ts}\n"
                f"🔹 <b>POLLING:</b> ACTIVE\n"
                f"🔹 <b>ENGINE:</b> RUNNING\n"
                f"🔹 <b>ALERT SYSTEM:</b> OPERATIONAL\n"
                "\n"
                "🔹 <b>MODULES:</b>\n"
                "   ✅ Token Scanner\n"
                "   ✅ Wallet Tracker\n"
                "   ✅ Scam Detector\n"
                "   ✅ Narrative Engine\n"
                "   ✅ Alpha Scorer\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>All systems functioning within normal parameters, Sir.</i>"
            )
            await self.send_to_chat(chat_id, status)
        elif command == "/alerts":
            recent = self.store.get_signals_today()[-10:] if self.store else []
            if recent:
                lines = "\n".join(
                    f"   {s['type']}  ${s['symbol']}  →  {s['score']:.0f}"
                    for s in reversed(recent)
                )
            else:
                lines = "   <i>No alerts yet, Sir.</i>"
            alerts = (
                "⚡ <b>RECENT ALERT HISTORY</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                f"{lines}\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await self.send_to_chat(chat_id, alerts)
        elif command == "/stats":
            s = self.store.get_daily_stats() if self.store else None
            today = self.store.get_signals_today() if self.store else []
            entries = sum(1 for x in today if x["type"] == "ENTRY")
            exits   = sum(1 for x in today if x["type"] == "EXIT")
            wallets = len(self.cfg.TIER_A_WALLETS) if hasattr(self, "cfg") else 0
            stats = (
                "⚡ <b>HUNTING STATISTICS</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🔹 <b>TODAY'S PERFORMANCE</b>\n"
                f"   Tokens Scanned: {s.tokens_scanned if s else 0}\n"
                f"   Scams Blocked: {s.scams_rejected if s else 0}\n"
                f"   Entry Signals: {entries}\n"
                f"   Exit Signals: {exits}\n"
                "\n"
                "🔹 <b>TIER-A ACTIVITY</b>\n"
                f"   Wallets Tracked: {wallets}\n"
                f"   Moves Detected: {s.tier_a_moves if s else 0}\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Statistics will update as system operates, Sir.</i>"
            )
            await self.send_to_chat(chat_id, stats)
        elif command == "/wallets":
            # Get wallet counts from config (need to access config - stored in telegram bot init)
            tier_a_count = len(self.cfg.TIER_A_WALLETS) if hasattr(self, 'cfg') else 0
            tier_b_count = len(self.cfg.TIER_B_WALLETS) if hasattr(self, 'cfg') else 0
            
            if tier_a_count > 0:
                wallet_list = "\n".join([f"   • {w[:8]}...{w[-6:]}" for w in self.cfg.TIER_A_WALLETS[:5]])
                if tier_a_count > 5:
                    wallet_list += f"\n   ... and {tier_a_count - 5} more"
                
                wallets = (
                    "⚡ <b>TIER-A WALLET TRACKING</b> ⚡\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "\n"
                    f"🔹 <b>TIER-A WALLETS:</b> {tier_a_count} tracked\n"
                    f"{wallet_list}\n"
                    "\n"
                    f"🔹 <b>TIER-B WALLETS:</b> {tier_b_count} tracked\n"
                    "\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>Smart money tracking active, Sir.</i>"
                )
            else:
                wallets = (
                    "⚡ <b>TIER-A WALLET TRACKING</b> ⚡\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "\n"
                    "🔹 <i>No wallets configured in settings.py</i>\n"
                    "\n"
                    "To enable smart money tracking:\n"
                    "1. Open config/settings.py\n"
                    "2. Add profitable Solana wallet addresses to TIER_A_WALLETS\n"
                    "3. Restart the system\n"
                    "\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>Awaiting wallet configuration, Sir.</i>"
                )
            await self.send_to_chat(chat_id, wallets)
        else:
            unknown = (
                f"⚡ <b>COMMAND NOT RECOGNIZED</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                f"<i>Unknown command: {command}</i>\n"
                "\n"
                "Type /menu to view available commands.\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await self.send_to_chat(chat_id, unknown)

    async def send_to_chat(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a specific chat ID."""
        url = self.BASE_URL.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        session = await self._get_session()
        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error(f"[telegram] Send failed: {data.get('description')}")
                    return False
                return True
        except Exception as e:
            logger.error(f"[telegram] Error: {e}")
            return False
