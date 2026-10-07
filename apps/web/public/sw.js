/*
 * Service worker de Snacki (J11, ADR 0016) : l'app s'installe et reste propre sans réseau.
 *
 * Règle de sécurité : AUCUNE page ni réponse d'API n'est mise en cache. Seuls les fichiers
 * publics et immuables (scripts et styles versionnés, images, polices, icônes) le sont. Ainsi
 * aucune commande, aucun numéro de client ni écran de la caisse ne reste sur le téléphone.
 * Sans réseau, une navigation affiche la page « hors connexion ».
 */
const CACHE = "snacki-static-v1";
const OFFLINE = "/offline.html";
const PRECACHE = [OFFLINE, "/offline.css", "/icons/icon-192.png"];
const STATIC = /^\/(_next\/static|img|icons|fonts)\//;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    // Toujours le réseau ; la page hors connexion seulement s'il ne répond pas.
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (STATIC.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            if (response.ok && response.type === "basic") {
              const copy = response.clone();
              caches.open(CACHE).then((c) => c.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
  // Tout le reste (pages, /api/…) : réseau direct, jamais mis en cache.
});
