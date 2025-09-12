import os
import time

import httpx
import jwt
from fastapi import BackgroundTasks, FastAPI, Header
from fastapi.responses import JSONResponse

SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"
ALERT_URL = os.getenv("ALERT_URL", "http://alert:8002/alert")

app = FastAPI()


async def send_alert_async(payload: dict):
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            await client.post(ALERT_URL, json=payload)
        except Exception:
            # En entorno real, registrar el error; en experimento no bloqueamos la respuesta
            pass


@app.get("/orders/{customer_id}/status")
async def order_status(
    customer_id: str,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    t0 = time.time()

    # 1) Sin token o mal formado
    if not authorization or not authorization.lower().startswith("bearer "):
        background_tasks.add_task(
            send_alert_async,
            {
                "reason": "no_token",
                "customer_id": customer_id,
                "subject": None,
                "t0": t0,
            },
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "missing or invalid token"},
            background=background_tasks,
        )

    # 2) Token inválido
    token = authorization.split(" ", 1)[1]
    try:
        decoded = jwt.decode(
            token,
            SECRET,
            algorithms=[ALGO],
            options={"require": ["exp", "iat"], "verify_iat": True},
        )
    except jwt.PyJWTError:
        background_tasks.add_task(
            send_alert_async,
            {
                "reason": "bad_token",
                "customer_id": customer_id,
                "subject": None,
                "t0": t0,
            },
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "invalid token"},
            background=background_tasks,
        )

    # 3) Token válido pero sujeto ≠ dueño del dato
    sub = decoded.get("sub")
    if sub != customer_id:
        background_tasks.add_task(
            send_alert_async,
            {
                "reason": "unauthorized_access",
                "customer_id": customer_id,
                "subject": sub,
                "t0": t0,
            },
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "forbidden"},
            background=background_tasks,
        )

    # 4) Autorizado
    return {"customer_id": customer_id, "status": "delivered"}


@app.get("/health")
def health():
    return {"ok": True}
