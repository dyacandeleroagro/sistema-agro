import streamlit as st
import pandas as pd
from database import get_conn


def pantalla_campanas():

    st.header("🌱 Campañas Agrícolas")

    conn = get_conn()

    # ==========================
    # NUEVA CAMPAÑA
    # ==========================

    st.subheader("➕ Nueva campaña")

    with st.form("form_campana"):

        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Campaña")
            cultivo = st.selectbox(
                "Cultivo",
                ["Soja", "Maíz", "Trigo", "Otro"]
            )
            hectareas = st.number_input(
                "Hectáreas",
                min_value=0.0
            )

        with col2:
            lotes = st.text_input("Lotes")
            estado = st.selectbox(
                "Estado",
                [
                    "Planificada",
                    "En curso",
                    "Finalizada"
                ]
            )

        guardar = st.form_submit_button("💾 Guardar")

        if guardar:

            if nombre.strip() != "":

                cur = conn.cursor()

                cur.execute(
                    """
                    INSERT INTO campanas
                    (nombre,cultivo,hectareas,lotes,estado)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (
                        nombre,
                        cultivo,
                        hectareas,
                        lotes,
                        estado
                    )
                )

                conn.commit()
                cur.close()

                st.success("Campaña creada correctamente")
                st.rerun()

            else:
                st.warning("Ingrese un nombre")

    st.divider()

    # ==========================
    # LISTADO
    # ==========================

    df = pd.read_sql(
        """
        SELECT *
        FROM campanas
        ORDER BY id DESC
        """,
        conn
    )

    st.subheader("📋 Campañas registradas")

    if df.empty:

        st.info("Todavía no hay campañas.")

        conn.close()
        return

    st.dataframe(df, use_container_width=True)

    st.divider()

    # ==========================
    # RESUMEN
    # ==========================

    st.subheader("📊 Resumen")

    campana = st.selectbox(
        "Seleccionar campaña",
        df["nombre"]
    )

    fila = df[df["nombre"] == campana].iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Cultivo", fila["cultivo"])

    with c2:
        st.metric("Hectáreas", fila["hectareas"])

    with c3:
        st.metric("Estado", fila["estado"])

    with c4:
        st.metric("Lotes", fila["lotes"])

    st.divider()

    # ==========================
    # EDITAR
    # ==========================

    st.subheader("✏️ Editar campaña")

    nombre_edit = st.text_input(
        "Nombre",
        value=fila["nombre"]
    )

    cultivos = [
        "Soja",
        "Maíz",
        "Trigo",
        "Otro"
    ]

    cultivo_edit = st.selectbox(
        "Cultivo",
        cultivos,
        index=cultivos.index(fila["cultivo"])
        if fila["cultivo"] in cultivos
        else 0
    )

    hectareas_edit = st.number_input(
        "Hectáreas",
        value=float(fila["hectareas"])
    )

    lotes_edit = st.text_input(
        "Lotes",
        value=fila["lotes"]
    )

    estados = [
        "Planificada",
        "En curso",
        "Finalizada"
    ]

    estado_edit = st.selectbox(
        "Estado",
        estados,
        index=estados.index(fila["estado"])
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "💾 Guardar cambios",
            key="guardar_campana"
        ):

            cur = conn.cursor()

            cur.execute(
                """
                UPDATE campanas
                SET
                    nombre=%s,
                    cultivo=%s,
                    hectareas=%s,
                    lotes=%s,
                    estado=%s
                WHERE id=%s
                """,
                (
                    nombre_edit,
                    cultivo_edit,
                    hectareas_edit,
                    lotes_edit,
                    estado_edit,
                    int(fila["id"])
                )
            )

            conn.commit()
            cur.close()

            st.success("Campaña actualizada")
            st.rerun()

    with col2:

        if st.button(
            "🗑 Eliminar campaña",
            key="eliminar_campana"
        ):

            cur = conn.cursor()

            cur.execute(
                "DELETE FROM campanas WHERE id=%s",
                (int(fila["id"]),)
            )

            conn.commit()
            cur.close()

            st.success("Campaña eliminada")
            st.rerun()

    conn.close()