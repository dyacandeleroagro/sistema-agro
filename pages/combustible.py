import streamlit as st
import pandas as pd
from datetime import datetime
import os


ARCHIVO_COMBUSTIBLE = "registro_combustible.csv"


def cargar_combustible():

    if not os.path.exists(ARCHIVO_COMBUSTIBLE):

        pd.DataFrame(
            columns=[
                "ID",
                "Fecha",
                "Máquina",
                "Proveedor",
                "Litros",
                "Precio Litro",
                "Total",
                "Responsable",
                "Observaciones"
            ]
        ).to_csv(
            ARCHIVO_COMBUSTIBLE,
            index=False
        )


    return pd.read_csv(
        ARCHIVO_COMBUSTIBLE
    )



def pantalla_combustible():

    st.header("⛽ Control de Combustible")


    df = cargar_combustible()


    tab1, tab2, tab3 = st.tabs(
        [
            "⛽ Nueva Carga",
            "📋 Historial",
            "📊 Estadísticas"
        ]
    )


    # =============================
    # NUEVA CARGA
    # =============================

    with tab1:

        st.subheader(
            "Registrar carga de combustible"
        )


        with st.form(
            "form_combustible"
        ):

            c1, c2 = st.columns(2)


            with c1:

                fecha = st.date_input(
                    "Fecha",
                    value=datetime.today()
                )

                maquina = st.selectbox(
                    "Máquina",
                    [
                        "Cosechadora CR 7.90",
                        "Tractor Valtra",
                        "Pulverizadora",
                        "Camión",
                        "Otro"
                    ]
                )


                proveedor = st.text_input(
                    "Proveedor"
                )


                responsable = st.text_input(
                    "Quién cargó"
                )


            with c2:

                litros = st.number_input(
                    "Litros",
                    min_value=0.0,
                    step=10.0
                )


                precio = st.number_input(
                    "Precio por litro",
                    min_value=0.0,
                    step=10.0
                )


                total = litros * precio


                st.info(
                    f"Total carga: $ {total:,.2f}"
                )


                observaciones = st.text_area(
                    "Observaciones"
                )


            guardar = st.form_submit_button(
                "💾 Guardar carga"
            )


            if guardar and litros > 0:


                nueva = {

                    "ID":
                    int(datetime.now().timestamp()),

                    "Fecha":
                    fecha.strftime("%Y-%m-%d"),

                    "Máquina":
                    maquina,

                    "Proveedor":
                    proveedor,

                    "Litros":
                    litros,

                    "Precio Litro":
                    precio,

                    "Total":
                    total,

                    "Responsable":
                    responsable,

                    "Observaciones":
                    observaciones

                }


                df = pd.concat(
                    [
                        df,
                        pd.DataFrame([nueva])
                    ],
                    ignore_index=True
                )


                df.to_csv(
                    ARCHIVO_COMBUSTIBLE,
                    index=False
                )


                st.success(
                    "Carga registrada correctamente"
                )

                st.rerun()



    # =============================
    # HISTORIAL
    # =============================

    with tab2:

        st.subheader(
            "Historial de cargas"
        )


        if not df.empty:

            st.dataframe(
                df,
                use_container_width=True
            )

        else:

            st.info(
                "No hay cargas registradas"
            )



    # =============================
    # ESTADISTICAS
    # =============================

    with tab3:

        st.subheader(
            "Consumo de combustible"
        )


        if not df.empty:


            total_litros = df["Litros"].sum()

            total_gasto = df["Total"].sum()


            col1, col2 = st.columns(2)


            with col1:

                st.metric(
                    "⛽ Litros consumidos",
                    f"{total_litros:,.0f} L"
                )


            with col2:

                st.metric(
                    "💰 Gasto total",
                    f"$ {total_gasto:,.2f}"
                )


            st.divider()


            resumen = (
                df
                .groupby("Máquina")
                [["Litros","Total"]]
                .sum()
                .reset_index()
            )


            st.subheader(
                "Consumo por máquina"
            )


            st.dataframe(
                resumen,
                use_container_width=True
            )


        else:

            st.info(
                "Todavía no hay datos"
            )