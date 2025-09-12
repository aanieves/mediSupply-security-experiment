import time

from fastapi.testclient import TestClient

from alert_sink.main import app, latencies

client = TestClient(app)


def test_metrics_empty():
    latencies.clear()
    r = client.get("/metrics")
    assert r.status_code == 200
    m = r.json()
    assert m["count"] == 0
    assert m["p50_ms"] is None
    assert m["p95_ms"] is None


def test_alert_and_metrics(monkeypatch):
    latencies.clear()
    latencies_before = client.get("/metrics").json()["count"]
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    payload = {"reason": "no_token", "customer_id": "u1", "subject": None, "t0": 999.0}
    r = client.post("/alert", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["received"] is True
    assert data["count"] == latencies_before + 1
    assert data["count"] == 1
    metrics = client.get("/metrics").json()
    assert metrics["count"] == latencies_before + 1
    assert metrics["count"] == 1
    assert metrics["max_ms"] >= 0
    assert metrics["max_ms"] >= 1000.0 - 999.0


def test_metrics_percentiles():
    latencies.clear()
    # Carga latencias predefinidas
    latencies.extend([1000, 2000, 3000, 4000, 5000])
    metrics = client.get("/metrics").json()
    assert metrics["count"] == 5
    assert metrics["p50_ms"] == 3000
    assert metrics["p95_ms"] == 4000
    assert metrics["max_ms"] == 5000
