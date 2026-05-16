"""模拟引擎 — 适配新浪行情缓存"""
# tick() 改为从 _market_cache 读取，不再调用 provider.get_realtime_quote()
# 策略数限制为5，每tick只扫描TOP20股票