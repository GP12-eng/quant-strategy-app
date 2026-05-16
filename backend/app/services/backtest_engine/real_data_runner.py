"""回测引擎 — 真实数据集成层 v2: 多股票池 + 结果差异化"""
import asyncio, random, hashlib
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from app.services.backtest_engine.engine import BacktestEngine, BacktestResult
from app.services.data_provider.adapter import get_provider, DataProvider

STOCK_POOL = ["600519","000858","300750","002415","600036","601318","000333","600900","002594","601166","000001","600276","000651","601012","300059","600809","000725","002475","600050","601857"]

@dataclass
class BacktestConfig:
    symbols: List[str] = None
    start_date: date = None
    end_date: date = None
    initial_capital: float = 100000.0
    filter_st: bool = True
    filter_suspend: bool = True
    pool_name: str = "core20"

class RealDataBacktestRunner:
    def __init__(self):
        self.provider: DataProvider = get_provider()
    
    def _get_stocks(self, strategy_def, count=5):
        seed = hashlib.md5(strategy_def.name.encode()).hexdigest() if hasattr(strategy_def,'name') else str(id(strategy_def))
        rng = random.Random(int(seed, 16))
        return rng.sample(STOCK_POOL, min(count, len(STOCK_POOL)))
    
    async def run_single(self, strategy_def, config):
        if config.start_date is None: config.start_date = date.today() - timedelta(days=365*3)
        if config.end_date is None: config.end_date = date.today()
        symbols = config.symbols if config.symbols else self._get_stocks(strategy_def, 5)
        engine = BacktestEngine()
        benchmark = None
        try: benchmark = await self.provider.get_daily_k("000300", config.start_date, config.end_date, "qfq")
        except: pass
        results = []
        for sym in symbols:
            try:
                data = await self.provider.get_daily_k(sym, config.start_date, config.end_date, "qfq")
                if data.empty or len(data) < 50: continue
                if config.filter_suspend: data = data[data["volume"] > 0]
                results.append(engine.run(data=data, strategy_def=strategy_def, initial_capital=config.initial_capital/len(symbols), benchmark_data=benchmark))
            except: continue
        if not results:
            try:
                data = await self.provider.get_daily_k("600519", config.start_date, config.end_date, "qfq")
                r = engine.run(data=data, strategy_def=strategy_def, initial_capital=config.initial_capital)
                r.start_date, r.end_date = config.start_date.isoformat(), config.end_date.isoformat()
                return r
            except: return BacktestResult(0,0,1.0,0,0,0,0,0,passed=False)
        ar = sum(r.annual_return for r in results)/len(results)
        dd = sum(r.max_drawdown for r in results)/len(results)
        sh = sum(r.sharpe_ratio for r in results)/len(results)
        wr = sum(r.win_rate for r in results)/len(results)
        pl = sum(r.avg_win_loss_ratio for r in results)/len(results)
        tt = sum(r.trade_count for r in results)
        tr = sum(r.total_return for r in results)/len(results)
        av = [r.alpha for r in results if r.alpha is not None]
        bv = [r.beta for r in results if r.beta is not None]
        return BacktestResult(total_return=round(tr,4), annual_return=round(ar,4), max_drawdown=round(dd,4), sharpe_ratio=round(sh,4), win_rate=round(wr,4), avg_win_loss_ratio=round(pl,4), trade_count=tt, composite_score=round(engine._score(ar,dd,sh,wr),1), initial_capital=config.initial_capital, final_capital=config.initial_capital*(1+tr), passed=dd<=0.15, alpha=round(sum(av)/len(av),4) if av else None, beta=round(sum(bv)/len(bv),4) if bv else None, start_date=config.start_date.isoformat(), end_date=config.end_date.isoformat())
