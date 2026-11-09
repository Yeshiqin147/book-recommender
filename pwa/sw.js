/* 阅荐 PWA Service Worker：离线缓存，网络优先保证更新 */
const CACHE = "yujian-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./style.css?v=2",
  "./app.js?v=2",
  "./books.json",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (e)=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate", (e)=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(
    keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))
  )).then(()=>self.clients.claim()));
});

self.addEventListener("fetch", (e)=>{
  const req = e.request;
  if(req.method!=="GET") return;
  const url = new URL(req.url);
  if(url.origin!==location.origin) return;
  // 网络优先：先尝试拿最新版，失败才用缓存
  e.respondWith(
    fetch(req).then(res=>{
      const copy = res.clone();
      caches.open(CACHE).then(c=>c.put(req, copy));
      return res;
    }).catch(()=> caches.match(req).then(hit=> hit || caches.match("./index.html")))
  );
});
