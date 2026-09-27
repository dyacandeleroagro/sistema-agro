import streamlit as st
import pandas as pd
import os
from datetime import datetime


ARCHIVO_NOTIFICACIONES = "notificaciones.csv"


# ==========================================================
# CARGAR NOTIFICACIONES
# ==========================================================

def cargar_notificaciones():

    if not os.path.exists(ARCHIVO_NOTIFICACIONES):

        pd.DataFrame(
            columns=[
                "ID",
                "Fecha",
                "Título",
                "Mensaje",
                "Tipo",
                "Destinatarios",
                "Estado"
            ]
        ).to_csv(
            ARCHIVO_NOTIFICACIONES,
            index=False
        )

    df = pd.read_csv(
        ARCHIVO_NOTIFICACIONES
    )

    columnas = [
        "ID",
        "Fecha",
        "Título",
        "Mensaje",
        "Tipo",
        "Destinatarios",
        "Estado"
    ]

    for columna in columnas:

        if columna not in df.columns:

            df[columna] = ""

    return df


# ==========================================================
# CREAR NOTIFICACIÓN
# ==========================================================

def crear_notificacion(
    titulo,
    mensaje,
    tipo="General",
    destinatarios=None
):

    if destinatarios is None:

        destinatarios = []

    df = cargar_notificaciones()

    nuevo = {

        "ID":
        int(datetime.now().timestamp() * 1000),

        "Fecha":
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "Título":
        titulo,

        "Mensaje":
        mensaje,

        "Tipo":
        tipo,

        "Destinatarios":
        ", ".join(destinatarios),

        "Estado":
        "No leída"

    }

    df = pd.concat(
        [
            df,
            pd.DataFrame([nuevo])
        ],
        ignore_index=True
    )

    df.to_csv(
        ARCHIVO_NOTIFICACIONES,
        index=False
    )


# ==========================================================
# VERIFICAR SI LA NOTIFICACIÓN CORRESPONDE AL USUARIO
# ==========================================================

def notificacion_corresponde(
    fila,
    rol_usuario
):

    destinatarios = str(
        fila.get(
            "Destinatarios",
            ""
        )
    )

    # Si no hay destinatarios específicos,
    # la notificación es para todos
    if not destinatarios.strip():

        return True

    lista_destinatarios = [
        x.strip()
        for x in destinatarios.split(",")
        if x.strip()
    ]

    # Notificación para todos
    if "Todos" in lista_destinatarios:

        return True

    # El usuario puede tener uno o varios roles
    roles_usuario = [
        x.strip()
        for x in str(rol_usuario).split(",")
        if x.strip()
    ]

    # Si alguno de los roles del usuario
    # coincide con los destinatarios
    for rol in roles_usuario:

        if rol in lista_destinatarios:

            return True

    return False

    destinatarios = str(
        fila.get(
            "Destinatarios",
            ""
        )
    )

    if not destinatarios:

        return True

    lista = [
        x.strip()
        for x in destinatarios.split(",")
    ]

    if "Todos" in lista:

        return True

    if rol_usuario in lista:

        return True

    return False


# ==========================================================
# MOSTRAR NOTIFICACIONES
# ==========================================================

def mostrar_notificaciones():

    df = cargar_notificaciones()

    if df.empty:

        st.info(
            "🔔 No tenés notificaciones."
        )

        return

    rol_usuario = st.session_state.get(
        "rol",
        ""
    )

    if not rol_usuario:

        rol_usuario = st.session_state.get(
            "rol_actual",
            ""
        )

    df_usuario = df[
        df.apply(
            lambda fila:
            notificacion_corresponde(
                fila,
                rol_usuario
            ),
            axis=1
        )
    ].copy()

    if df_usuario.empty:

        st.info(
            "🔔 No tenés notificaciones."
        )

        return

    df_usuario = df_usuario.sort_values(
        "Fecha",
        ascending=False
    )

    for idx, fila in df_usuario.iterrows():

        estado = str(
            fila.get(
                "Estado",
                "No leída"
            )
        )

        if estado == "No leída":

            st.warning(
                f"🔔 **{fila['Título']}**\n\n"
                f"{fila['Mensaje']}\n\n"
                f"📅 {fila['Fecha']}"
            )

            if st.button(
                "✅ Marcar como leída",
                key=f"leer_notificacion_{fila['ID']}_{idx}"
            ):

                df.loc[
                    df["ID"].astype(str)
                    == str(fila["ID"]),
                    "Estado"
                ] = "Leída"

                df.to_csv(
                    ARCHIVO_NOTIFICACIONES,
                    index=False
                )

                st.rerun()

        else:

            with st.expander(
                f"🔔 {fila['Título']} — {fila['Fecha']}"
            ):

                st.write(
                    fila["Mensaje"]
                )


# ==========================================================
# CANTIDAD DE NOTIFICACIONES SIN LEER
# ==========================================================

def contar_notificaciones_no_leidas():

    df = cargar_notificaciones()

    if df.empty:

        return 0

    rol_usuario = st.session_state.get(
        "rol",
        ""
    )

    if not rol_usuario:

        rol_usuario = st.session_state.get(
            "rol_actual",
            ""
        )

    df_usuario = df[
        df.apply(
            lambda fila:
            notificacion_corresponde(
                fila,
                rol_usuario
            ),
            axis=1
        )
    ]

    return len(
        df_usuario[
            df_usuario["Estado"]
            == "No leída"
        ]
    )