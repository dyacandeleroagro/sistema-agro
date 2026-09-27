import streamlit.components.v1 as components


def activar_pwa():

    components.html(
        """
        <script>

        // ==================================================
        // REGISTRAR SERVICE WORKER
        // ==================================================

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
                    "D&A Agro - Error Service Worker:",
                    error
                );

            });

        }

        </script>
        """,
        height=0
    )