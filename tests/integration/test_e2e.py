import time
from fastapi.testclient import TestClient

from authorizer.main import app as auth_app
from security_audit import main as secmod
from alert_sink.main import app as alert_app, latencies


def test_end_to_end_experiment(monkeypatch):
    auth_client = TestClient(auth_app)
    sec_client = TestClient(secmod.app)
    alert_client = TestClient(alert_app)
    latencies.clear()

    async def fake_alert(payload: dict):
        alert_client.post("/alert", json=payload)

    monkeypatch.setattr(secmod, "send_alert_async", fake_alert)

    t1 = auth_client.post(
        "/login", json={"username": "user1", "password": "pass1"}
    ).json()["access_token"]
    r_ok = sec_client.get(
        "/orders/u1/status", headers={"Authorization": f"Bearer {t1}"}
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["customer_id"] == "u1"

    r_no = sec_client.get("/orders/u1/status")
    assert r_no.status_code == 401

    t2 = auth_client.post(
        "/login", json={"username": "user2", "password": "pass2"}
    ).json()["access_token"]
    r_forbidden = sec_client.get(
        "/orders/u1/status", headers={"Authorization": f"Bearer {t2}"}
    )
    assert r_forbidden.status_code == 403

    metrics = alert_client.get("/metrics").json()
    assert metrics["count"] == 2
    assert metrics["p95_ms"] is not None
    assert metrics["max_ms"] >= 0
