"""市场 API v1 — WebSocket行情 + 股票搜索 + 龙头池"""
import asyncio
from typing import Dict, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
router = APIRouter()

@router.get("/search")
async def search_stocks(q: str = Query("")):
    if not q: return {"results": []}
    try:
        from app.services.data_provider.adapter import get_provider
        provider = get_provider()
        df = await provider.get_stock_list()
        if df.empty: return {"results": []}
        ql = q.lower().strip()
        results = []
        for _, row in df.iterrows():
            sym = str(row.get("symbol", row.get("code", "")))
            name = str(row.get("name", row.get("code_name", "")))
            if ql in sym or ql in name.lower():
                results.append({"symbol": sym, "name": name, "display": f"{sym} {name}"})
                if len(results) >= 20: break
        return {"results": results, "query": q}
    except Exception as e:
        return {"results": [], "error": str(e)}

@router.get("/leaders")
async def get_leaders():
    try:
        try:
            import akshare as ak
            df = ak.index_stock_cons_weight_csindex("000300")
            syms = df["成分券代码"].tolist()[:50] if "成分券代码" in df.columns else []
            names = df["成分券名称"].tolist()[:50] if "成分券名称" in df.columns else []
            return {"pool": [{"symbol": s, "name": n} for s, n in zip(syms, names)], "source": "沪深300"}
        except: pass
        from app.services.data_provider.adapter import get_provider
        df = await get_provider().get_stock_list()
        return {"pool": [{"symbol": str(r.get("symbol","")), "name": str(r.get("name",""))} for _, r in df.head(100).iterrows()], "source": "全A股"}
    except Exception as e:
        return {"pool": [], "error": str(e)}

@router.post("/validate")
async def validate_symbols(payload: dict):
    syms = payload.get("symbols", [])
    if not syms: return {"valid": [], "invalid": []}
    try:
        from app.services.data_provider.adapter import get_provider
        df = await get_provider().get_stock_list()
        all_codes = set(str(r.get("symbol", r.get("code", ""))) for _, r in df.iterrows())
        return {"valid": [s for s in syms if s in all_codes], "invalid": [s for s in syms if s not in all_codes]}
    except: return {"valid": [], "invalid": syms}

class ConnectionManager:
    def __init__(self): self.active = {}; self.subs = {}
    async def connect(self, cid, ws): await ws.accept(); self.active[cid] = ws; self.subs[cid] = set()
    def disconnect(self, cid): self.active.pop(cid, None); self.subs.pop(cid, None)
    def subscribe(self, cid, syms):
        if cid in self.subs: self.subs[cid].update(syms)
    async def broadcast_quotes(self, quotes):
        for cid, ws in list(self.active.items()):
            try:
                subbed = self.subs.get(cid, set())
                filtered = {s: q for s, q in quotes.items() if s in subbed or not subbed}
                if filtered: await ws.send_json({"type": "quotes", "data": filtered})
            except: self.disconnect(cid)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def ws_endpoint(ws: WebSocket, client_id: str):
    await manager.connect(client_id, ws)
    try:
        await ws.send_json({"type": "connected", "data": {"client_id": client_id}})
        while True:
            data = await ws.receive_json()
            t = data.get("type")
            if t == "subscribe": manager.subscribe(client_id, data.get("symbols", []))
            elif t == "ping": await ws.send_json({"type": "pong"})
    except WebSocketDisconnect: manager.disconnect(client_id)
    except Exception: manager.disconnect(client_id)

@router.websocket("/ws/market")
async def market_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await asyncio.sleep(3)
            from app.services.data_provider.adapter import get_provider
            try:
                quotes = await get_provider().get_realtime_quote(["600519","000858","300750","600036","601318"])
                await ws.send_json({"type": "market_snapshot", "data": quotes})
            except: pass
    except WebSocketDisconnect: pass
    except Exception: pass

async def market_broadcast_loop():
    from app.services.data_provider.adapter import get_provider
    provider = get_provider()
    syms = ["600519","000858","300750","600036","601318","000333","002594","600900","601166","600276","000651","601012","300059","002475","600050"]
    while True:
        try:
            quotes = await provider.get_realtime_quote(syms)
            if quotes: await manager.broadcast_quotes(quotes)
        except: pass
        await asyncio.sleep(5)
