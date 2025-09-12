import time
from typing import List

from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()
latencies: List[float] = []


class Alert(BaseModel):
    reason: str
    customer_id: str
    subject: str | None = None
    t0: float


@app.post("/alert")
async def alert(a: Alert, request: Request):
    t1 = time.time()
    dt = (t1 - a.t0) * 1000.0
    latencies.append(dt)
    return {"received": True, "latency_ms": dt, "count": len(latencies)}


@app.get("/metrics")
def metrics():
    if not latencies:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    s = sorted(latencies)
    n = len(s)
    p50 = s[int(0.5 * (n - 1))]
    p95 = s[int(0.95 * (n - 1))]
    return {"count": n, "p50_ms": p50, "p95_ms": p95, "max_ms": max(s)}
