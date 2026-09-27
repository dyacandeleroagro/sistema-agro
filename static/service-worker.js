self.addEventListener("install", function(event) {
    console.log("D&A Candelero Agro - Service Worker instalado");
    self.skipWaiting();
});

self.addEventListener("activate", function(event) {
    console.log("D&A Candelero Agro - Service Worker activo");
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", function(event) {

    let datos = {
        title: "D&A Candelero Agro",
        body: "Tenés una nueva notificación.",
        url: "/"
    };

    if (event.data) {
        try {
            datos = event.data.json();
        } catch (e) {
            datos.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(
            datos.title,
            {
                body: datos.body,
                icon: "/app/static/logo.png",
                badge: "/app/static/logo.png",
                data: datos.url || "/"
            }
        )
    );
});

self.addEventListener("notificationclick", function(event) {

    event.notification.close();

    event.waitUntil(
        clients.openWindow(
            event.notification.data || "/"
        )
    );
});