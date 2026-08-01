import streamlit as st
import pandas as pd
from database import get_conn
from datetime import datetime


def pantalla_campanas():

    st.header("🌱 Campañas Agrícolas")

    conn = get_conn()

    # ==========================
    # NUEVA CAMPAÑA
    # ==========================

    st.subheader("➕ Crear nueva campaña")

    with st.form("form_campana"):

        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input(
                "Campaña",
                placeholder="Ej: 2026/2027"
            )

            cultivo = st.selectbox(
                "Cultivo",
                [
                    "Soja",
                    "Maíz",
                    "Trigo",
                    "Otro"
                ]
            )

            hectareas = st.number_input(
                "Hectáreas",
                min_value=0.0,
                step=1.0
            )

        with col2:

            lotes = st.text_input(
                "Lotes involucrados"
            )

            estado = st.selectbox(
                "Estado",
                [
                    "Planificada",
                    "En curso",
                    "Finalizada"
                ]
            )


        guardar = st.form_submit_button(
            "💾 Guardar Campaña"
        )


        if guardar:

            if nombre:

                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO campanas
                    (
                        nombre,
                        cultivo,
                        hectareas,
                        lotes,
                        estado
                    )
                    VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    nombre,
                    cultivo,
                    hectareas,
                    lotes,
                    estado
                ))

                conn.commit()
                cur.close()

                st.success(
                    "✅ Campaña creada correctamente"
                )

                st.rerun()

            else:
                st.warning(
                    "Ingrese el nombre de la campaña"
                )


    st.divider()


    # ==========================
    # LISTADO
    # ==========================

    st.subheader("📋 Campañas registradas")


    df = pd.read_sql("""
        SELECT *
        FROM campanas
        ORDER BY id DESC
    """, conn)


    if not df.empty:

        st.dataframe(
            df,
            use_container_width=True
        )

    else:

        st.info(
            "Todavía no hay campañas cargadas"
        )


    conn.close()