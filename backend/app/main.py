"""FastAPI 主应用 — 含速率限制 + 安全头 + 行情广播"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time, asyncio
from app.core.config import settings
from app.core.database import init_db

# 简易速率限制
_rate_limits: dict[str, list] = {}

def rate_limit(request: Request, max_req: int = 60, window: int = 60):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    if client not in _rate_limits: _rate_limits[client] = []
    _rate_limits[client] = [t for t in _rate_limits[client] if now - t < window]
    if len(_rate_limits[client]) >= max_req: return False
    _rate_limits[client].append(now)
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        print(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION}")
        from app.api.v1.strategies import _restore_from_db
        await _restore_from_db()
        import asyncio as _asyncio
        from app.api.v1.market import market_broadcast_loop
        _broadcast_task = _asyncio.create_task(market_broadcast_loop())
        print(f"[OK] 行情广播已启动")
    except Exception as e: print(f"[WARN] {e}")
    print(f"[OK] http://localhost:8000/docs")
    yield
    print("[OK] 应用关闭")

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# 安全头中间件
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# 速率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if not rate_limit(request):
        return JSONResponse(status_code=429, content={"error": "请求过于频繁，请稍后"})
    return await call_next(request)

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root(): return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}
@app.get("/health")
async def health(): return {"status": "healthy", "timestamp": time.strftime("%H:%M:%S")}

from app.api.v1 import strategies, backtest, market, explain, coin, summary, health, versioning
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["策略"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["回测"])
app.include_router(market.router, prefix="/api/v1/market", tags=["市场"])
app.include_router(explain.router, prefix="/api/v1/explain", tags=["白话"])
app.include_router(coin.router, prefix="/api/v1/coin", tags=["虚拟币"])
app.include_router(summary.router, prefix="/api/v1/summary", tags=["总结"])
app.include_router(health.router, prefix="/api/v1/health", tags=["系统"])
app.include_router(versioning.router, prefix="/api/v1/versioning", tags=["版本"])
