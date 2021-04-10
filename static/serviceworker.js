self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('dynamic').then((cache) => {
            return cache.addAll([
                '/static/chat.css',
                '/static/chat.html',
                '/static/chat.js',
                '/static/chat.webmanifest',
                '/static/jnet.svg',
            ]);
        }),
    );
});

self.addEventListener('fetch', (event) =>
    event.respondWith((async () => {
        const cache = await caches.open('dynamic');
        try {
            const network = await fetch(event.request);
            console.log(await network.clone().text())
            await cache.put(event.request, network.clone());
            return network;
        } catch (e) {
            console.info(`[sw] Recovering ${event.request.url} from cache.`);
            return cache.match(event.request)
        }
    })()
    ));
