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
            index=False,
            encoding="utf-8-sig"
        )

    df = pd.read_csv(
        ARCHIVO_NOTIFICACIONES,
        encoding="utf-8-sig"
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

    # Aseguramos que sea una lista
    if isinstance(destinatarios, str):

        destinatarios = [
            x.strip()
            for x in destinatarios.split(",")
            if x.strip()
        ]

    df = cargar_notificaciones()

    nuevo = {

        "ID":
        str(
            int(
                datetime.now().timestamp() * 1000
            )
        ),

        "Fecha":
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "Título":
        str(titulo),

        "Mensaje":
        str(mensaje),

        "Tipo":
        str(tipo),

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
        index=False,
        encoding="utf-8-sig"
    )

    return True


# ==========================================================
# VERIFICAR SI CORRESPONDE AL USUARIO
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
    ).strip()

    # ------------------------------------------------------
    # SIN DESTINATARIOS = PARA TODOS
    # ------------------------------------------------------

    if not destinatarios:

        return True

    # ------------------------------------------------------
    # DESTINATARIOS DE LA NOTIFICACIÓN
    # ------------------------------------------------------

    lista_destinatarios = [
        x.strip()
        for x in destinatarios.split(",")
        if x.strip()
    ]

    # ------------------------------------------------------
    # PARA TODOS
    # ------------------------------------------------------

    if "Todos" in lista_destinatarios:

        return True

    # ------------------------------------------------------
    # ROLES DEL USUARIO
    # ------------------------------------------------------

    roles_usuario = [
        x.strip()
        for x in str(rol_usuario).split(",")
        if x.strip()
    ]

    # ------------------------------------------------------
    # COMPROBAR COINCIDENCIA
    # ------------------------------------------------------

    for rol in roles_usuario:

        if rol in lista_destinatarios:

            return True

    return False


# ==========================================================
# OBTENER ROL DEL USUARIO
# ==========================================================

def obtener_rol_usuario():

    rol = st.session_state.get(
        "rol",
        ""
    )

    if not rol:

        rol = st.session_state.get(
            "rol_actual",
            ""
        )

    return str(rol).strip()


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

    rol_usuario = obtener_rol_usuario()

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

        # ==================================================
        # NO LEÍDA
        # ==================================================

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
                    index=False,
                    encoding="utf-8-sig"
                )

                st.rerun()

        # ==================================================
        # LEÍDA
        # ==================================================

        else:

            with st.expander(
                f"🔔 {fila['Título']} — {fila['Fecha']}"
            ):

                st.write(
                    fila["Mensaje"]
                )


# ==========================================================
# CONTAR NOTIFICACIONES SIN LEER
# ==========================================================

def contar_notificaciones_no_leidas():

    df = cargar_notificaciones()

    if df.empty:

        return 0

    rol_usuario = obtener_rol_usuario()

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

    if df_usuario.empty:

        return 0

    return len(
        df_usuario[
            df_usuario["Estado"].astype(str)
            == "No leída"
        ]
    )