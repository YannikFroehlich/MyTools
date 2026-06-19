const CACHE_VERSION = "{{ cache_version|escapejs }}";
const APP_SHELL_CACHE = `${CACHE_VERSION}:app-shell`;
const RUNTIME_STATIC_CACHE = `${CACHE_VERSION}:runtime-static`;
const OFFLINE_URL = "{{ offline_url|escapejs }}";
const PRECACHE_URLS = {{ precache_urls_json|safe }};

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(APP_SHELL_CACHE)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    const expectedCaches = new Set([APP_SHELL_CACHE, RUNTIME_STATIC_CACHE]);

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => Promise.all(
                cacheNames
                    .filter((cacheName) => cacheName.startsWith("mytools-pwa-") && !expectedCaches.has(cacheName))
                    .map((cacheName) => caches.delete(cacheName))
            ))
            .then(() => self.clients.claim())
    );
});

function isSameOrigin(requestUrl) {
    return requestUrl.origin === self.location.origin;
}

function isStaticAsset(requestUrl) {
    return requestUrl.pathname.startsWith("/static/");
}

async function cacheStaticAsset(request) {
    const cache = await caches.open(RUNTIME_STATIC_CACHE);
    const cachedResponse = await cache.match(request);

    const networkFetch = fetch(request)
        .then((response) => {
            if (response && response.ok) {
                cache.put(request, response.clone());
            }
            return response;
        })
        .catch(() => cachedResponse);

    return cachedResponse || networkFetch;
}

async function navigationFallback(request) {
    try {
        return await fetch(request);
    } catch (error) {
        const cachedOfflinePage = await caches.match(OFFLINE_URL);
        return cachedOfflinePage || Response.error();
    }
}

self.addEventListener("fetch", (event) => {
    const { request } = event;

    if (request.method !== "GET") {
        return;
    }

    const requestUrl = new URL(request.url);

    if (!isSameOrigin(requestUrl)) {
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(navigationFallback(request));
        return;
    }

    if (isStaticAsset(requestUrl)) {
        event.respondWith(cacheStaticAsset(request));
    }
});
function normalizeNotificationUrl(url) {
    try {
        const parsedUrl = new URL(url || '/', self.location.origin);
        if (parsedUrl.origin === self.location.origin) {
            return parsedUrl.href;
        }
    } catch (error) {
    }
    return new URL('/', self.location.origin).href;
}

self.addEventListener('push', (event) => {
    let payload = {};
    try {
        payload = event.data ? event.data.json() : {};
    } catch (error) {
        payload = { body: event.data ? event.data.text() : '' };
    }

    const title = payload.title || 'MyTools';
    const options = {
        body: payload.body || 'Du hast eine neue Benachrichtigung.',
        icon: payload.icon || '/static/app/icons/pwa-icon-192.png',
        badge: payload.badge || '/static/app/icons/pwa-icon-180.png',
        tag: payload.tag || 'mytools-notification',
        data: {
            url: normalizeNotificationUrl(payload.url || '/'),
        },
        vibrate: [80, 40, 80],
        timestamp: Date.now(),
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const targetUrl = normalizeNotificationUrl(event.notification.data && event.notification.data.url);

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url === targetUrl && 'focus' in client) {
                    return client.focus();
                }
            }

            if (self.clients.openWindow) {
                return self.clients.openWindow(targetUrl);
            }
            return undefined;
        })
    );
});

