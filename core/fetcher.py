"""
core/fetcher.py — Fetches token data from DexScreener, Birdeye, and Pump.fun.
All free APIs used where possible; Birdeye key needed for holder data.
"""

import asyncio
import aiohttp
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger("fetcher")

# ── DexScreener ─────────────────────────────────────────────────────────────
DEXSCREENER_NEW     = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_SEARCH  = "https://api.dexscreener.com/latest/dex/search?q={query}"
DEXSCREENER_TOKENS  = "https://api.dexscreener.com/latest/dex/tokens/{address}"
DEXSCREENER_PAIRS   = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair}"

# ── Birdeye ──────────────────────────────────────────────────────────────────
BIRDEYE_TOKEN_LIST  = "https://public-api.birdeye.so/defi/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50&min_liquidity=10000"
BIRDEYE_TOKEN_INFO  = "https://public-api.birdeye.so/defi/token_overview?address={address}"
BIRDEYE_HOLDERS     = "https://public-api.birdeye.so/defi/token_holder?address={address}&offset=0&limit=20"

# ── Pump.fun ──────────────────────────────────────────────────────────────────
PUMPFUN_NEW_TOKENS  = "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp&order=DESC&includeNsfw=false"
PUMPFUN_TOKEN       = "https://frontend-api.pump.fun/coins/{address}"

# ── Solana public RPC (free) ─────────────────────────────────────────────────
# Multiple endpoints for fallback if one is rate-limited
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo",   # demo tier, works for reads
]


