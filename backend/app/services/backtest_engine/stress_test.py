"""
压力测试引擎 — 历史危机回放
"""
from datetime import date
from typing import List, Any
from dataclasses import dataclass
from app.services.backtest_engine.engine import BacktestEngine
from app.services.data_provider.adapter import get_provider

CRISIS_SCENARIOS = {
    "2015_股灾1.0": {"start": date(2015,6,15), "end": date(2015,7,8), "description": "上证从5178暴跌至3500，跌幅32%", "index_drop_pct": -32.0},
    "2016_熔断": {"start": date(2016,1,4), "end": date(2016,1,28), "description": "熔断机制引发恐慌，上证暴跌25%", "index_drop_pct": -25.0},
    "2018_全年熊市": {"start": date(2018,1,29), "end": date(2018,12,28), "description": "中美贸易战+去杠杆，全年阴跌25%", "index_drop_pct": -25.0},
    "2020_疫情暴跌": {"start": date(2020,1,20), "end": date(2020,3,23), "description": "COVID-19全球扩散", "index_drop_pct": -14.5},
    "2022_全年下跌": {"start": date(2022,1,4), "end": date(2022,10,31), "description": "封控+地产危机", "index_drop_pct": -15.0},
    "2024_微盘股危机": {"start": date(2024,1,2), "end": date(2024,2,5), "description": "微盘股流动性枯竭", "index_drop_pct": -30.0},
}

@dataclass
class StressTestResult:
    scenario_name: str
    description: str
    index_drop_pct: float
    strategy_return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    sharpe: float
    survived: bool
    insight: str

class StressTestEngine:
    def __init__(self):
        self.engine = BacktestEngine()
        self.scenarios = CRISIS_SCENARIOS
    
    async def run(self, strategy_def: Any, symbol: str = "600519") -> List[StressTestResult]:
        provider = get_provider()
        results = []
        for name, scenario in self.scenarios.items():
            try:
                data = await provider.get_daily_k(symbol=symbol, start=scenario["start"], end=scenario["end"], adjust="qfq")
                if data.empty or len(data) < 10: continue
                bt = self.engine.run(data=data, strategy_def=strategy_def)
                survived = bt.max_drawdown < 0.15
                ret = bt.total_return * 100
                if ret > 0 and survived: insight = f"在{name}期间逆势盈利 {ret:.1f}%，具备熊市防御能力"
                elif survived: insight = f"在{name}期间回撤可控（{bt.max_drawdown*100:.1f}%）"
                else: insight = f"在{name}期间回撤 {bt.max_drawdown*100:.1f}%，超过警戒线"
                results.append(StressTestResult(scenario_name=name, description=scenario["description"], index_drop_pct=scenario["index_drop_pct"], strategy_return_pct=round(ret,1), max_drawdown_pct=round(bt.max_drawdown*100,1), win_rate_pct=round(bt.win_rate*100,1), sharpe=round(bt.sharpe_ratio,2), survived=survived, insight=insight))
            except Exception: pass
        return results
    
    def aggregate(self, results):
        survived = sum(1 for r in results if r.survived)
        total = max(len(results), 1)
        avg_ret = sum(r.strategy_return_pct for r in results) / total
        avg_dd = sum(r.max_drawdown_pct for r in results) / total
        survival_rate = survived / total
        if survival_rate >= 0.8 and avg_ret >= 0: grade = "A"
        elif survival_rate >= 0.6 and avg_dd < 10: grade = "B"
        elif survival_rate >= 0.4: grade = "C"
        else: grade = "D"
        return {"total_scenarios": len(results), "survived": survived, "survival_rate": round(survival_rate*100,1), "avg_return_pct": round(avg_ret,1), "avg_max_drawdown_pct": round(avg_dd,1), "grade": grade}
