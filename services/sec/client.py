from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Default User-Agent header required by SEC EDGAR fair access policy: Sample Company AdminContact@<sample company domain>.com
DEFAULT_USER_AGENT = "InvestiCore Research Workstation contact@investicore.local"
MIN_REQUEST_INTERVAL_SECONDS = 0.12  # Limits to ~8.3 requests/second, strictly under SEC 10 req/s limit


class SECClient:
    """HTTP Client for SEC EDGAR APIs conforming to SEC Fair Access guidelines.

    - Custom descriptive User-Agent
    - Rate-limiting (max 10 requests/sec)
    - Disk-based caching for filings and metadata
    - Exponential backoff retry logic
    """

    def __init__(
        self,
        user_agent: str | None = None,
        cache_dir: str | Path | None = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.user_agent = (
            user_agent
            or os.getenv("SEC_USER_AGENT")
            or os.getenv("INVESTICORE_SEC_USER_AGENT")
            or self._get_streamlit_secret("SEC_USER_AGENT")
            or DEFAULT_USER_AGENT
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_time: float = 0.0

        if cache_dir is None:
            cache_dir = Path(".sec_cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": None,  # requests will populate appropriately
            }
        )

    @staticmethod
    def _get_streamlit_secret(key: str) -> str | None:
        try:
            import streamlit as st

            if hasattr(st, "secrets") and key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
        return None

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            sleep_time = MIN_REQUEST_INTERVAL_SECONDS - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _get_cache_path(self, url: str) -> Path:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        cache_ttl_seconds: int = 86400,  # 24 hours
    ) -> Any | None:
        """Fetch JSON data from SEC EDGAR API with rate limiting and caching."""
        cache_file = self._get_cache_path(url + str(sorted(params.items()) if params else ""))
        if use_cache and cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                if (time.time() - mtime) < cache_ttl_seconds:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading cache for {url}: {e}")

        # Fetch from network with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                # Ensure User-Agent is explicitly attached
                headers = {"User-Agent": self.user_agent}
                resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)

                if resp.status_code == 200:
                    data = resp.json()
                    if use_cache:
                        try:
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(data, f)
                        except Exception as ce:
                            logger.warning(f"Failed to write cache for {url}: {ce}")
                    return data
                elif resp.status_code == 429:
                    wait = 1.5 * attempt
                    logger.warning(f"SEC rate limit hit (429) for {url}. Waiting {wait:.1f}s...")
                    time.sleep(wait)
                elif resp.status_code == 404:
                    logger.info(f"SEC resource not found (404): {url}")
                    return None
                else:
                    logger.warning(f"SEC returned HTTP {resp.status_code} for {url} (attempt {attempt})")
                    time.sleep(0.5 * attempt)
            except Exception as ex:
                logger.warning(f"SEC request error for {url} (attempt {attempt}): {ex}")
                time.sleep(0.5 * attempt)

        logger.error(f"Failed to fetch JSON from {url} after {self.max_retries} attempts.")
        return None

    def get_text(
        self,
        url: str,
        use_cache: bool = True,
        cache_ttl_seconds: int = 86400 * 7,  # 7 days for document text
    ) -> str | None:
        """Fetch raw document text/HTML from SEC EDGAR with rate limiting and caching."""
        cache_file = self._get_cache_path(url)
        if use_cache and cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                if (time.time() - mtime) < cache_ttl_seconds:
                    with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
                        return f.read()
            except Exception as e:
                logger.warning(f"Error reading cache for {url}: {e}")

        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                headers = {"User-Agent": self.user_agent}
                resp = self.session.get(url, headers=headers, timeout=self.timeout)

                if resp.status_code == 200:
                    text = resp.text
                    if use_cache:
                        try:
                            with open(cache_file, "w", encoding="utf-8", errors="replace") as f:
                                f.write(text)
                        except Exception as ce:
                            logger.warning(f"Failed to write cache for {url}: {ce}")
                    return text
                elif resp.status_code == 429:
                    time.sleep(1.5 * attempt)
                elif resp.status_code == 404:
                    return None
                else:
                    time.sleep(0.5 * attempt)
            except Exception as ex:
                logger.warning(f"SEC request error for {url} (attempt {attempt}): {ex}")
                time.sleep(0.5 * attempt)

        return None


# Global singleton instance
sec_client = SECClient()