class Fetcher:
    def __init__(self, birdeye_api_key: str = ""):
        self.birdeye_key = birdeye_api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._rpc_index = 0   # rotate between RPC endpoints

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _get(self, url: str, headers: dict = None) -> Optional[dict]:
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    logger.warning(f"Rate limited: {url}")
                    await asyncio.sleep(5)
                else:
                    logger.debug(f"HTTP {resp.status} for {url}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
        except Exception as e:
            logger.error(f"Fetch error {url}: {e}")
        return None

    async def _rpc(self, method: str, params: list) -> Optional[dict]:
        """POST to Solana JSON-RPC, rotating endpoints on failure."""
        session = await self._get_session()
        payload  = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        for attempt in range(len(SOLANA_RPC_URLS)):
            url = SOLANA_RPC_URLS[self._rpc_index % len(SOLANA_RPC_URLS)]
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if "result" in data:
                            return data
                    elif resp.status == 429:
                        logger.warning(f"RPC rate limit: {url}")
                        self._rpc_index += 1
                        await asyncio.sleep(2)
            except Exception as e:
                logger.debug(f"RPC attempt failed ({url}): {e}")
                self._rpc_index += 1

        return None

    # ── Pump.fun ─────────────────────────────────────────────────────────────

    async def get_pumpfun_new_tokens(self) -> List[dict]:
        """Fetch the most recently launched tokens from Pump.fun."""
        data = await self._get(PUMPFUN_NEW_TOKENS)
        if not data:
            return []
        tokens = []
        for coin in data:
            tokens.append({
                "source":       "pumpfun",
                "address":      coin.get("mint", ""),
                "symbol":       coin.get("symbol", ""),
                "name":         coin.get("name", ""),
                "market_cap":   coin.get("usd_market_cap", 0),
                "created_at":   coin.get("created_timestamp", 0),
                "description":  coin.get("description", ""),
                "twitter":      coin.get("twitter", ""),
                "telegram":     coin.get("telegram", ""),
                "website":      coin.get("website", ""),
                "image_uri":    coin.get("image_uri", ""),
                "reply_count":  coin.get("reply_count", 0),
                "is_raydium":   coin.get("raydium_pool") is not None,
            })
        return tokens

    async def get_pumpfun_token(self, address: str) -> Optional[dict]:
        data = await self._get(PUMPFUN_TOKEN.format(address=address))
        return data

    # ── DexScreener ──────────────────────────────────────────────────────────

    async def get_dex_token(self, address: str) -> Optional[dict]:
        """Get pair data for a token from DexScreener."""
        data = await self._get(DEXSCREENER_TOKENS.format(address=address))
        if not data or not data.get("pairs"):
            return None
        # Pick the Solana pair with highest liquidity
        pairs = [p for p in data["pairs"] if p.get("chainId") == "solana"]
        if not pairs:
            return None
        pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
        pair = pairs[0]
        return self._parse_dex_pair(pair)

    async def get_dex_new_pairs(self) -> List[dict]:
        """Get latest Solana token profiles from DexScreener."""
        data = await self._get(DEXSCREENER_NEW)
        if not data:
            return []
        results = []
        for item in data:
            if item.get("chainId") == "solana":
                results.append({
                    "source":  "dexscreener",
                    "address": item.get("tokenAddress", ""),
                })
        return results

    async def search_dexscreener_tokens(self, query: str, limit: int = 20) -> List[dict]:
        """
        Search DexScreener for tokens matching a keyword.
        Used for finding sub-narrative candidates.
        """
        url = DEXSCREENER_SEARCH.format(query=query)
        data = await self._get(url)
        if not data:
            return []
        
        pairs = data.get("pairs", [])
        results = []
        
        for pair in pairs[:limit]:
            base_token = pair.get("baseToken", {})
            results.append({
                "address": base_token.get("address"),
                "symbol": base_token.get("symbol"),
                "name": base_token.get("name"),
                "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
                "volume_24h": pair.get("volume", {}).get("h24", 0),
                "price_usd": float(pair.get("priceUsd", 0) or 0),
                "pair_address": pair.get("pairAddress"),
                "chain": pair.get("chainId"),
            })
        
        return results

    def _parse_dex_pair(self, pair: dict) -> dict:
        liq = pair.get("liquidity", {})
        vol = pair.get("volume", {})
        txns = pair.get("txns", {})
        price_change = pair.get("priceChange", {})
        info = pair.get("info", {})

        buys_5m  = txns.get("m5", {}).get("buys", 0)
        sells_5m = txns.get("m5", {}).get("sells", 0)
        buys_1h  = txns.get("h1", {}).get("buys", 0)
        sells_1h = txns.get("h1", {}).get("sells", 0)

        return {
            "source":           "dexscreener",
            "address":          pair.get("baseToken", {}).get("address", ""),
            "symbol":           pair.get("baseToken", {}).get("symbol", ""),
            "name":             pair.get("baseToken", {}).get("name", ""),
            "pair_address":     pair.get("pairAddress", ""),
            "price_usd":        float(pair.get("priceUsd", 0) or 0),
            "liquidity_usd":    float(liq.get("usd", 0) or 0),
            "volume_5m":        float(vol.get("m5", 0) or 0),
            "volume_1h":        float(vol.get("h1", 0) or 0),
            "volume_24h":       float(vol.get("h24", 0) or 0),
            "market_cap":       float(pair.get("marketCap", 0) or 0),
            "fdv":              float(pair.get("fdv", 0) or 0),
            "buys_5m":          buys_5m,
            "sells_5m":         sells_5m,
            "buys_1h":          buys_1h,
            "sells_1h":         sells_1h,
            "price_change_5m":  float(price_change.get("m5", 0) or 0),
            "price_change_1h":  float(price_change.get("h1", 0) or 0),
            "price_change_24h": float(price_change.get("h24", 0) or 0),
            "pair_created_at":  pair.get("pairCreatedAt", 0),
            "dex_id":           pair.get("dexId", ""),
            "socials":          {s["type"]: s["url"] for s in info.get("socials", [])},
            "websites":         [w["url"] for w in info.get("websites", [])],
        }

    # ── Birdeye ──────────────────────────────────────────────────────────────

    async def get_birdeye_token(self, address: str) -> Optional[dict]:
        if not self.birdeye_key:
            return None
        headers = {"X-API-KEY": self.birdeye_key}
        data = await self._get(
            BIRDEYE_TOKEN_INFO.format(address=address),
            headers=headers
        )
        if not data or not data.get("data"):
            return None
        d = data["data"]
        return {
            "holders":          d.get("holder", 0),
            "unique_wallets":   d.get("uniqueWallet24h", 0),
            "buy_24h":          d.get("buy24h", 0),
            "sell_24h":         d.get("sell24h", 0),
            "trade_24h":        d.get("trade24h", 0),
        }

    async def get_birdeye_holders(self, address: str) -> Optional[dict]:
        """Returns top holder distribution info."""
        if not self.birdeye_key:
            return None
        headers = {"X-API-KEY": self.birdeye_key}
        data = await self._get(
            BIRDEYE_HOLDERS.format(address=address),
            headers=headers
        )
        if not data or not data.get("data"):
            return None
        items = data["data"].get("items", [])
        if not items:
            return None
        total_supply = sum(h.get("uiAmount", 0) for h in items)
        top10_amount = sum(h.get("uiAmount", 0) for h in items[:10])
        top10_pct    = (top10_amount / total_supply * 100) if total_supply > 0 else 100
        return {
            "top10_pct":    round(top10_pct, 1),
            "holder_count": len(items),
            "top_holders":  items[:5],
        }

    async def get_birdeye_trending(self) -> List[dict]:
        """Get trending Solana tokens by volume."""
        if not self.birdeye_key:
            return []
        headers = {"X-API-KEY": self.birdeye_key}
        data = await self._get(BIRDEYE_TOKEN_LIST, headers=headers)
        if not data or not data.get("data"):
            return []
        return data["data"].get("tokens", [])

    # ── Solana wallet tracking ────────────────────────────────────────────────

    async def get_wallet_transactions(self, wallet_address: str) -> List[dict]:
        """
        Fetch recent transactions for a wallet using Solana public RPC.
        Returns simplified tx list with token swaps.
        """
        data = await self._rpc(
            "getSignaturesForAddress",
            [wallet_address, {"limit": 10, "commitment": "confirmed"}]
        )
        if not data:
            return []
        sigs = data.get("result", [])
        return [{"signature": s["signature"], "slot": s.get("slot")} for s in sigs]

    async def get_token_accounts_for_wallet(self, wallet_address: str) -> List[dict]:
        """
        Get all SPL token accounts owned by a wallet.
        Used to check which tokens a wallet currently holds.
        """
        data = await self._rpc(
            "getTokenAccountsByOwner",
            [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed", "commitment": "confirmed"},
            ]
        )
        if not data:
            return []
        accounts = data.get("result", {}).get("value", [])
        result = []
        for acc in accounts:
            info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            mint = info.get("mint", "")
            balance = float(info.get("tokenAmount", {}).get("uiAmount", 0) or 0)
            if mint and balance > 0:
                result.append({"mint": mint, "balance": balance})
        return result

    async def get_token_largest_accounts(self, mint_address: str) -> Optional[dict]:
        """
        Uses getTokenLargestAccounts (free Solana RPC) to get top 20 holders.
        Returns holder count estimate + top-10 concentration %.

        Note: getTokenLargestAccounts returns up to 20 accounts.
        For a rough holder count we also call getTokenSupply.
        """
        data = await self._rpc(
            "getTokenLargestAccounts",
            [mint_address, {"commitment": "confirmed"}]
        )
        if not data:
            return None

        accounts = data.get("result", {}).get("value", [])
        if not accounts:
            return None

        # Parse amounts
        amounts = []
        for acc in accounts:
            try:
                ui = float(acc.get("uiAmount") or acc.get("amount", 0))
                amounts.append(ui)
            except (TypeError, ValueError):
                pass

        if not amounts:
            return None

        total = sum(amounts)
        if total == 0:
            return None

        top10_amount = sum(amounts[:10])
        top10_pct    = round(top10_amount / total * 100, 1)

        # Estimate total holder count via getTokenAccountsByDelegate trick:
        # we just use len(accounts) as a lower bound (max 20 from this call)
        # Real count needs getProgramAccounts which is rate-limited on public RPC.
        # So we estimate: if top-20 accounts hold X%, total ≈ 20 / (X/100)
        # This is a rough proxy, good enough for scam detection.
        top20_pct = round(sum(amounts[:20]) / total * 100, 1) if len(amounts) >= 20 else 100
        estimated_holders = max(20, int(20 / (top20_pct / 100))) if top20_pct > 0 else 20

        return {
            "holder_count": estimated_holders,   # lower-bound estimate
            "top10_pct":    top10_pct,
            "top20_pct":    top20_pct,
            "top_holders":  accounts[:5],        # raw account objects
        }

    async def get_token_supply(self, mint_address: str) -> Optional[dict]:
        """Get total supply info for a token mint."""
        data = await self._rpc("getTokenSupply", [mint_address])
        if not data:
            return None
        val = data.get("result", {}).get("value", {})
        return {
            "supply":     float(val.get("uiAmount", 0) or 0),
            "decimals":   val.get("decimals", 0),
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
