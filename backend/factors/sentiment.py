"""因子11: 市场情绪因子"""
import numpy as np
import pandas as pd
from factors import BaseFactor, FactorParam, register_factor

@register_factor
class SentimentFactor(BaseFactor):
    name = "sentiment"; description = "市场情绪:连涨连跌+成交量异动+振幅"
    @property
    def params(self):
        return [FactorParam("lookback","int",5,30), FactorParam("fear_threshold","float",-3.0,-1.0), FactorParam("greed_threshold","float",1.0,3.0)]
    def compute(self, data, params):
        lb=params["lookback"]; close=data["close"]; volume=data["volume"]; high=data["high"]; low=data["low"]
        direction=np.sign(close.diff()); streak=direction.copy()
        for i in range(1,len(streak)):
            if direction.iloc[i]==direction.iloc[i-1] and direction.iloc[i]!=0: streak.iloc[i]=streak.iloc[i-1]+direction.iloc[i]
        fear=streak.clip(upper=0).abs()/5; greed=streak.clip(lower=0)/5
        vol_surge=volume/volume.rolling(lb).mean().replace(0,1)
        amplitude=(high-low)/close.replace(0,1)
        score=-fear*0.4+greed*0.3+(vol_surge>1.5).astype(float)*(np.sign(close.pct_change())*0.2)+(amplitude<amplitude.rolling(lb).mean()).astype(float)*0.1
        return score.fillna(0)
