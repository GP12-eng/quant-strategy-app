"""策略 API v1 — 动态风格 + 自动龙头选股"""
import uuid, io, json, concurrent.futures
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.services.strategy_engine.composer import StrategyComposer, strategy_to_dict
from app.services.strategy_engine.translator import translator

router = APIRouter()
_strategies_store: dict[str, dict] = {}
_composer = StrategyComposer()

STOCK_POOLS = {"hs300":{"name":"沪深300","count":300},"zz500":{"name":"中证500","count":500},"all_a":{"name":"全A股","count":4500},"core20":{"name":"核心20只","count":20},"custom":{"name":"自定义","count":0}}

def _run_backtest_sync(sid, sd, sdata, stock_pool="core20", custom_symbols=None):
    def _run_in_thread():
        import asyncio
        from app.services.backtest_engine.real_data_runner import RealDataBacktestRunner, BacktestConfig
        async def _run():
            try:
                config = BacktestConfig()
                if not custom_symbols:
                    try:
                        from app.api.v1.market import _market_cache, _cache_lock
                        with _cache_lock: leaders = [s["symbol"] for s in _market_cache.get("stocks",[])[:10]]
                        if leaders: config.symbols = leaders; sdata["auto_stocks"] = leaders
                    except: pass
                elif custom_symbols: config.symbols = custom_symbols
                if not config.symbols: config.symbols = None
                config.pool_name = stock_pool
                runner = RealDataBacktestRunner()
                result = await runner.run_single(sd, config)
                from app.api.v1.backtest import _results_store, _format_result
                _results_store[sid] = result
                sdata["backtest"] = _format_result(result)
                sdata["backtest_status"] = "done"
            except Exception as e:
                sdata["backtest_status"] = "failed"
                sdata["backtest_error"] = str(e)[:300]
        try: asyncio.run(_run())
        except Exception as e: sdata["backtest_status"] = "failed"; sdata["backtest_error"] = str(e)[:300]
    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_run_in_thread)

@router.get("/pools")
async def list_stock_pools():
    return {"pools":[{"id":k,"name":v["name"],"count":v["count"]} for k,v in STOCK_POOLS.items()]}

@router.get("")
async def list_strategies(style:str|None=Query(None),search:str|None=Query(None),sort:str|None=Query(None),status:str|None=Query(None),limit:int=Query(20,ge=1,le=200),offset:int=Query(0,ge=0)):
    result=list(_strategies_store.values())
    if style: result=[s for s in result if s.get("style")==style or s.get("dynamic_style","").find(style)>=0]
    if search: result=[s for s in result if search.lower() in s.get("name","").lower()]
    if status: result=[s for s in result if s.get("status","active")==status]
    if sort=="score": result.sort(key=lambda s:s.get("backtest",{}).get("composite_score",0) or 0,reverse=True)
    elif sort=="return": result.sort(key=lambda s:s.get("backtest",{}).get("annual_return_pct",0) or 0,reverse=True)
    else: result.sort(key=lambda s:s.get("generated_at",""),reverse=True)
    return {"total":len(result),"items":result[offset:offset+limit]}

@router.post("/generate")
async def generate_strategies(count:int=Query(10,ge=1,le=50),auto_backtest:bool=Query(True),stock_pool:str=Query("core20"),background_tasks:BackgroundTasks=None):
    definitions=_composer.compose_batch(count)
    created=[]
    for d in definitions:
        sid=f"STG_{uuid.uuid4().hex[:8]}"
        now=datetime.now(timezone.utc).isoformat()
        explanation=translator.translate(d)
        strategy_data={"id":sid,"name":d.name,"style":d.style,"dynamic_style":d.dynamic_style,"status":"active","generated_at":now,"factors":[{"name":f.factor_name,"label":f.factor_name,"params":f.params,"weight":f.weight} for f in d.factors],"plain_explanation":{"logic":explanation["one_liner"],"entry_rules":d.entry_conditions,"exit_rules":[f"止损：亏损 {int(d.stop_loss_pct*100)}% 无条件卖出"]+[f"止盈第{tp['level']}档：盈利 {int(tp['pct']*100)}% 卖出 {int(tp['sell_ratio']*100)}%" for tp in d.take_profit_rules],"position_rule":f"总仓位 ≤ {int(d.position_rules['max_total_position_pct']*100)}%，单票 ≤ {int(d.position_rules['single_stock_pct']*100)}%，最多 {d.position_rules['max_stocks']} 只","suitable_market":d.market_conditions},"backtest":None,"backtest_status":"pending","stock_pool":stock_pool,"practical_advice":{"when_to_use":explanation["plain_text"],"risk_warning":explanation["risk_warning"],"suggested_capital":"建议 5-10 万"},"_raw_definition":d}
        _strategies_store[sid]=strategy_data
        created.append(strategy_data)
        if auto_backtest and background_tasks: background_tasks.add_task(_run_backtest_sync,sid,d,strategy_data,stock_pool)
    return {"count":len(created),"strategies":created}

@router.get("/{strategy_id}")
async def get_strategy(strategy_id:str):
    s=_strategies_store.get(strategy_id)
    if not s: raise HTTPException(404,"策略不存在")
    return s

@router.get("/stats/dashboard")
async def dashboard_stats():
    all_s=list(_strategies_store.values())
    active=[s for s in all_s if s.get("status")=="active"]
    passed=[s for s in active if s.get("backtest",{}).get("passed")]
    failed=[s for s in active if s.get("backtest") and not s.get("backtest",{}).get("passed")]
    total_annual=sum(s.get("backtest",{}).get("annual_return_pct",0) or 0 for s in passed)
    return {"total_strategies":len(all_s),"active_strategies":len(active),"passed_backtest":len(passed),"failed_backtest":len(failed),"avg_annual_return":round(total_annual/max(len(passed),1),1),"styles":{s:len([x for x in active if x.get("style")==s or x.get("dynamic_style","").find(s)>=0]) for s in ["short_term","mid_term","low_vol","value"]}}

@router.get("/{strategy_id}/export")
async def export_strategy(strategy_id:str,fmt:str=Query("json")):
    s=_strategies_store.get(strategy_id)
    if not s: raise HTTPException(404,"策略不存在")
    if fmt=="txt":
        bt=s.get("backtest",{})
        text=f"# {s['name']}\n风格: {s.get('dynamic_style',s.get('style',''))}\n\n## 概括\n{s.get('plain_explanation',{}).get('logic','')}\n\n## 回测\n年化: {bt.get('annual_return_pct','N/A')}%  回撤: {bt.get('max_drawdown_pct','N/A')}%  评分: {bt.get('composite_score','N/A')}/100\n"
        return StreamingResponse(io.BytesIO(text.encode('utf-8')),media_type="text/plain",headers={"Content-Disposition":f"attachment; filename={s['name']}.txt"})
    return {"name":s["name"],"style":s.get("dynamic_style",s.get("style")),"factors":s.get("factors",[]),"backtest":s.get("backtest")}
