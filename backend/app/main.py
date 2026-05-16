"""FastAPI 主应用 — 含行情广播后台任务"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        print(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION}")
        print(f"[OK] 数据源: {settings.DATA_PROVIDER}")
    except Exception as e:
        print(f"[WARN] 数据库初始化跳过: {e}")
    import asyncio
    from app.api.v1.market import market_broadcast_loop
    broadcast_task = asyncio.create_task(market_broadcast_loop())
    print(f"[OK] API 文档: http://localhost:8000/docs")
    yield
    broadcast_task.cancel()
    print("[OK] 应用关闭")

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, description="量化股票策略 App", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:3000", "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

from app.api.v1 import strategies, backtest, market, explain, coin, summary
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["策略"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["回测"])
app.include_router(market.router, prefix="/api/v1/market", tags=["市场"])
app.include_router(explain.router, prefix="/api/v1/explain", tags=["白话"])
app.include_router(coin.router, prefix="/api/v1/coin", tags=["虚拟币"])
app.include_router(summary.router, prefix="/api/v1/summary", tags=["总结"])
