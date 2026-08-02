import os
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_conn


def pantalla_ingresos():

    st.header("💰 Ingresos por Trabajos")

    conn = get_conn()


    # ==========================
    # CREAR INGRESO
    # ==========================

    st.subheader("➕ Nuevo ingreso")

    with st.form("form_ingreso"):

        col1, col2 = st.columns(2)

        with col1:

            fecha = st.date_input(
                "Fecha",
                datetime.today()
            )

            cliente = st.text_input(
                "Cliente"
            )

            servicio = st.text_input(
                "Servicio realizado"
            )


        with col2:

            lote = st.text_input(
                "Campo / Establecimiento"
            )

            hectareas = st.number_input(
                "Hectáreas trabajadas",
                min_value=0.0
            )

            monto = st.number_input(
                "Monto cobrado ($)",
                min_value=0.0
            )


        detalle = st.text_area(
            "Detalle"
        )


        archivo = st.file_uploader(
            "Adjuntar comprobante",
            type=["pdf","png","jpg","jpeg"]
        )


        guardar = st.form_submit_button(
            "💾 Guardar ingreso"
        )


        if guardar:

    if cliente and monto > 0:

        nuevo_ingreso = {

            "ID": int(datetime.now().timestamp()),

            "Fecha": fecha.strftime("%Y-%m-%d"),

            "Cliente": cliente,

            "Tipo Servicio": servicio,

            "Lote/Establecimiento": lote,

            "Hectáreas": hectareas,

            "Monto Total (ARS)": monto,

            "Detalle": detalle
        }


        df = pd.concat(
            [
                df,
                pd.DataFrame([nuevo_ingreso])
            ],
            ignore_index=True
        )


        df.to_csv(
            "registro_ingresos.csv",
            index=False
        )


        st.success(
            "✅ Ingreso guardado correctamente"
        )

        st.rerun()


    else:

        st.warning(
            "Complete cliente y monto"
        )



    st.divider()


    # ==========================
    # LISTADO
    # ==========================

    st.subheader(
        "📋 Ingresos registrados"
    )


if not os.path.exists("registro_ingresos.csv"):
    pd.DataFrame(columns=[
        "ID",
        "Fecha",
        "Cliente",
        "Tipo Servicio",
        "Lote/Establecimiento",
        "Hectáreas",
        "Monto Total (ARS)",
        "Detalle"
    ]).to_csv("registro_ingresos.csv", index=False)


df = pd.read_csv("registro_ingresos.csv")



if not df.empty:

        st.dataframe(
            df,
            use_container_width=True
        )

    else:

        st.info(
            "No hay ingresos cargados"
        )


    conn.close()