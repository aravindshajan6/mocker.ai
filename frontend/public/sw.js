/* Mocker service worker.
 *
 * Two jobs:
 *   1. Web-push notifications (the daily nudge).
 *   2. Enough offline support to finish a quiz you have already started — aspirants study on
 *      patchy mobile data, and losing answers to a dropped connection is the worst failure here.
 *
 * Deliberately NOT offline: the whole 6,000-question bank. Syncing that is a freshness and storage
 * problem with no matching payoff.
 */

const VERSION = "v4";
const SHELL = `mocker-shell-${VERSION}`;
const STATIC = `mocker-static-${VERSION}`;
const DATA = `mocker-data-${VERSION}`;
const KEEP = [SHELL, STATIC, DATA];

const OFFLINE_URL = "/offline";
const SHELL_URLS = [OFFLINE_URL, "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"];

// API responses worth keeping so a started quiz survives a tunnel. Deliberately excludes
// /api/auth/me — serving a stale identity to whoever signs in next on a shared phone is worse
// than showing them a loading state.
const CACHEABLE_API = [/^\/api\/quiz\/[^/]+$/, /^\/api\/topics$/, /^\/api\/quiz\/daily$/];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("mocker-") && !KEEP.includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* ---------- offline answer queue ------------------------------------------------ */
const DB_NAME = "mocker-outbox";
const STORE = "answers";

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

const MAX_QUEUE_AGE_MS = 48 * 60 * 60 * 1000;

async function queueAnswer(url, body, owner) {
  const db = await openDb();
  await new Promise((res, rej) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add({ url, body, owner, at: Date.now() });
    tx.oncomplete = res;
    tx.onerror = () => rej(tx.error);
  });
}

async function flushQueue(owner) {
  const db = await openDb();
  const items = await new Promise((res, rej) => {
    const tx = db.transaction(STORE, "readonly");
    const r = tx.objectStore(STORE).getAll();
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  let flushed = 0;
  for (const item of items) {
    // Stale entries are dropped rather than retried forever on every page load.
    if (Date.now() - (item.at || 0) > MAX_QUEUE_AGE_MS) {
      await deleteQueued(item.id);
      continue;
    }
    // Only replay answers belonging to whoever is signed in now: a different account on the same
    // device must not inherit them (the server would reject it, but the entry would never clear).
    if (item.owner && owner && item.owner !== owner) continue;
    try {
      const resp = await fetch(item.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: item.body,
        credentials: "same-origin",
      });
      if (resp.ok || resp.status === 409) {
        await deleteQueued(item.id);
        flushed++;
      } else if (resp.status >= 400 && resp.status < 500) {
        await deleteQueued(item.id);   // wrong user, gone session, deleted quiz: never replayable
      }
    } catch {
      return; // still offline; try again on the next flush
    }
  }
  const clients = await self.clients.matchAll();
  if (flushed) clients.forEach((c) => c.postMessage({ type: "outbox-flushed", count: flushed }));
}

async function deleteQueued(id) {
  const db = await openDb();
  return new Promise((res) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = res;
  });
}

async function clearUserData() {
  await caches.delete(DATA);
  const db = await openDb();
  await new Promise((res) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).clear();
    tx.oncomplete = res;
  });
}

self.addEventListener("message", (e) => {
  const msg = e.data;
  if (msg === "skip-waiting") self.skipWaiting();
  // Sign-out: drop everything tied to the account that is leaving this device.
  if (msg === "clear-user-data") e.waitUntil(clearUserData());
  if (msg === "flush-outbox") e.waitUntil(flushQueue());
  if (msg && msg.type === "flush-outbox") e.waitUntil(flushQueue(msg.owner));
});

self.addEventListener("sync", (e) => {
  if (e.tag === "mocker-answers") e.waitUntil(flushQueue());
});

/* ---------- fetch strategies ---------------------------------------------------- */
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Answers posted while offline are queued and replayed rather than lost.
  if (request.method === "POST" && /^\/api\/quiz\/[^/]+\/answer$/.test(url.pathname)) {
    event.respondWith(
      (async () => {
        const clone = request.clone();
        try {
          return await fetch(request);
        } catch {
          await queueAnswer(url.pathname, await clone.text(), request.headers.get("X-Mocker-User") || null);
          return new Response(JSON.stringify({ queued: true }), {
            status: 202, headers: { "Content-Type": "application/json" },
          });
        }
      })()
    );
    return;
  }

  if (request.method !== "GET") return;

  // Immutable build assets: cache first, they never change under a given URL.
  if (url.pathname.startsWith("/_next/static/") || SHELL_URLS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((resp) => {
        const copy = resp.clone();
        caches.open(STATIC).then((c) => c.put(request, copy));
        return resp;
      }))
    );
    return;
  }

  // API reads: fresh when possible, last-known-good when not.
  if (url.pathname.startsWith("/api/")) {
    if (!CACHEABLE_API.some((re) => re.test(url.pathname))) return;
    event.respondWith(
      fetch(request)
        .then((resp) => {
          if (resp.ok) {
            const copy = resp.clone();
            caches.open(DATA).then((c) => c.put(request, copy));
          }
          return resp;
        })
        .catch(() => caches.match(request).then((hit) => hit || new Response(
          JSON.stringify({ detail: "You are offline and this hasn't been saved for offline use yet." }),
          { status: 503, headers: { "Content-Type": "application/json" } }
        )))
    );
    return;
  }

  // Page navigations: network first, falling back to the offline page.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL).then((hit) => hit || Response.error()))
    );
  }
});

/* ---------- push ---------------------------------------------------------------- */
self.addEventListener("push", (event) => {
  let data = { title: "Mocker", body: "Your daily questions are waiting.", url: "/" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch {
    /* a push with no JSON payload still shows the default nudge */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      tag: "mocker-daily",
      data: { url: data.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
