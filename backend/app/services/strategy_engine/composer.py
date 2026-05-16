"""
策略组合器 — 从因子池随机组合生成完整策略
"""
import random, json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from factors import FACTOR_REGISTRY

STYLES = {
    "short_term": {"name": "短线轮动", "hold_days_min": 1, "hold_days_max": 5, "rebalance_freq": "daily", "description": "快速进出，捕捉短期波动"},
    "mid_term": {"name": "中线趋势", "hold_days_min": 5, "hold_days_max": 20, "rebalance_freq": "weekly", "description": "跟随中期趋势，持股数周"},
    "low_vol": {"name": "低波动稳健", "hold_days_min": 10, "hold_days_max": 40, "rebalance_freq": "monthly", "description": "追求低回撤，稳健收益"},
    "value": {"name": "白马价值", "hold_days_min": 20, "hold_days_max": 60, "rebalance_freq": "monthly", "description": "精选优质股票，长期持有"},
}

@dataclass
class FactorSelection:
    factor_name: str
    params: Dict[str, Any]
    weight: float

@dataclass
class StrategyDefinition:
    name: str
    style: str
    core_logic: str
    factors: List[FactorSelection]
    entry_conditions: List[str]
    buy_timing: str
    take_profit_rules: List[Dict[str, Any]]
    stop_loss_pct: float
    position_rules: Dict[str, Any]
    rebalance_rules: str
    market_conditions: str
    hold_days: tuple


class StrategyComposer:
    def __init__(self, seed: Optional[int] = None):
        if seed: random.seed(seed)
        self.used_combinations = set()
    
    def compose(self) -> StrategyDefinition:
        style_key = random.choice(list(STYLES.keys()))
        style = STYLES[style_key]
        factor_count = random.randint(4, 6)
        factor_names = random.sample(list(FACTOR_REGISTRY.keys()), factor_count)
        combo_key = "-".join(sorted(factor_names))
        retries = 0
        while combo_key in self.used_combinations and retries < 20:
            factor_count = random.randint(4, 6)
            factor_names = random.sample(list(FACTOR_REGISTRY.keys()), factor_count)
            combo_key = "-".join(sorted(factor_names))
            retries += 1
        self.used_combinations.add(combo_key)
        raw_weights = [random.uniform(0.3, 1.0) for _ in factor_names]
        total = sum(raw_weights)
        weights = [w / total for w in raw_weights]
        factors = []
        entry_conditions = []
        for i, fname in enumerate(factor_names):
            factor_cls = FACTOR_REGISTRY[fname]
            params = factor_cls().random_params()
            factors.append(FactorSelection(factor_name=fname, params=params, weight=round(weights[i], 4)))
            entry_conditions.append(f"{factor_cls.description}信号为正面")
        take_profit = [
            {"level": 1, "pct": round(random.uniform(0.03, 0.08), 2), "sell_ratio": round(random.uniform(0.2, 0.4), 1)},
            {"level": 2, "pct": round(random.uniform(0.08, 0.15), 2), "sell_ratio": round(random.uniform(0.3, 0.5), 1)},
            {"level": 3, "pct": round(random.uniform(0.15, 0.25), 2), "sell_ratio": 1.0},
        ]
        stop_loss = round(random.uniform(0.03, 0.10), 2)
        position_rules = {
            "max_total_position_pct": round(random.uniform(0.5, 0.9), 1),
            "single_stock_pct": round(random.uniform(0.05, 0.20), 2),
            "max_stocks": random.randint(3, 10),
        }
        style_name = style["name"]
        factor_abbr = "-".join([f[:4].upper() for f in factor_names[:3]])
        strategy_name = f"{style_name}-{factor_abbr}-{random.randint(1000, 9999)}"
        return StrategyDefinition(
            name=strategy_name, style=style_key,
            core_logic=f"基于{len(factors)}个因子综合打分，{style['description']}",
            factors=factors, entry_conditions=entry_conditions,
            buy_timing="每日/每周收盘前评估，满足条件后次日开盘买入",
            take_profit_rules=take_profit, stop_loss_pct=stop_loss,
            position_rules=position_rules, rebalance_rules=f"{style['rebalance_freq']}调仓",
            market_conditions=f"适用于{style['name']}行情环境",
            hold_days=(style["hold_days_min"], style["hold_days_max"]),
        )
    
    def compose_batch(self, count: int = 10) -> List[StrategyDefinition]:
        return [self.compose() for _ in range(count)]


def strategy_to_dict(s: StrategyDefinition) -> dict:
    return asdict(s)
