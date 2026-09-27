import streamlit as st


PWA_COMPONENT = st.components.v2.component(
    name="da_candelero_agro_pwa",
    html="""
        <div id="pwa-status"></div>
    """,
    js="""
        export default function(component) {

            const { parentElement } = component;

            // Agregar manifest a la página
            if (!document.querySelector('link[rel="manifest"]')) {

                const manifest = document.createElement("link");

                manifest.rel = "manifest";
                manifest.href = "/app/static/manifest.json";

                document.head.appendChild(manifest);
            }

            // Registrar Service Worker
            if ("serviceWorker" in navigator) {

                navigator.serviceWorker.register(
                    "/app/static/service-worker.js"
                )
                .then(function(registration) {

                    console.log(
                        "D&A Agro - Service Worker registrado",
                        registration
                    );

                })
                .catch(function(error) {

                    console.error(
                        "D&A Agro - Error registrando Service Worker:",
                        error
                    );

                });
            }

            const estado =
                parentElement.querySelector("#pwa-status");

            if (estado) {

                estado.innerHTML =
                    "📱 Sistema Agro preparado para notificaciones";
            }
        }
    """
)


def activar_pwa():

    PWA_COMPONENT()