import os
import time

import jwt
from fastapi.testclient import TestClient

from authorizer.main import app

client = TestClient(app)


def test_login_success():
    r = client.post("/login", json={"username": "user1", "password": "pass1"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_failure():
    r = client.post("/login", json={"username": "user1", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user():
    r = client.post("/login", json={"username": "nouser", "password": "whatever"})
    assert r.status_code == 401


def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_validate_token():
    r = client.post("/login", json={"username": "user1", "password": "pass1"})
    token = r.json()["access_token"]
    vr = client.post("/validate", json={"token": token})
    body = vr.json()
    assert body["valid"] is True
    assert body["claims"]["sub"] == "u1"


def test_validate_bad_token():
    now = int(time.time())
    bad = jwt.encode({"sub": "u1", "exp": now - 10}, "wrong", algorithm="HS256")
    r = client.post("/validate", json={"token": bad})
    assert r.status_code == 200
    assert r.json() == {"valid": False}


def test_validate_future_iat():
    future = int(time.time()) + 1000
    tok = jwt.encode(
        {"sub": "u1", "iat": future, "exp": future + 3600},
        os.getenv("JWT_SECRET", "devsecret"),
        algorithm="HS256",
    )
    r = client.post("/validate", json={"token": tok})
    assert r.status_code == 200
    assert r.json() == {"valid": False}
