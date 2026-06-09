self.addEventListener('push', event => {
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
    event.waitUntil(clients.openWindow('/'));
});
