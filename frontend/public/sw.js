self.addEventListener('push', event => {
    if (!event.data) return;
    const { title, body } = event.data.json();
    event.waitUntil(
        self.registration.showNotification(title, {
            body,
            icon: '/favicon.svg',
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            for (const client of windowClients) {
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            return clients.openWindow('/');
        })
    );
});
