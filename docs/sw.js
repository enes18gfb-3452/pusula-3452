// Uygulama dosyalarını önbellekte tutar; veri dosyası her zaman önce ağdan istenir.
const SURUM = "pusula-v1";
const KABUK = ["./", "./index.html", "./manifest.webmanifest", "./icon-180.png", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SURUM).then((c) => c.addAll(KABUK)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== SURUM).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.endsWith(".enc.json")) {
    // önce ağ, ağ yoksa son kaydedilen veri
    e.respondWith(
      fetch(e.request).then((r) => {
        const kopya = r.clone();
        caches.open(SURUM).then((c) => c.put(url.pathname, kopya));
        return r;
      }).catch(() => caches.match(url.pathname))
    );
    return;
  }
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
