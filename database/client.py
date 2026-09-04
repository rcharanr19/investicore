from __future__ import annotations

import os

from dotenv import load_dotenv

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - optional dependency fallback
    Client = object  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def ensure_database() -> None:
    """No-op when credentials are absent; local V1 runs in in-memory mode."""
    return None
