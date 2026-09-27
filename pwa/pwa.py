import streamlit as st


VAPID_PUBLIC_KEY = st.secrets.get(
    "VAPID_PUBLIC_KEY",
    ""
)


PWA_COMPONENT = st.components.v2.component(
    name="da_candelero_agro_pwa",

    html="""
        <div id="pwa-status">
            📱 Preparando notificaciones...
        </div>
    """,

    js="""
        export default async function(component) {

            const {
                parentElement,
                setStateValue
            } = component;

            const publicKey =
                component.data.vapid_public_key;

            const estado =
                parentElement.querySelector(
                    "#pwa-status"
                );

            if (!document.querySelector(
                'link[rel="manifest"]'
            )) {

                const manifest =
                    document.createElement("link");

                manifest.rel = "manifest";

                manifest.href =
                    "/static/manifest.json";

                document.head.appendChild(
                    manifest
                );
            }


            async function prepararPWA() {

                try {

                    if (!(
                        "serviceWorker"
                        in navigator
                    )) {

                        estado.innerText =
                            "⚠️ Service Worker no disponible";

                        return;
                    }


                    const registration =
                        await navigator.serviceWorker.register(
                            "/static/service-worker.js"
                        );


                    console.log(
                        "D&A Agro - Service Worker registrado",
                        registration
                    );


                    if (!(
                        "PushManager"
                        in window
                    )) {

                        estado.innerText =
                            "⚠️ Push no disponible";

                        return;
                    }


                    const permiso =
                        await Notification.requestPermission();


                    if (permiso !== "granted") {

                        estado.innerText =
                            "🔕 Notificaciones no autorizadas";

                        return;
                    }


                    let subscription =
                        await registration
                            .pushManager
                            .getSubscription();


                    if (!subscription) {

                        if (!publicKey) {

                            estado.innerText =
                                "⚠️ Falta la clave VAPID";

                            return;
                        }


                        subscription =
                            await registration
                                .pushManager
                                .subscribe({
                                    userVisibleOnly: true,
                                    applicationServerKey:
                                        publicKey
                                });
                    }


                    const datos =
                        subscription.toJSON();


                    if (
                        datos &&
                        datos.endpoint &&
                        datos.keys &&
                        datos.keys.p256dh &&
                        datos.keys.auth
                    ) {

                        setStateValue(
                            "push_subscription",
                            {
                                endpoint:
                                    datos.endpoint,

                                p256dh:
                                    datos.keys.p256dh,

                                auth:
                                    datos.keys.auth
                            }
                        );


                        estado.innerText =
                            "🔔 Notificaciones activadas";


                        console.log(
                            "D&A Agro - Suscripción Push lista"
                        );
                    }

                } catch (error) {

                    console.error(
                        "D&A Agro - Error Push:",
                        error
                    );


                    estado.innerText =
                        "⚠️ Error Push: " +
                        (error?.message || error);
                }
            }


            prepararPWA();
        }
    """
)


def activar_pwa():

    PWA_COMPONENT(
        key="pwa_notificaciones",

        data={
            "vapid_public_key":
                VAPID_PUBLIC_KEY
        }
    )