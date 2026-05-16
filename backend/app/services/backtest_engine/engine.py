"""回测引擎 v4 — 修复零交易 + 因子归一化bug + 诊断信息"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import backtrader as bt
from app.core.config import settings
from factors import FACTOR_REGISTRY

@dataclass
class BacktestResult:
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    avg_win_loss_ratio: float
    trade_count: int
    composite_score: float
    equity_curve: List[float] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)
    benchmark_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100000.0
    final_capital: float = 0.0
    passed: bool = True
    diagnostic: str = ""

class CostModel(bt.CommInfoBase):
    params = (("stamp_tax", settings.STAMP_TAX), ("commission", settings.COMMISSION), ("min_commission", settings.MIN_COMMISSION), ("slippage", settings.SLIPPAGE), ("transfer_fee", 0.00002))
    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        return max(value * self.p.commission, self.p.min_commission) + (value * self.p.stamp_tax if size < 0 else 0.0) + value * self.p.transfer_fee

STYLE_STOP_MAP = {"short_term": 0.03, "mid_term": 0.07, "low_vol": 0.05, "value": 0.10}
SIGNAL_THRESHOLD = 0.05

def precompute_factors(data, strategy_def):
    scores = {}
    for f in strategy_def.factors:
        if f.factor_name not in FACTOR_REGISTRY: continue
        try:
            raw = FACTOR_REGISTRY[f.factor_name]().compute(data, f.params)
            scores[f.factor_name] = raw.fillna(0.0).values.astype(np.float64) * f.weight
        except Exception:
            scores[f.factor_name] = np.zeros(len(data))
    return scores

class StrategyAdapter(bt.Strategy):
    params = (("strategy_def", None), ("factor_scores", None))
    def __init__(self):
        self.strategy_def = self.p.strategy_def
        self.factor_scores = self.p.factor_scores or {}
        self.bought_today = set()
        self.order = None
        self.stop_loss_pct = STYLE_STOP_MAP.get(self.strategy_def.style if self.strategy_def else "mid_term", 0.05)
        self.entry_price = 0.0
        self.signal_count = 0
    def _get_score(self, fname, idx):
        arr = self.factor_scores.get(fname)
        if arr is None or idx >= len(arr): return 0.0
        val = float(arr[idx])
        return 0.0 if np.isnan(val) or np.isinf(val) else val
    def _normalize(self, scores):
        if not scores: return scores
        vals = list(scores.values())
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return {k: 0.5 if v > 0 else (-0.5 if v < 0 else 0.0) for k, v in scores.items()}
        return {k: 2 * (v - mn) / (mx - mn) - 1 for k, v in scores.items()}
    def _check_price_limit(self, buy):
        if len(self.data) < 2: return True
        close, pre = self.data.close[0], self.data.close[-1]
        if pre <= 0: return True
        pct = (close - pre) / pre
        return not (buy and pct >= 0.098) and not (not buy and pct <= -0.098)
    def next(self):
        if self.order or self.strategy_def is None: return
        idx = len(self.data) - 1
        raw_scores = {f: self._get_score(f, idx) for f in self.factor_scores}
        if not raw_scores: return
        total_score = sum(self._normalize(raw_scores).values())
        cv, cash = self.broker.getvalue(), self.broker.getcash()
        pct = (cv - cash) / max(cv, 1)
        mp = self.strategy_def.position_rules.get("max_total_position_pct", 0.8)
        sp = self.strategy_def.position_rules.get("single_stock_pct", 0.1)
        if self.position.size > 0 and self.entry_price > 0:
            if (self.data.close[0] - self.entry_price) / self.entry_price < -self.stop_loss_pct:
                self.order = self.sell(size=self.position.size); self.signal_count += 1; return
        sellable = max(0, self.position.size - sum(self.bought_today))
        if total_score > SIGNAL_THRESHOLD and pct < mp and self._check_price_limit(True):
            size = int(cash * sp / max(self.data.close[0], 0.01) / 100) * 100
            if size >= 100:
                self.order = self.buy(size=size); self.bought_today.add(size); self.entry_price = self.data.close[0]; self.signal_count += 1
        elif total_score < -SIGNAL_THRESHOLD and sellable >= 100 and self._check_price_limit(False):
            self.order = self.sell(size=sellable); self.signal_count += 1
    def nextstart(self): self.bought_today.clear()

class EquityObserver(bt.Observer):
    lines = ('equity',)
    def next(self): self.lines.equity[0] = self._owner.broker.getvalue()

class BacktestEngine:
    def run(self, data, strategy_def, initial_capital=100000, benchmark_data=None):
        factor_scores = precompute_factors(data, strategy_def)
        nz = sum(1 for a in factor_scores.values() if np.abs(a).max() > 1e-10)
        cerebro = bt.Cerebro()
        cerebro.addstrategy(StrategyAdapter, strategy_def=strategy_def, factor_scores=factor_scores)
        cerebro.adddata(bt.feeds.PandasData(dataname=data))
        cerebro.broker.setcash(initial_capital)
        cerebro.broker.addcommissioninfo(CostModel())
        cerebro.broker.set_slippage_perc(settings.SLIPPAGE)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.025)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addobserver(EquityObserver)
        sv = cerebro.broker.getvalue()
        results = cerebro.run()
        strat = results[0]
        ev = cerebro.broker.getvalue()
        eq = []
        for o in strat.getobservers():
            if isinstance(o, EquityObserver):
                pv = initial_capital
                for i in range(len(o.lines.equity)):
                    v = float(o.lines.equity[i]) if o.lines.equity[i] != 0 else pv
                    eq.append(round(v, 2)); pv = v
                break
        tr = (ev - sv) / max(sv, 1)
        ar = (1 + tr) ** (252 / max(len(data), 1)) - 1 if tr > -1 else -1.0
        dd = strat.analyzers.drawdown.get_analysis()
        md = dd.get("max", {}).get("drawdown", 0) / 100 if dd.get("max") else 0
        sh = strat.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0.0
        ta = strat.analyzers.trades.get_analysis()
        tt = ta.get("total", {}).get("total", 0)
        w = ta.get("won", {}).get("total", 0) / max(tt, 1)
        aw = ta.get("won", {}).get("pnl", {}).get("average", 0) or 0
        al = abs(ta.get("lost", {}).get("pnl", {}).get("average", 1) or 1)
        sc = max(0, min(100, 50 + min(ar*100, 25) - max(0, (md-0.05))*200 + min(sh*10, 15) + (w-0.4)*50))
        return BacktestResult(total_return=round(tr,4), annual_return=round(ar,4), max_drawdown=round(md,4), sharpe_ratio=round(sh,4), win_rate=round(w,4), avg_win_loss_ratio=round(aw/max(al,1),4), trade_count=tt, composite_score=round(sc,1), equity_curve=eq, initial_capital=initial_capital, final_capital=ev, passed=md<=0.15, diagnostic=f"因子:{nz}/{len(factor_scores)}活跃|信号:{strat.signal_count}次|交易:{tt}笔")
    def walk_forward(self, data, sd, train=504, test=126, step=63):
        return [self.run(data.iloc[s+train:s+train+test], sd) for s in range(0, len(data)-train-test, step)]
