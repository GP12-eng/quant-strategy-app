"""
量化股票 App — 核心配置
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "量化策略 App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./quant_app.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATA_PROVIDER: str = "akshare"
    TUSHARE_TOKEN: Optional[str] = None
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    DAILY_STRATEGY_COUNT: int = 10
    STRATEGY_GENERATION_TIME: str = "02:00"
    MAX_SINGLE_STOCK_PCT: float = 0.10
    MAX_INDUSTRY_PCT: float = 0.25
    MAX_TOTAL_POSITION_PCT: float = 0.80
    DRAWDOWN_MELTDOWN_PCT: float = 0.03
    CONSECUTIVE_LOSS_LIMIT: int = 5
    STAMP_TAX: float = 0.001
    COMMISSION: float = 0.00025
    MIN_COMMISSION: float = 5.0
    SLIPPAGE: float = 0.001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
