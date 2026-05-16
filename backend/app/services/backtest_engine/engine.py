"""回测引擎 v5 — 动态阈值 + 直接加权求和"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import backtrader as bt
from app.core.config import settings
from factors import FACTOR_REGISTRY

@dataclass
class BacktestResult:
    total_return: float; annual_return: float; max_drawdown: float
    sharpe_ratio: float; win_rate: float; avg_win_loss_ratio: float
    trade_count: int; composite_score: float
    equity_curve: List[float] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)
    benchmark_return: Optional[float] = None; alpha: Optional[float] = None; beta: Optional[float] = None
    start_date: str = ""; end_date: str = ""
    initial_capital: float = 100000.0; final_capital: float = 0.0
    passed: bool = True; diagnostic: str = ""
    capacity_wan: float = 0; attribution: str = ""

class CostModel(bt.CommInfoBase):
    params = (("stamp_tax", settings.STAMP_TAX), ("commission", settings.COMMISSION), ("min_commission", settings.MIN_COMMISSION), ("slippage", settings.SLIPPAGE), ("transfer_fee", 0.00001))
    def _getcommission(self, size, price, pseudoexec):
        v = abs(size) * price
        return max(v * self.p.commission, self.p.min_commission) + (v * self.p.stamp_tax if size < 0 else 0.0) + v * self.p.transfer_fee

STYLE_STOP_MAP = {"short_term": 0.03, "mid_term": 0.07, "low_vol": 0.05, "value": 0.10}

def precompute_factors(data, strategy_def):
    scores = {}
    for f in strategy_def.factors:
        if f.factor_name not in FACTOR_REGISTRY: continue
        try:
            raw = FACTOR_REGISTRY[f.factor_name]().compute(data, f.params)
            scores[f.factor_name] = raw.fillna(0.0).values.astype(np.float64) * f.weight
        except: scores[f.factor_name] = np.zeros(len(data))
    return scores

class StrategyAdapter(bt.Strategy):
    params = (("strategy_def", None), ("factor_scores", None))
    def __init__(self):
        self.strategy_def = self.p.strategy_def; self.factor_scores = self.p.factor_scores or {}
        self.bought_today = set(); self.order = None
        self.stop_loss_pct = STYLE_STOP_MAP.get(self.strategy_def.style if self.strategy_def else "mid_term", 0.05)
        self.entry_price = 0.0; self.signal_count = 0
    def _get_score(self, fname, idx):
        arr = self.factor_scores.get(fname)
        if arr is None or idx >= len(arr): return 0.0
        v = float(arr[idx]); return 0.0 if np.isnan(v) or np.isinf(v) else v
    def _check_price_limit(self, buy):
        if len(self.data) < 2: return True
        c, p = self.data.close[0], self.data.close[-1]
        if p <= 0: return True
        pct = (c - p) / p
        return not (buy and pct >= 0.098) and not (not buy and pct <= -0.098)
    def next(self):
        self.bought_today.clear()
        if self.order or self.strategy_def is None: return
        idx = len(self.data) - 1
        total_score = sum(self._get_score(f, idx) for f in self.factor_scores)
        cv, cash = self.broker.getvalue(), self.broker.getcash()
        pct = (cv - cash) / max(cv, 1)
        mp = self.strategy_def.position_rules.get("max_total_position_pct", 0.8)
        sp = self.strategy_def.position_rules.get("single_stock_pct", 0.1)
        if self.position.size > 0 and self.entry_price > 0:
            if (self.data.close[0] - self.entry_price) / self.entry_price < -self.stop_loss_pct:
                self.order = self.sell(size=self.position.size); self.signal_count += 1; return
        sellable = max(0, self.position.size - sum(self.bought_today))
        dyn_threshold = 0.01 * (4 / max(len(self.factor_scores), 1))
        if total_score > dyn_threshold and pct < mp and self._check_price_limit(True):
            size = int(cash * sp / max(self.data.close[0], 0.01) / 100) * 100
            if size >= 100: self.order = self.buy(size=size); self.bought_today.add(size); self.entry_price = self.data.close[0]; self.signal_count += 1
        elif total_score < -dyn_threshold and sellable >= 100 and self._check_price_limit(False):
            self.order = self.sell(size=sellable); self.signal_count += 1

class EquityObserver(bt.Observer):
    lines = ('equity',)
    def next(self): self.lines.equity[0] = self._owner.broker.getvalue()

class BacktestEngine:
    def run(self, data, strategy_def, initial_capital=100000, benchmark_data=None):
        fs = precompute_factors(data, strategy_def)
        nz = sum(1 for a in fs.values() if np.abs(a).max() > 1e-10)
        cerebro = bt.Cerebro()
        cerebro.addstrategy(StrategyAdapter, strategy_def=strategy_def, factor_scores=fs)
        cerebro.adddata(bt.feeds.PandasData(dataname=data))
        cerebro.broker.setcash(initial_capital)
        cerebro.broker.addcommissioninfo(CostModel())
        cerebro.broker.set_slippage_perc(settings.SLIPPAGE)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.025)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addobserver(EquityObserver)
        sv = cerebro.broker.getvalue(); results = cerebro.run(); strat = results[0]; ev = cerebro.broker.getvalue()
        eq = []
        for o in strat.getobservers():
            if isinstance(o, EquityObserver):
                pv = initial_capital
                for i in range(len(o.lines.equity)):
                    v = float(o.lines.equity[i]) if o.lines.equity[i] != 0 else pv
                    eq.append(round(v,2)); pv = v
                break
        tr = (ev - sv) / max(sv, 1); days = max(len(data), 1)
        ar = (1 + tr) ** (252 / days) - 1 if tr > -1 else -1.0
        dd = strat.analyzers.drawdown.get_analysis()
        md = dd.get("max", {}).get("drawdown", 0) / 100 if dd.get("max") else 0
        sh = strat.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0.0
        ta = strat.analyzers.trades.get_analysis()
        tt = ta.get("total", {}).get("total", 0); w = ta.get("won", {}).get("total", 0) / max(tt, 1)
        aw = ta.get("won", {}).get("pnl", {}).get("average", 0) or 0
        al = abs(ta.get("lost", {}).get("pnl", {}).get("average", 1) or 1)
        sc = max(0, min(100, 50 + min(ar*100,25) - max(0,(md-0.05))*200 + min(sh*10,15) + (w-0.4)*50))
        diag = f"因子:{nz}/{len(fs)}活跃|信号:{strat.signal_count}次|交易:{tt}笔|阈值:{0.01*(4/max(len(fs),1)):.4f}"
        avg_amt = float(data["amount"].mean()) if "amount" in data.columns else 1e8
        cap = avg_amt * 0.01 / max(tt/max(days,1)*252, 0.1) / 10000
        alpha = beta = None
        if benchmark_data is not None:
            try:
                sr2 = data["close"].pct_change().dropna(); br2 = benchmark_data["close"].pct_change().dropna()
                idx2 = sr2.index.intersection(br2.index)
                if len(idx2) >= 30:
                    cov = np.cov(sr2[idx2].values, br2[idx2].values)
                    if cov.shape == (2,2) and cov[1,1] != 0:
                        beta = cov[0,1]/cov[1,1]; alpha = (np.mean(sr2[idx2].values)-beta*np.mean(br2[idx2].values))*252
            except: pass
        attr = f"Beta贡献:{beta*0.06*100:.1f}%|Alpha:{alpha*100 if alpha else ar*100:.1f}%" if beta and alpha is not None else f"年化{ar*100:.1f}%"
        return BacktestResult(total_return=round(tr,4), annual_return=round(ar,4), max_drawdown=round(md,4), sharpe_ratio=round(sh,4), win_rate=round(w,4), avg_win_loss_ratio=round(aw/max(al,1),4), trade_count=tt, composite_score=round(sc,1), equity_curve=eq, initial_capital=initial_capital, final_capital=ev, passed=md<=0.15, diagnostic=diag, capacity_wan=round(cap,1), attribution=attr, alpha=round(alpha,4) if alpha else None, beta=round(beta,2) if beta else None)
