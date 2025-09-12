import os
import time

import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"

app = FastAPI()


class Credentials(BaseModel):
    username: str
    password: str


users = {
    "user1": {"id": "u1", "password": "pass1", "roles": ["customer"]},
    "user2": {"id": "u2", "password": "pass2", "roles": ["customer"]},
}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/login")
def login(creds: Credentials):
    u = users.get(creds.username)
    if not u or u["password"] != creds.password:
        raise HTTPException(status_code=401, detail="invalid credentials")
    payload = {
        "sub": u["id"],
        "roles": u["roles"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGO)
    return {"access_token": token, "token_type": "bearer"}


class TokenIn(BaseModel):
    token: str


@app.post("/validate")
def validate(data: TokenIn):
    try:
        decoded = jwt.decode(
            data.token,
            SECRET,
            algorithms=[ALGO],
            options={"require": ["exp", "iat"], "verify_iat": True},
        )
        return {"valid": True, "claims": decoded}
    except jwt.PyJWTError:
        return {"valid": False}
