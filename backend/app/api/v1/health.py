"""模拟引擎 REST API — start/stop/status"""
from fastapi import APIRouter
router = APIRouter()

@router.post("/simulation/start")
async def start_simulation(payload: dict):
    from app.services.simulation_engine.engine import simulation_engine
    from app.api.v1.strategies import _strategies_store
    from app.services.strategy_engine.composer import StrategyDefinition, FactorSelection
    ids = payload.get("strategy_ids", [])
    active = []
    for s in _strategies_store.values():
        if ids and s.get("id") not in ids: continue
        if not ids and not (s.get("backtest_status")=="done" and s.get("backtest",{}).get("passed")): continue
        d = s.get("_raw_definition")
        if not d:
            factors = [FactorSelection(factor_name=f.get("name","momentum"),params=f.get("params",{}),weight=f.get("weight",0.2)) for f in s.get("factors",[])]
            d = StrategyDefinition(name=s.get("name",""),style=s.get("style","mid_term"),dynamic_style=s.get("dynamic_style",""),core_logic="",factors=factors,entry_conditions=[],buy_timing="close",take_profit_rules=[],stop_loss_pct=0.05,position_rules={"max_total_position_pct":0.8,"single_stock_pct":0.1,"max_stocks":5},rebalance_rules="weekly",market_conditions="all",hold_days=(5,20))
        active.append(d)
    await simulation_engine.start(active[:10])
    return {"status":"started","strategies":len(active[:10]),"message":f"已启动{len(active[:10])}个策略"}

@router.post("/simulation/stop")
async def stop_simulation():
    from app.services.simulation_engine.engine import simulation_engine
    await simulation_engine.stop()
    return {"status":"stopped","message":"已停止"}

@router.get("/simulation/status")
async def simulation_status():
    from app.services.simulation_engine.engine import simulation_engine
    return {"running":simulation_engine._running,"strategies":len(simulation_engine.active_strategies),"signals":len(simulation_engine.signals)}
