import asyncio
import os
import time

import httpx
import jwt
from fastapi.testclient import TestClient

from security_audit import main as secmod

client = TestClient(secmod.app)


def _token(sub: str, iat: int | None = None):
    now = int(time.time()) if iat is None else iat
    return jwt.encode(
        {
            "sub": sub,
            "roles": ["customer"],
            "iat": now,
            "exp": now + 3600,
        },
        os.getenv("JWT_SECRET", "devsecret"),
        algorithm="HS256",
    )


def test_status_authorized_ok(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    tok = _token("u1")
    r = client.get("/orders/u1/status", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["customer_id"] == "u1"
    assert calls == []


def test_status_no_token_alert(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    r = client.get("/orders/u1/status")
    assert r.status_code == 401
    assert calls and calls[-1]["reason"] == "no_token"
    assert "subject" in calls[-1] and calls[-1]["subject"] is None


def test_status_wrong_subject_alert(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    tok = _token("u2")
    r = client.get("/orders/u1/status", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert calls and calls[-1]["reason"] == "unauthorized_access"
    assert calls[-1]["subject"] == "u2"


def test_status_bad_token_alert(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    r = client.get(
        "/orders/u1/status",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401
    assert calls and calls[-1]["reason"] == "bad_token"
    assert "subject" in calls[-1] and calls[-1]["subject"] is None


def test_status_expired_token_alert(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    now = int(time.time())
    expired = jwt.encode(
        {"sub": "u1", "roles": ["customer"], "iat": now - 7200, "exp": now - 3600},
        os.getenv("JWT_SECRET", "devsecret"),
        algorithm="HS256",
    )
    r = client.get(
        "/orders/u1/status",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 401
    assert calls and calls[-1]["reason"] == "bad_token"


def test_status_future_iat(monkeypatch):
    calls = []

    async def fake_alert(payload: dict):
        calls.append(payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)
    future = int(time.time()) + 1000
    tok = _token("u1", iat=future)
    r = client.get("/orders/u1/status", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
    assert calls and calls[-1]["reason"] == "bad_token"


def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_send_alert_async(monkeypatch):
    calls = []

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, url, json):
            calls.append((url, json))

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=2.0: DummyClient())
    asyncio.run(secmod.send_alert_async({"reason": "x"}))
    assert calls and calls[0][0] == secmod.ALERT_URL

    class ErrorClient(DummyClient):
        async def post(self, url, json):
            raise RuntimeError("fail")

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=2.0: ErrorClient())
    asyncio.run(secmod.send_alert_async({"reason": "y"}))
