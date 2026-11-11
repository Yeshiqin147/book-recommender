/* 阅荐言情 PWA Service Worker v6 */
const CACHE = "yujian-romance-v6";
const ASSETS = [
  "./",
  "./index.html",
  "./style.css?v=6",
  "./app.js?v=6",
  "./story-data.js?v=6",
  "./books.json",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (e)=>{
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).catch(()=>{}));
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
  // 网络优先：先拿最新版，失败才用缓存
  e.respondWith(
    fetch(req).then(res=>{
      const copy = res.clone();
      caches.open(CACHE).then(c=>c.put(req, copy)).catch(()=>{});
      return res;
    }).catch(()=> caches.match(req).then(hit=> hit || caches.match("./")))
  );
});
