"""策略组合器 v2 — 动态风格 + 永不重复因子搭配"""
import random, json, hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from factors import FACTOR_REGISTRY

STYLES = {
    "short_term": {"name": "短线轮动", "hold_days_min": 1, "hold_days_max": 5, "rebalance_freq": "daily", "description": "快速进出"},
    "mid_term": {"name": "中线趋势", "hold_days_min": 5, "hold_days_max": 20, "rebalance_freq": "weekly", "description": "跟随中期趋势"},
    "low_vol": {"name": "低波动稳健", "hold_days_min": 10, "hold_days_max": 40, "rebalance_freq": "monthly", "description": "追求低回撤"},
    "value": {"name": "白马价值", "hold_days_min": 20, "hold_days_max": 60, "rebalance_freq": "monthly", "description": "精选优质股"},
}

FACTOR_STYLE_TAG = {
    "trend_ma": "趋势", "momentum": "动量", "breakout": "突破",
    "volume": "量能", "money_flow": "资金流", "pullback": "低吸",
    "volatility": "波动", "price_position": "位置", "fundamental": "价值",
}

def derive_dynamic_style(factors):
    if not factors: return "均衡型"
    sf = sorted(factors, key=lambda f: f.weight, reverse=True)
    p = FACTOR_STYLE_TAG.get(sf[0].factor_name, "")
    s = FACTOR_STYLE_TAG.get(sf[1].factor_name, "") if len(sf) > 1 else ""
    return f"{p}{s}型" if p and s and p != s else (f"{p}驱动型" if p else "多因子均衡型")

@dataclass
class FactorSelection:
    factor_name: str; params: Dict[str, Any]; weight: float

@dataclass
class StrategyDefinition:
    name: str; style: str; dynamic_style: str; core_logic: str
    factors: List[FactorSelection]; entry_conditions: List[str]
    buy_timing: str; take_profit_rules: List[Dict[str, Any]]
    stop_loss_pct: float; position_rules: Dict[str, Any]
    rebalance_rules: str; market_conditions: str; hold_days: tuple

class StrategyComposer:
    def __init__(self, seed=None):
        if seed: random.seed(seed)
        self.used_factor_combos = set()
        self.used_param_hashes = set()
    
    def compose(self):
        style_key = random.choice(list(STYLES.keys()))
        style = STYLES[style_key]
        fc = random.randint(4, 6)
        fnames = random.sample(list(FACTOR_REGISTRY.keys()), fc)
        ck = "-".join(sorted(fnames))
        retries = 0
        while ck in self.used_factor_combos and retries < 50:
            fc = random.randint(4, 6); fnames = random.sample(list(FACTOR_REGISTRY.keys()), fc)
            ck = "-".join(sorted(fnames)); retries += 1
        self.used_factor_combos.add(ck)
        rw = [random.uniform(0.3, 1.0) for _ in fnames]
        t = sum(rw); weights = [w/t for w in rw]
        factors = []; ec = []; phs = ""
        for i, fn in enumerate(fnames):
            fc_obj = FACTOR_REGISTRY[fn]; p = fc_obj().random_params()
            factors.append(FactorSelection(factor_name=fn, params=p, weight=round(weights[i], 4)))
            ec.append(f"{fc_obj.description}信号为正面")
            phs += f"{fn}:{sorted(p.values())}"
        ph = hashlib.md5(phs.encode()).hexdigest()[:8]
        r2 = 0
        while ph in self.used_param_hashes and r2 < 20:
            factors = []; phs = ""
            for i, fn in enumerate(fnames):
                fc_obj = FACTOR_REGISTRY[fn]; p = fc_obj().random_params()
                factors.append(FactorSelection(factor_name=fn, params=p, weight=round(weights[i], 4)))
                phs += f"{fn}:{sorted(p.values())}"
            ph = hashlib.md5(phs.encode()).hexdigest()[:8]; r2 += 1
        self.used_param_hashes.add(ph)
        ds = derive_dynamic_style(factors)
        tp = [{"level":1,"pct":round(random.uniform(0.03,0.08),2),"sell_ratio":round(random.uniform(0.2,0.4),1)},{"level":2,"pct":round(random.uniform(0.08,0.15),2),"sell_ratio":round(random.uniform(0.3,0.5),1)},{"level":3,"pct":round(random.uniform(0.15,0.25),2),"sell_ratio":1.0}]
        sl = round(random.uniform(0.03, 0.10), 2)
        pr = {"max_total_position_pct":round(random.uniform(0.5,0.9),1),"single_stock_pct":round(random.uniform(0.05,0.20),2),"max_stocks":random.randint(3,10)}
        sn = f"{ds}-{ck[:20]}-{random.randint(1000,9999)}"
        return StrategyDefinition(name=sn, style=style_key, dynamic_style=ds, core_logic=f"{ds}策略，基于{len(factors)}因子综合打分", factors=factors, entry_conditions=ec, buy_timing="收盘前评估", take_profit_rules=tp, stop_loss_pct=sl, position_rules=pr, rebalance_rules=f"{style['rebalance_freq']}调仓", market_conditions=f"适用于{style['name']}行情", hold_days=(style["hold_days_min"], style["hold_days_max"]))
    
    def compose_batch(self, count=10): return [self.compose() for _ in range(count)]

def strategy_to_dict(s: StrategyDefinition) -> dict: return asdict(s)
