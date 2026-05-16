"""
白话翻译引擎 — 策略规则 → 自然语言
"""
from typing import Dict, List, Any

FACTOR_PLAIN_NAMES = {
    "trend_ma": "趋势均线", "volume": "成交量", "price_position": "价格位置",
    "volatility": "波动率", "momentum": "相对强弱动量", "money_flow": "资金流向",
    "fundamental": "基本面", "breakout": "区间突破", "pullback": "回踩企稳",
}

FACTOR_EXPLANATIONS = {
    "trend_ma": "通过比较短期、中期和长期均线的排列方向来判断趋势。",
    "volume": "观察成交量的异常变化。放量可能意味着大资金进场。",
    "price_position": "看当前股价在近期高低点之间的位置。",
    "volatility": "衡量股价的波动幅度。低波动说明市场情绪稳定。",
    "momentum": "计算股价在一定周期内的涨跌力度。",
    "money_flow": "结合价格和成交量估算资金是净流入还是净流出。",
    "fundamental": "从市值、市盈率等基本面角度筛选股票。",
    "breakout": "检测价格是否突破近期的最高点或最低点。",
    "pullback": "在上涨趋势中寻找短暂回调的机会。",
}

STYLE_EXPLANATIONS = {
    "short_term": "短线轮动策略，持仓1~5天，快速进出。适合有时间盯盘的投资者。",
    "mid_term": "中线趋势策略，持仓5~20天，跟随主要趋势。适合上班族。",
    "low_vol": "低波动稳健策略，持仓10~40天，以稳为主。适合厌恶风险的投资者。",
    "value": "白马价值策略，持仓20~60天，精选优质股。适合长期投资。",
}


class PlainLanguageTranslator:
    def translate(self, strategy) -> Dict[str, str]:
        one_liner = self._generate_one_liner(strategy)
        plain_text = self._generate_plain_text(strategy)
        risk_warning = self._generate_risk_warning(strategy)
        return {"one_liner": one_liner, "plain_text": plain_text, "risk_warning": risk_warning}
    
    def _generate_one_liner(self, s):
        names = [FACTOR_PLAIN_NAMES.get(f.factor_name, f.factor_name) for f in s.factors[:3]]
        style = STYLE_EXPLANATIONS.get(s.style, "").split("，")[0]
        return f"{style}，结合{'、'.join(names)}三个维度选股"
    
    def _generate_plain_text(self, s):
        lines = []
        style_desc = STYLE_EXPLANATIONS.get(s.style, "")
        lines.append(f"📌 这是一套{style_desc}")
        lines.append("")
        lines.append(f"🔍 本策略使用了 {len(s.factors)} 个选股因子：")
        for i, factor in enumerate(s.factors, 1):
            name = FACTOR_PLAIN_NAMES.get(factor.factor_name, factor.factor_name)
            explanation = FACTOR_EXPLANATIONS.get(factor.factor_name, "")
            weight_pct = int(factor.weight * 100)
            lines.append(f"  {i}. 【{name}】（权重{weight_pct}%）— {explanation}")
        lines.append("")
        lines.append("📈 买入规则：")
        for cond in s.entry_conditions[:3]:
            lines.append(f"  • {cond}")
        lines.append(f"  触发条件后，{s.buy_timing}")
        lines.append("")
        lines.append("📉 卖出规则：")
        lines.append(f"  • 硬止损：亏损达到 {int(s.stop_loss_pct*100)}% 时无条件卖出")
        for tp in s.take_profit_rules:
            lines.append(f"  • 止盈第{tp['level']}档：盈利 {int(tp['pct']*100)}% 时卖出 {int(tp['sell_ratio']*100)}% 仓位")
        lines.append("")
        pr = s.position_rules
        lines.append(f"💰 仓位管理：总仓位不超过 {int(pr['max_total_position_pct']*100)}%，每只股票不超过 {int(pr['single_stock_pct']*100)}%，最多持有 {pr['max_stocks']} 只股票")
        return "\n".join(lines)
    
    def _generate_risk_warning(self, s):
        warnings = []
        style_risks = {
            "short_term": "短线频繁交易会产生较多手续费，遇到极端行情可能连续亏损。",
            "mid_term": "趋势策略在震荡市中容易出现假信号，需要耐心等待。",
            "low_vol": "低波动策略在牛市中可能跑输大盘，收益空间有限。",
            "value": "价值股的估值修复可能需要较长时间，需要有足够耐心。",
        }
        if s.style in style_risks:
            warnings.append(style_risks[s.style])
        if s.stop_loss_pct > 0.07:
            warnings.append(f"止损线设在 {int(s.stop_loss_pct*100)}%，相对较宽，单笔最大亏损可能较大。")
        if len(s.factors) >= 6:
            warnings.append("使用了较多因子，可能出现条件过于严格导致很少触发交易的情况。")
        return "\n".join(warnings) if warnings else "该策略风险适中，但仍需注意市场系统性风险。"
    
    def translate_backtest_result(self, result) -> str:
        lines = ["📊 回测结果解读：", ""]
        annual = result.annual_return
        if annual > 0.2: lines.append(f"✅ 年化收益率 {annual*100:.1f}%，表现非常优秀。")
        elif annual > 0.05: lines.append(f"✅ 年化收益率 {annual*100:.1f}%，表现尚可。")
        else: lines.append(f"⚠️ 年化收益率 {annual*100:.1f}%，收益偏低。")
        dd = result.max_drawdown
        if dd < 0.1: lines.append(f"✅ 最大回撤仅 {dd*100:.1f}%，风控出色。")
        elif dd < 0.2: lines.append(f"⚠️ 最大回撤 {dd*100:.1f}%，在可接受范围内。")
        else: lines.append(f"🔴 最大回撤 {dd*100:.1f}%，超过15%警戒线，已自动淘汰。")
        if result.sharpe_ratio > 1: lines.append(f"✅ 夏普比率 {result.sharpe_ratio:.2f}，风险调整后收益良好。")
        lines.append(f"📈 胜率 {result.win_rate*100:.1f}%，共交易 {result.trade_count} 次。")
        lines.append(f"📊 综合评分: {result.composite_score}/100")
        return "\n".join(lines)


translator = PlainLanguageTranslator()
