from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.sec.client import SECClient


def test_sec_client_initialization_and_user_agent():
    client = SECClient(user_agent="TestAgent test@investicore.org")
    assert client.user_agent == "TestAgent test@investicore.org"
    assert "User-Agent" in client.session.headers
    assert client.session.headers["User-Agent"] == "TestAgent test@investicore.org"


def test_sec_client_caching(tmp_path):
    client = SECClient(user_agent="TestAgent test@investicore.org", cache_dir=tmp_path)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "test_id": 42}

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        # First call hits network
        res1 = client.get_json("https://data.sec.gov/test.json", use_cache=True)
        assert res1 == {"status": "ok", "test_id": 42}
        assert mock_get.call_count == 1

        # Second call uses disk cache
        res2 = client.get_json("https://data.sec.gov/test.json", use_cache=True)
        assert res2 == {"status": "ok", "test_id": 42}
        assert mock_get.call_count == 1  # Network was NOT hit again


def test_sec_client_rate_limiting():
    client = SECClient(user_agent="TestAgent test@investicore.org")
    client._last_request_time = 0.0
    client._rate_limit()
    assert client._last_request_time > 0.0


def test_sec_client_handles_404(tmp_path):
    client = SECClient(cache_dir=tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch.object(client.session, "get", return_value=mock_resp):
        res = client.get_json("https://data.sec.gov/not_found.json")
        assert res is None
