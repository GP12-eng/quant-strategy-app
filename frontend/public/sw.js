// PWA Service Worker — 后台同步 + 离线缓存
const CACHE = 'quant-app-v1'
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(['/','/index.html']))); self.skipWaiting() })
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim() })
self.addEventListener('fetch', (e) => { e.respondWith(caches.match(e.request).then(r => r || fetch(e.request))) })
self.addEventListener('sync', (e) => { if (e.tag === 'sync-market') { e.waitUntil(fetch('/api/v1/market/live').then(r => r.json()).then(d => { self.clients.matchAll().then(clients => clients.forEach(c => c.postMessage({type:'market-update',data:d}))) })) } })
