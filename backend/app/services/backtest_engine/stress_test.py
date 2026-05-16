"""压力测试引擎 — 6段A股历史危机回放"""
from datetime import date
from typing import List, Any
from dataclasses import dataclass
from app.services.backtest_engine.engine import BacktestEngine
from app.services.data_provider.adapter import get_provider

CRISIS_SCENARIOS = {
    "2015_股灾": {"start": date(2015,6,15), "end": date(2015,7,8), "description": "上证5178暴跌至3500，跌幅32%", "index_drop_pct": -32.0},
    "2016_熔断": {"start": date(2016,1,4), "end": date(2016,1,28), "description": "熔断机制引发恐慌", "index_drop_pct": -25.0},
    "2018_熊市": {"start": date(2018,1,29), "end": date(2018,12,28), "description": "中美贸易战+去杠杆", "index_drop_pct": -25.0},
    "2020_疫情": {"start": date(2020,1,20), "end": date(2020,3,23), "description": "COVID-19全球扩散", "index_drop_pct": -14.5},
    "2022_封控": {"start": date(2022,1,4), "end": date(2022,10,31), "description": "封控+地产危机", "index_drop_pct": -15.0},
    "2024_微盘": {"start": date(2024,1,2), "end": date(2024,2,5), "description": "微盘股流动性枯竭", "index_drop_pct": -30.0},
}

@dataclass
class StressTestResult:
    scenario_name: str; description: str; index_drop_pct: float
    strategy_return_pct: float; max_drawdown_pct: float; win_rate_pct: float
    sharpe: float; survived: bool; insight: str

class StressTestEngine:
    def __init__(self): self.engine = BacktestEngine()
    async def run(self, strategy_def, symbol="600519"):
        provider = get_provider()
        results = []
        for name, sc in CRISIS_SCENARIOS.items():
            try:
                data = await provider.get_daily_k(symbol=symbol, start=sc["start"], end=sc["end"], adjust="qfq")
                if data.empty or len(data) < 10: continue
                bt = self.engine.run(data=data, strategy_def=strategy_def)
                survived = bt.max_drawdown < 0.15
                ret = bt.total_return * 100
                if ret > 0 and survived: insight = f"逆势盈利{ret:.1f}%，具备熊市防御能力"
                elif survived: insight = f"回撤可控（{bt.max_drawdown*100:.1f}%）"
                else: insight = f"回撤{bt.max_drawdown*100:.1f}%，超过警戒线"
                results.append(StressTestResult(scenario_name=name, description=sc["description"], index_drop_pct=sc["index_drop_pct"], strategy_return_pct=round(ret,1), max_drawdown_pct=round(bt.max_drawdown*100,1), win_rate_pct=round(bt.win_rate*100,1), sharpe=round(bt.sharpe_ratio,2), survived=survived, insight=insight))
            except: pass
        return results
    def aggregate(self, results):
        sv = sum(1 for r in results if r.survived)
        t = max(len(results), 1)
        sr = sv / t
        g = "A" if sr>=0.8 and sum(r.strategy_return_pct for r in results)/t>=0 else "B" if sr>=0.6 else "C" if sr>=0.4 else "D"
        return {"total_scenarios":len(results),"survived":sv,"survival_rate":round(sr*100,1),"avg_return_pct":round(sum(r.strategy_return_pct for r in results)/t,1),"avg_max_drawdown_pct":round(sum(r.max_drawdown_pct for r in results)/t,1),"grade":g}
