from __future__ import annotations

import os

from dotenv import load_dotenv

# Ensure SSL certificate bundle is configured for httpx / requests in corporate environments
if "REQUESTS_CA_BUNDLE" in os.environ:
    ca_raw = os.environ["REQUESTS_CA_BUNDLE"]
    ca_path = os.path.expandvars(os.path.expanduser(ca_raw))
    if os.path.exists(ca_path):
        os.environ["SSL_CERT_FILE"] = ca_path
    elif "USERPROFILE" in os.environ:
        alt_path = os.path.join(os.environ["USERPROFILE"], "windows-ca-bundle.pem")
        if os.path.exists(alt_path):
            os.environ["SSL_CERT_FILE"] = alt_path
            os.environ["REQUESTS_CA_BUNDLE"] = alt_path

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


def get_db_table(table_name: str):
    client = get_supabase_client()
    if not client:
        return None
    try:
        return client.schema("investicore").table(table_name)
    except Exception:
        return client.table(table_name)


def ensure_database() -> None:
    """No-op when credentials are absent or database is managed via Supabase client."""
    return None
