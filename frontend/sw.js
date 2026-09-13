// Service Worker placeholder
// This file prevents 404 errors when the browser requests it
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', () => {
  self.clients.claim();
});
