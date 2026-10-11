const CACHE_VERSION = 'quiet-tracker-v2';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;

const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/stats.js',
  '/static/js/stats-daily.js',
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => !k.startsWith(CACHE_VERSION)).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Never cache personal data endpoints
  if (
    url.pathname.startsWith('/stats') ||
    url.pathname.startsWith('/compare/data') ||
    url.pathname === '/export'
  ) {
    return;
  }

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/') || url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(resp => {
          if (resp.status === 200) {
            const clone = resp.clone();
            caches.open(STATIC_CACHE).then(c => c.put(request, clone));
          }
          return resp;
        });
      })
    );
    return;
  }

   // HTML pages: network-first, cache only as offline fallback
  const acceptsHtml = (request.headers.get('accept') || '').includes('text/html');
  if (request.mode === 'navigate' || acceptsHtml) {
    event.respondWith(
      fetch(request)
        .then(resp => {
          if (resp.status === 200) {
            const clone = resp.clone();
            caches.open(PAGES_CACHE).then(c => c.put(request, clone));
          }
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }
});