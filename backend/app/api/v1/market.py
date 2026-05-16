"""市场 API — 全局缓存 + 数据新鲜度 + 交易时间检测"""
import asyncio, time, threading
from datetime import datetime
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
router = APIRouter()

_market_cache: dict = {"stocks":[],"indices":[],"summary":{"up":0,"down":0,"flat":0},"updated_at":"","market_open":True,"data_age_sec":0}
_cache_lock = threading.Lock()

def _is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False
    t = now.hour * 60 + now.minute
    return 9*60+15 <= t <= 15*60+5

def _fetch_market_data():
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty: return
        indices = []
        for code, name in [("000001","上证指数"),("399001","深证成指"),("399006","创业板指")]:
            row = df[df["代码"]==code]
            if not row.empty:
                r = row.iloc[0]
                indices.append({"code":code,"name":name,"price":float(r["最新价"]) if r["最新价"] else 0,"change_pct":float(r["涨跌幅"]) if r["涨跌幅"] else 0})
        changes = df["涨跌幅"].dropna()
        up, down, flat = int((changes>0).sum()), int((changes<0).sum()), int((changes==0).sum())
        df_sorted = df.sort_values("成交额", ascending=False).head(200)
        stocks = []
        for _, r in df_sorted.iterrows():
            stocks.append({"symbol":str(r["代码"]),"name":str(r["名称"]),"price":float(r["最新价"]) if r["最新价"] and r["最新价"]!="-" else 0,"change_pct":float(r["涨跌幅"]) if r["涨跌幅"] and r["涨跌幅"]!="-" else 0,"volume":float(r["成交量"]) if r["成交量"] and r["成交量"]!="-" else 0,"amount":float(r["成交额"]) if r["成交额"] and r["成交额"]!="-" else 0})
        with _cache_lock:
            _market_cache["stocks"] = stocks; _market_cache["indices"] = indices
            _market_cache["summary"] = {"up":up,"down":down,"flat":flat}
            _market_cache["updated_at"] = time.strftime("%H:%M:%S")
            _market_cache["market_open"] = _is_market_open()
            _market_cache["data_age_sec"] = 0
    except Exception as e:
        with _cache_lock:
            _market_cache["data_age_sec"] = _market_cache.get("data_age_sec", 0) + 5
            _market_cache["error"] = str(e)[:100]

def _refresh_loop():
    while True:
        try: _fetch_market_data()
        except: pass
        with _cache_lock: _market_cache["data_age_sec"] = _market_cache.get("data_age_sec", 0) + 5
        time.sleep(5)

threading.Thread(target=_refresh_loop, daemon=True).start()

@router.get("/indices")
async def get_indices():
    with _cache_lock:
        return {"indices":_market_cache.get("indices",[]),"updated_at":_market_cache.get("updated_at",""),"market_open":_market_cache.get("market_open",False),"data_age_sec":_market_cache.get("data_age_sec",0)}

@router.get("/live")
async def get_live_market(sort:str=Query("amount"),page:int=Query(1,ge=1),page_size:int=Query(50,ge=10,le=200)):
    with _cache_lock:
        stocks=list(_market_cache.get("stocks",[])); summary=dict(_market_cache.get("summary",{})); updated=_market_cache.get("updated_at",""); err=_market_cache.get("error",""); mo=_market_cache.get("market_open",False); age=_market_cache.get("data_age_sec",0)
    if sort=="change_pct": stocks.sort(key=lambda s:s.get("change_pct",0),reverse=True)
    elif sort=="price": stocks.sort(key=lambda s:s.get("price",0),reverse=True)
    elif sort=="volume": stocks.sort(key=lambda s:s.get("volume",0),reverse=True)
    total=len(stocks); start=(page-1)*page_size
    return {"stocks":stocks[start:start+page_size],"total":total,"page":page,"summary":summary,"updated_at":updated,"market_open":mo,"data_age_sec":age,"error":err}

@router.get("/leaders")
async def get_leaders():
    with _cache_lock:
        stocks=_market_cache.get("stocks",[]); age=_market_cache.get("data_age_sec",0); mo=_market_cache.get("market_open",False)
    return {"pool":[{"symbol":s["symbol"],"name":s["name"]} for s in stocks[:50]],"source":"成交额TOP50","market_open":mo,"data_age_sec":age,"updated_at":_market_cache.get("updated_at","")}

@router.get("/search")
async def search_stocks(q:str=Query("")):
    if not q: return {"results":[]}
    with _cache_lock: stocks=_market_cache.get("stocks",[])
    ql=q.lower().strip()
    return {"results":[{"symbol":s["symbol"],"name":s["name"],"price":s["price"],"change_pct":s["change_pct"]} for s in stocks if ql in s["symbol"] or ql in s["name"].lower()][:20],"query":q}

class ConnectionManager:
    def __init__(self): self.active={}; self.subs={}
    async def connect(self,cid,ws): await ws.accept(); self.active[cid]=ws; self.subs[cid]=set()
    def disconnect(self,cid): self.active.pop(cid,None); self.subs.pop(cid,None)

manager=ConnectionManager()

@router.websocket("/ws/{client_id}")
async def ws_endpoint(ws:WebSocket,client_id:str):
    await manager.connect(client_id,ws)
    try:
        await ws.send_json({"type":"connected","data":{"client_id":client_id}})
        while True:
            data=await ws.receive_json(); t=data.get("type")
            if t=="subscribe": manager.subscribe(client_id,data.get("symbols",[]))
            elif t=="ping": await ws.send_json({"type":"pong"})
    except WebSocketDisconnect: manager.disconnect(client_id)
    except: manager.disconnect(client_id)
