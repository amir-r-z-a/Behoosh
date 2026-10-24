"""کلاینت مشترک MCP: هدر توکن، و دو حالت مدیریت خطا."""
import importlib

import httpx
import pytest

from app.mcp import _auth, _client


@pytest.fixture
def fake_api(monkeypatch):
    calls = []

    def fake_request(method, url, json=None, params=None, headers=None, timeout=None):
        calls.append({"method": method, "url": url, "json": json, "headers": headers})
        code = 404 if url.endswith("/missing") else 200
        return httpx.Response(code, json={"ok": code == 200},
                              request=httpx.Request(method, url))

    monkeypatch.setattr(_client.httpx, "request", fake_request)
    monkeypatch.setenv("BEHOOSH_API", "http://api.test/")
    _auth._token_var.set("bh_user_token")
    return calls


def test_request_sends_user_token(fake_api):
    assert _client.request("POST", "/log_mood", body={"mood": 5}) == {"ok": True}
    call = fake_api[0]
    assert call["url"] == "http://api.test/v1/log_mood"
    assert call["headers"] == {"X-API-Key": "bh_user_token"}


def test_error_modes(fake_api):
    assert _client.request("GET", "/missing")["status"] == 404
    with pytest.raises(httpx.HTTPStatusError):
        _client.request("GET", "/missing", raise_errors=True)


def test_missing_token_refused(monkeypatch):
    _auth._token_var.set(None)
    monkeypatch.delenv("MCP_ALLOW_FALLBACK", raising=False)
    with pytest.raises(PermissionError):
        _auth.current_token()


@pytest.mark.parametrize("mod", ["app.mcp.server", "app.mcp.finance_server"])
def test_mcp_servers_import(mod):
    assert importlib.import_module(mod).mcp is not None
