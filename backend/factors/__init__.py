"""
因子系统 — 基类 + 注册表
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class FactorParam:
    name: str
    param_type: str
    range_min: float = None
    range_max: float = None
    choices: List[Any] = None
    description: str = ""


class BaseFactor(ABC):
    name: str = "base"
    description: str = ""
    
    @property
    @abstractmethod
    def params(self) -> List[FactorParam]:
        ...
    
    @abstractmethod
    def compute(self, data: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        ...
    
    def random_params(self) -> Dict[str, Any]:
        import random
        result = {}
        for p in self.params:
            if p.param_type == "int":
                result[p.name] = random.randint(int(p.range_min), int(p.range_max))
            elif p.param_type == "float":
                result[p.name] = round(random.uniform(p.range_min, p.range_max), 4)
            elif p.param_type == "choice":
                result[p.name] = random.choice(p.choices)
        return result


FACTOR_REGISTRY: Dict[str, type] = {}


def register_factor(cls):
    FACTOR_REGISTRY[cls.name] = cls
    return cls


from factors.trend_ma import TrendMAFactor
from factors.volume import VolumeFactor
from factors.price_position import PricePositionFactor
from factors.volatility import VolatilityFactor
from factors.momentum import MomentumFactor
from factors.money_flow import MoneyFlowFactor
from factors.fundamental import FundamentalFactor
from factors.breakout import BreakoutFactor
from factors.pullback import PullbackFactor
