// Cache only the public offline explanation. Never cache API, OTP, private pages or media.
const CACHE = 'roadscan-public-v1';
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache=>cache.add('/offline.html'))); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('roadscan-public-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())); });
self.addEventListener('fetch', event => {
  if(event.request.method!=='GET'||event.request.mode!=='navigate') return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin||url.pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).catch(()=>caches.match('/offline.html')));
});
