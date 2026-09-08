from __future__ import annotations

import logging
from typing import Any

from services.sec.client import SECClient, sec_client

logger = logging.getLogger(__name__)

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_EXCHANGE_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def format_cik(cik: int | str) -> str:
    """Format CIK into a standard 10-digit zero-padded string."""
    clean = str(cik).strip().lstrip("0")
    if not clean:
        return "0000000000"
    return clean.zfill(10)


class SECCompanyService:
    """Service for resolving companies, CIK numbers, and SEC tickers."""

    def __init__(self, client: SECClient | None = None):
        self.client = client or sec_client
        self._ticker_map: dict[str, dict[str, Any]] | None = None
        self._cik_map: dict[str, dict[str, Any]] | None = None

    def _load_tickers(self) -> None:
        """Load SEC company tickers directory."""
        if self._ticker_map is not None:
            return

        self._ticker_map = {}
        self._cik_map = {}

        data = self.client.get_json(SEC_COMPANY_TICKERS_URL, cache_ttl_seconds=86400 * 3)
        if data and isinstance(data, dict):
            for item in data.values():
                cik_str = format_cik(item.get("cik_str", ""))
                ticker = str(item.get("ticker", "")).upper()
                title = str(item.get("title", ""))

                record = {
                    "cik": cik_str,
                    "ticker": ticker,
                    "name": title,
                }
                self._ticker_map[ticker] = record
                self._cik_map[cik_str] = record

                # Also register standard dash/dot variations for fast lookup
                ticker_dot = ticker.replace("-", ".").replace("/", ".")
                ticker_dash = ticker.replace(".", "-").replace("/", "-")
                ticker_clean = ticker.replace(".", "").replace("-", "").replace("/", "")

                self._ticker_map.setdefault(ticker_dot, record)
                self._ticker_map.setdefault(ticker_dash, record)
                self._ticker_map.setdefault(ticker_clean, record)

    def get_company_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        """Resolve ticker to SEC company record (CIK, name, ticker)."""
        clean_ticker = (ticker or "").strip().upper()
        if not clean_ticker:
            return None

        self._load_tickers()
        if not self._ticker_map:
            return None

        if clean_ticker in self._ticker_map:
            return dict(self._ticker_map[clean_ticker])

        for alt in (
            clean_ticker.replace("-", ".").replace("/", "."),
            clean_ticker.replace(".", "-").replace("/", "-"),
            clean_ticker.replace(".", "").replace("-", "").replace("/", ""),
        ):
            if alt in self._ticker_map:
                return dict(self._ticker_map[alt])

        return None

    def get_company_by_cik(self, cik: int | str) -> dict[str, Any] | None:
        """Resolve CIK to SEC company record."""
        cik_str = format_cik(cik)
        self._load_tickers()
        if self._cik_map and cik_str in self._cik_map:
            return dict(self._cik_map[cik_str])
        return None

    def search_companies(self, query: str, limit: int = 15) -> list[dict[str, Any]]:
        """Search SEC directory by ticker prefix or company name."""
        needle = (query or "").strip().lower()
        if not needle:
            return []

        self._load_tickers()
        if not self._ticker_map:
            return []

        exact_matches = []
        prefix_matches = []
        name_matches = []

        for ticker, record in self._ticker_map.items():
            t_lower = ticker.lower()
            n_lower = record["name"].lower()

            if t_lower == needle:
                exact_matches.append(record)
            elif t_lower.startswith(needle):
                prefix_matches.append(record)
            elif needle in n_lower:
                name_matches.append(record)

        combined = exact_matches + prefix_matches + name_matches
        return combined[:limit]


# Global singleton instance
sec_company_service = SECCompanyService()
