"""数据源适配器 — Hybrid: Baostock历史K线优先 + AKShare实时行情优先"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import date
import pandas as pd
from app.core.config import settings

class DataProvider(ABC):
    @abstractmethod
    async def get_stock_list(self) -> pd.DataFrame: ...
    @abstractmethod
    async def get_daily_k(self, symbol: str, start: date, end: date, adjust: str = "qfq") -> pd.DataFrame: ...
    @abstractmethod
    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, dict]: ...
    @abstractmethod
    async def get_stock_info(self, symbol: str) -> dict: ...

class AKShareProvider(DataProvider):
    def __init__(self): import akshare as ak; self.ak = ak
    async def get_stock_list(self):
        df = self.ak.stock_info_a_code_name(); df.columns = ["symbol", "name"]; return df
    async def get_daily_k(self, symbol, start, end, adjust="qfq"):
        code = symbol.replace("sh","").replace("sz","")
        df = self.ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust=adjust)
        df = df.rename(columns={"日期":"date","开盘":"open","最高":"high","最低":"low","收盘":"close","成交量":"volume","成交额":"amount"})
        df["date"] = pd.to_datetime(df["date"]); return df.set_index("date").sort_index()
    async def get_realtime_quote(self, symbols):
        try:
            df = self.ak.stock_zh_a_spot_em()
            codes = [s.replace("sh","").replace("sz","") for s in symbols]
            df = df[df["代码"].isin(codes)]
            return {r["代码"]:{"name":r["名称"],"price":r["最新价"],"change_pct":r["涨跌幅"],"volume":r["成交量"],"amount":r["成交额"]} for _,r in df.iterrows()}
        except: return {}
    async def get_stock_info(self, symbol): return {}

class BaostockProvider(DataProvider):
    def __init__(self): import baostock as bs; self.bs = bs; self._logged_in = False
    def _login(self):
        if not self._logged_in: lg = self.bs.login(); self._logged_in = lg.error_code == '0'
        return self._logged_in
    async def get_stock_list(self):
        self._login(); rs = self.bs.query_stock_basic()
        return rs.get_data().rename(columns={'code':'symbol','code_name':'name'})
    async def get_daily_k(self, symbol, start, end, adjust="qfq"):
        self._login()
        code = f"sh.{symbol}" if symbol.startswith('6') else f"sz.{symbol}"
        rs = self.bs.query_history_k_data_plus(code, "date,open,high,low,close,volume,amount", start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"), frequency="d", adjustflag="2" if adjust=="qfq" else "1")
        df = rs.get_data()
        if df.empty: return df
        for c in ['open','high','low','close','volume','amount']: df[c] = pd.to_numeric(df[c], errors='coerce')
        df['date'] = pd.to_datetime(df['date']); return df.set_index('date').sort_index()
    async def get_realtime_quote(self, symbols): return {}
    async def get_stock_info(self, symbol): return {}

class HybridProvider(DataProvider):
    def __init__(self):
        self.ak = self.bs = None
        try: self.ak = AKShareProvider()
        except: pass
        try: self.bs = BaostockProvider()
        except: pass
    async def get_daily_k(self, *a, **kw):
        for p in [self.bs, self.ak]:
            if p is None: continue
            try:
                r = await p.get_daily_k(*a, **kw)
                if isinstance(r, pd.DataFrame) and not r.empty and len(r) > 10: return r
            except: continue
        return pd.DataFrame()
    async def get_realtime_quote(self, *a, **kw):
        if self.ak:
            try:
                r = await self.ak.get_realtime_quote(*a, **kw)
                if r: return r
            except: pass
        return {}
    async def get_stock_list(self):
        for p in [self.ak, self.bs]:
            if p is None: continue
            try:
                r = await p.get_stock_list()
                if isinstance(r, pd.DataFrame) and not r.empty: return r
            except: continue
        return pd.DataFrame()
    async def get_stock_info(self, *a, **kw):
        if self.ak:
            try: return await self.ak.get_stock_info(*a, **kw)
            except: pass
        return {}

def get_provider():
    p = settings.DATA_PROVIDER
    if p == "hybrid": return HybridProvider()
    if p == "akshare": return AKShareProvider()
    if p == "baostock": return BaostockProvider()
    return HybridProvider()
