"""因子10: 质量因子"""
import numpy as np
import pandas as pd
from factors import BaseFactor, FactorParam, register_factor

@register_factor
class QualityFactor(BaseFactor):
    name = "quality"; description = "价格隐含质量:高上涨占比+低波动+正动量"
    @property
    def params(self):
        return [FactorParam("lookback","int",20,120), FactorParam("stability_weight","float",0.3,0.7), FactorParam("min_growth","float",0.0,0.05)]
    def compute(self, data, params):
        lb=params["lookback"]; close=data["close"]
        up_ratio = (close.diff()>0).rolling(lb).sum() / close.diff().notna().rolling(lb).sum().replace(0,1)
        stability = 1.0/(1.0+close.pct_change().rolling(lb).std()*100)
        momentum = close.pct_change(lb)
        return (up_ratio*0.3 + stability*params["stability_weight"] + (momentum>params["min_growth"]).astype(float)*0.3).fillna(0)
