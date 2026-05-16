"""回测缓存 — TTL 300秒, 最大100条"""
import hashlib, time
_cache: dict = {}
def cache_key(sd, syms, s, e, cap): return hashlib.md5(f"{sd.name}|{'-'.join(sorted(syms))}|{s}|{e}|{cap}".encode()).hexdigest()
def get_cached(k):
    e = _cache.get(k)
    if e and time.time()-e[0] < 300: return e[1]
    if e: del _cache[k]
    return None
def set_cache(k, v):
    _cache[k] = (time.time(), v)
    if len(_cache) > 100:
        oldest = min(_cache, key=lambda x: _cache[x][0])
        del _cache[oldest]
