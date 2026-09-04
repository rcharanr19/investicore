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
    url = SUPABASE_URL
    key = SUPABASE_KEY

    # Fallback to Streamlit secrets if environment variables are not set (e.g. in deployed apps)
    if not url or not key:
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                url = url or st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase_url")
                key = key or st.secrets.get("SUPABASE_KEY") or st.secrets.get("supabase_key")
        except Exception:
            pass

    if not url or not key or create_client is None:
        return None
    return create_client(url, key)



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
