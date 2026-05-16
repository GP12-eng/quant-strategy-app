"""行情广播 + 模拟引擎联动"""
async def market_broadcast_loop():
    from app.services.data_provider.adapter import get_provider
    from app.services.simulation_engine.engine import simulation_engine
    provider = get_provider()
    syms = ["600519","000858","300750","600036","601318","000333","002594","600900","601166"]
    while True:
        try:
            quotes = await provider.get_realtime_quote(syms)
            if quotes:
                await manager.broadcast_quotes(quotes)
                if simulation_engine._running:
                    sigs = await simulation_engine.tick()
                    for sig in sigs[-5:]:
                        await manager.broadcast_signal({"id":f"SIG_{sig.timestamp.timestamp()}","strategy_name":sig.strategy_name,"symbol":sig.symbol,"stock_name":sig.stock_name,"direction":sig.direction.value,"price":sig.price,"score":sig.score,"reason":sig.reason,"timestamp":sig.timestamp.isoformat()})
        except: pass
        await asyncio.sleep(5)
