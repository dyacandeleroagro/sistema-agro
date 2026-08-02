import streamlit as st
import pandas as pd
import os
from datetime import datetime
st.write("ESTOY EJECUTANDO EL INGRESOS CSV NUEVO")


ARCHIVO = "registro_ingresos.csv"


def pantalla_ingresos():

    st.header("💰 Ingresos por Trabajos")


    if not os.path.exists(ARCHIVO):
        pd.DataFrame(columns=[
            "ID",
            "Fecha",
            "Cliente",
            "Servicio",
            "Lote",
            "Hectáreas",
            "Monto",
            "Detalle"
        ]).to_csv(
            ARCHIVO,
            index=False
        )


    df = pd.read_csv(ARCHIVO)


    st.subheader("➕ Nuevo ingreso")


    with st.form("nuevo_ingreso"):

        cliente = st.text_input("Cliente")
        servicio = st.text_input("Servicio")
        lote = st.text_input("Lote / Campo")
        hectareas = st.number_input(
            "Hectáreas",
            min_value=0.0
        )

        monto = st.number_input(
            "Monto",
            min_value=0.0
        )

        detalle = st.text_area(
            "Detalle"
        )


        guardar = st.form_submit_button(
            "💾 Guardar"
        )


    if guardar:

        nuevo = {
            "ID": int(datetime.now().timestamp()),
            "Fecha": datetime.today().strftime("%Y-%m-%d"),
            "Cliente": cliente,
            "Servicio": servicio,
            "Lote": lote,
            "Hectáreas": hectareas,
            "Monto": monto,
            "Detalle": detalle
        }


        df = pd.concat(
            [
                df,
                pd.DataFrame([nuevo])
            ],
            ignore_index=True
        )


        df.to_csv(
            ARCHIVO,
            index=False
        )


        st.success(
            "Ingreso guardado"
        )

        st.rerun()


    st.divider()

    st.subheader("📋 Ingresos registrados")


    if not df.empty:

        st.dataframe(
            df,
            use_container_width=True
        )

    else:

        st.info(
            "No hay ingresos cargados"
        )
    st.divider()