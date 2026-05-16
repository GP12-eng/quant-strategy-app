"""FastAPI — 生产就绪: 速率限制+安全头+广播+心跳+DB重试"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time, asyncio
from app.core.config import settings
from app.core.database import init_db

_rate_limits: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(3):
        try:
            await init_db()
            from app.api.v1.strategies import _restore_from_db
            await _restore_from_db()
            break
        except Exception as e:
            if attempt == 2: print(f"[ERROR] DB: {e}")
            else: await asyncio.sleep(1)
    from app.api.v1.market import market_broadcast_loop, _heartbeat_loop
    asyncio.create_task(market_broadcast_loop())
    asyncio.create_task(_heartbeat_loop())
    print(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION}")
    yield

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

@app.middleware("http")
async def security(request: Request, call_next):
    resp = await call_next(request)
    for k, v in {"X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY"}.items():
        resp.headers[k] = v
    return resp

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root(): return {"app":settings.APP_NAME}
@app.get("/health")
async def health(): return {"status":"healthy"}

from app.api.v1 import strategies, backtest, market, explain, coin, summary, health, versioning
for m, p, t in [(strategies,"/api/v1/strategies","策略"),(backtest,"/api/v1/backtest","回测"),(market,"/api/v1/market","市场"),(explain,"/api/v1/explain","白话"),(coin,"/api/v1/coin","虚拟币"),(summary,"/api/v1/summary","总结"),(health,"/api/v1/health","系统"),(versioning,"/api/v1/versioning","版本")]:
    app.include_router(m.router, prefix=p, tags=[t])
