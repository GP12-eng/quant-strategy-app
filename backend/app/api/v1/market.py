"""市场 API v1 — 行情面板 + 股票搜索 + WebSocket"""
import asyncio
from typing import Dict, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
router = APIRouter()

@router.get("/indices")
async def get_indices():
    try:
        from app.services.data_provider.adapter import get_provider
        quotes = await get_provider().get_realtime_quote(["000001","399001","399006"])
        indices = {"sh":{"name":"上证指数","code":"000001","price":3252.68,"change_pct":0.42},"sz":{"name":"深证成指","code":"399001","price":11089.23,"change_pct":-0.18},"cy":{"name":"创业板指","code":"399006","price":2156.30,"change_pct":1.20}}
        for k,c in [("sh","000001"),("sz","399001"),("cy","399006")]:
            if c in quotes:
                q=quotes[c]; indices[k]["price"]=q.get("price",indices[k]["price"]); indices[k]["change_pct"]=q.get("change_pct",indices[k]["change_pct"])
        return {"indices":list(indices.values()),"updated":True}
    except: return {"indices":[{"name":"上证指数","code":"000001","price":3252.68,"change_pct":0.42},{"name":"深证成指","code":"399001","price":11089.23,"change_pct":-0.18},{"name":"创业板指","code":"399006","price":2156.30,"change_pct":1.20}],"updated":False}

@router.get("/live")
async def get_live_market(page:int=Query(1,ge=1),page_size:int=Query(50,ge=10,le=200),sort:str=Query("change_pct")):
    try:
        import akshare as ak
        df=ak.stock_zh_a_spot_em()
        if df.empty: return {"stocks":[],"total":0,"summary":{"up":0,"down":0,"flat":0}}
        up=int((df["涨跌幅"]>0).sum()); down=int((df["涨跌幅"]<0).sum()); flat=int((df["涨跌幅"]==0).sum())
        if sort=="volume": df=df.sort_values("成交额",ascending=False)
        elif sort=="price": df=df.sort_values("最新价",ascending=False)
        else: df=df.sort_values("涨跌幅",ascending=False)
        total=len(df); start=(page-1)*page_size; pdf=df.iloc[start:start+page_size]
        stocks=[{"symbol":str(r["代码"]),"name":str(r["名称"]),"price":float(r["最新价"]) if r["最新价"] else 0,"change_pct":float(r["涨跌幅"]) if r["涨跌幅"] else 0,"volume":float(r["成交量"]) if r["成交量"] else 0,"amount":float(r["成交额"]) if r["成交额"] else 0,"turnover":float(r.get("换手率",0))} for _,r in pdf.iterrows()]
        return {"stocks":stocks,"total":total,"page":page,"summary":{"up":up,"down":down,"flat":flat}}
    except Exception as e: return {"stocks":[],"total":0,"summary":{"up":0,"down":0,"flat":0},"error":str(e)}

@router.get("/search")
async def search_stocks(q:str=Query("")):
    if not q: return {"results":[]}
    try:
        from app.services.data_provider.adapter import get_provider
        df=await get_provider().get_stock_list()
        if df.empty: return {"results":[]}
        ql=q.lower().strip(); results=[]
        for _,r in df.iterrows():
            s=str(r.get("symbol",r.get("code",""))); n=str(r.get("name",r.get("code_name","")))
            if ql in s or ql in n.lower():
                results.append({"symbol":s,"name":n,"display":f"{s} {n}"})
                if len(results)>=20: break
        return {"results":results,"query":q}
    except: return {"results":[]}

@router.get("/leaders")
async def get_leaders():
    try:
        try:
            import akshare as ak
            df=ak.index_stock_cons_weight_csindex("000300")
            s=df["成分券代码"].tolist()[:50] if "成分券代码" in df.columns else []
            n=df["成分券名称"].tolist()[:50] if "成分券名称" in df.columns else []
            return {"pool":[{"symbol":x,"name":y} for x,y in zip(s,n)],"source":"沪深300"}
        except: pass
        from app.services.data_provider.adapter import get_provider
        df=await get_provider().get_stock_list()
        return {"pool":[{"symbol":str(r.get("symbol","")),"name":str(r.get("name",""))} for _,r in df.head(100).iterrows()],"source":"全A股"}
    except: return {"pool":[]}

@router.post("/validate")
async def validate_symbols(payload:dict):
    syms=payload.get("symbols",[])
    if not syms: return {"valid":[],"invalid":[]}
    try:
        from app.services.data_provider.adapter import get_provider
        df=await get_provider().get_stock_list()
        codes=set(str(r.get("symbol",r.get("code",""))) for _,r in df.iterrows())
        return {"valid":[s for s in syms if s in codes],"invalid":[s for s in syms if s not in codes]}
    except: return {"valid":[],"invalid":syms}

class ConnectionManager:
    def __init__(self): self.active={}; self.subs={}
    async def connect(self,cid,ws): await ws.accept(); self.active[cid]=ws; self.subs[cid]=set()
    def disconnect(self,cid): self.active.pop(cid,None); self.subs.pop(cid,None)
    def subscribe(self,cid,syms):
        if cid in self.subs: self.subs[cid].update(syms)
    async def broadcast_quotes(self,quotes):
        for cid,ws in list(self.active.items()):
            try:
                subbed=self.subs.get(cid,set())
                filtered={s:q for s,q in quotes.items() if s in subbed or not subbed}
                if filtered: await ws.send_json({"type":"quotes","data":filtered})
            except: self.disconnect(cid)

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

@router.websocket("/ws/market")
async def market_ws(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            await asyncio.sleep(3)
            try:
                quotes=await __import__('app.services.data_provider.adapter',fromlist=['get_provider']).get_provider().get_realtime_quote(["600519","000858","300750","600036","601318"])
                await ws.send_json({"type":"market_snapshot","data":quotes})
            except: pass
    except WebSocketDisconnect: pass
    except: pass

async def market_broadcast_loop():
    from app.services.data_provider.adapter import get_provider
    provider=get_provider()
    syms=["600519","000858","300750","600036","601318","000333","002594","600900","601166","600276","000651","601012","300059","002475","600050"]
    while True:
        try:
            quotes=await provider.get_realtime_quote(syms)
            if quotes: await manager.broadcast_quotes(quotes)
        except: pass
        await asyncio.sleep(5)
