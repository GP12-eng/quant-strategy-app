"""
因子分析引擎 — IC 分析 + 分层回测
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from dataclasses import dataclass
from factors import FACTOR_REGISTRY

@dataclass
class FactorICResult:
    factor_name: str
    ic_mean: float
    ic_std: float
    ic_ir: float
    ic_positive_ratio: float
    top_return: float
    bottom_return: float
    spread: float
    monotonic: bool
    decay_days: int
    grade: str

class FactorAnalyzer:
    def analyze_single(self, data: pd.DataFrame, factor_name: str, params: Dict[str, Any] = None, forward_periods: List[int] = None) -> FactorICResult:
        if factor_name not in FACTOR_REGISTRY: raise ValueError(f"未知因子: {factor_name}")
        if forward_periods is None: forward_periods = [1, 5, 10, 20]
        factor_obj = FACTOR_REGISTRY[factor_name]()
        if params is None: params = factor_obj.random_params()
        factor_values = factor_obj.compute(data, params)
        close = data["close"]
        ic_list = []
        for period in forward_periods:
            forward_ret = close.pct_change(period).shift(-period)
            valid = factor_values.notna() & forward_ret.notna()
            if valid.sum() < 30: continue
            ic = factor_values[valid].rank().corr(forward_ret[valid].rank())
            ic_list.append(ic)
        ic_mean = np.mean(ic_list) if ic_list else 0
        ic_std = np.std(ic_list) if ic_list else 1
        ic_ir = ic_mean / max(ic_std, 1e-10)
        ic_positive_ratio = sum(1 for x in ic_list if x > 0) / max(len(ic_list), 1)
        forward_ret_5 = close.pct_change(5).shift(-5)
        valid_mask = factor_values.notna() & forward_ret_5.notna()
        top_return = bottom_return = spread = 0.0
        monotonic = False
        if valid_mask.sum() >= 50:
            fv_valid = factor_values[valid_mask]
            labels = pd.qcut(fv_valid, q=5, labels=[1,2,3,4,5], duplicates='drop')
            group_returns = forward_ret_5[valid_mask].groupby(labels).mean()
            top_return = group_returns.iloc[-1] if len(group_returns) > 0 else 0
            bottom_return = group_returns.iloc[0] if len(group_returns) > 0 else 0
            spread = top_return - bottom_return
            monotonic = all(group_returns.iloc[i] <= group_returns.iloc[i+1] for i in range(len(group_returns)-1)) if len(group_returns) >= 3 else False
        decay_days = 20
        for p in [1,3,5,10,15,20,30]:
            fr = close.pct_change(p).shift(-p)
            valid = factor_values.notna() & fr.notna()
            if valid.sum() < 30: break
            ic = factor_values[valid].rank().corr(fr[valid].rank())
            if abs(ic) < 0.02: decay_days = p; break
            decay_days = p
        grade = self._grade_ic(ic_mean, ic_ir, monotonic, spread)
        return FactorICResult(factor_name=factor_name, ic_mean=round(ic_mean,4), ic_std=round(ic_std,4), ic_ir=round(ic_ir,2), ic_positive_ratio=round(ic_positive_ratio,2), top_return=round(top_return*100,2), bottom_return=round(bottom_return*100,2), spread=round(spread*100,2), monotonic=monotonic, decay_days=decay_days, grade=grade)
    
    def analyze_all(self, data: pd.DataFrame) -> List[FactorICResult]:
        results = []
        for fname in FACTOR_REGISTRY:
            try: results.append(self.analyze_single(data, fname))
            except Exception: pass
        return sorted(results, key=lambda r: abs(r.ic_ir), reverse=True)
    
    def correlation_matrix(self, data: pd.DataFrame) -> pd.DataFrame:
        factor_values = {}
        for fname in FACTOR_REGISTRY:
            try:
                factor_obj = FACTOR_REGISTRY[fname]()
                params = factor_obj.random_params()
                factor_values[fname] = factor_obj.compute(data, params)
            except Exception: pass
        if len(factor_values) < 2: return pd.DataFrame()
        return pd.DataFrame(factor_values).corr(method='spearman')
    
    def _grade_ic(self, ic_mean, ic_ir, monotonic, spread):
        score = 0
        if abs(ic_mean) > 0.05: score += 3
        elif abs(ic_mean) > 0.03: score += 2
        elif abs(ic_mean) > 0.01: score += 1
        if ic_ir > 1.0: score += 3
        elif ic_ir > 0.5: score += 2
        elif ic_ir > 0.3: score += 1
        if monotonic: score += 2
        if abs(spread) > 3: score += 2
        elif abs(spread) > 1: score += 1
        if score >= 8: return "A"
        elif score >= 6: return "B"
        elif score >= 4: return "C"
        return "D"
