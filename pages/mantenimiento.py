import streamlit as st
import pandas as pd
from datetime import datetime
import os


ARCHIVO_MAQUINAS = "maquinas.csv"
ARCHIVO_MANTENIMIENTO = "mantenimientos.csv"


def cargar_datos():

    if not os.path.exists(ARCHIVO_MAQUINAS):
        pd.DataFrame(
            columns=[
                "ID",
                "Máquina",
                "Marca",
                "Modelo",
                "Año",
                "Horas Actuales",
                "Estado"
            ]
        ).to_csv(
            ARCHIVO_MAQUINAS,
            index=False
        )


    if not os.path.exists(ARCHIVO_MANTENIMIENTO):
        pd.DataFrame(
            columns=[
                "ID",
                "Fecha",
                "Máquina",
                "Tipo",
                "Horas Máquina",
                "Descripción",
                "Proveedor",
                "Costo"
            ]
        ).to_csv(
            ARCHIVO_MANTENIMIENTO,
            index=False
        )


    maquinas = pd.read_csv(ARCHIVO_MAQUINAS)
    mantenimientos = pd.read_csv(ARCHIVO_MANTENIMIENTO)

    return maquinas, mantenimientos



def pantalla_mantenimiento():

    st.header("🔧 Mantenimiento de Maquinaria")


    maquinas, mantenimientos = cargar_datos()


    tab1, tab2 = st.tabs(
        [
            "🚜 Máquinas",
            "🛠 Historial de mantenimiento"
        ]
    )


    # ==========================
    # TAB MÁQUINAS
    # ==========================

    with tab1:

        st.subheader("Agregar maquinaria")


        with st.form("nueva_maquina"):

            nombre = st.text_input(
                "Nombre de la máquina"
            )

            marca = st.text_input(
                "Marca"
            )

            modelo = st.text_input(
                "Modelo"
            )

            año = st.number_input(
                "Año",
                min_value=1900,
                max_value=2100,
                value=2026
            )

            horas = st.number_input(
                "Horas actuales",
                min_value=0.0
            )


            estado = st.selectbox(
                "Estado",
                [
                    "🟢 Operativa",
                    "🟡 Revisión próxima",
                    "🔴 Fuera de servicio"
                ]
            )


            guardar = st.form_submit_button(
                "💾 Guardar máquina"
            )


            if guardar and nombre:

                nueva = {
                    "ID": int(datetime.now().timestamp()),
                    "Máquina": nombre,
                    "Marca": marca,
                    "Modelo": modelo,
                    "Año": año,
                    "Horas Actuales": horas,
                    "Estado": estado
                }


                maquinas = pd.concat(
                    [
                        maquinas,
                        pd.DataFrame([nueva])
                    ],
                    ignore_index=True
                )


                maquinas.to_csv(
                    ARCHIVO_MAQUINAS,
                    index=False
                )


                st.success(
                    "Máquina registrada"
                )

                st.rerun()



        if not maquinas.empty:

            st.dataframe(
                maquinas,
                use_container_width=True
            )



    # ==========================
    # TAB MANTENIMIENTO
    # ==========================

    with tab2:

        st.subheader(
            "Registrar mantenimiento"
        )


        if maquinas.empty:

            st.warning(
                "Primero cargá una máquina"
            )

        else:


            with st.form("nuevo_mantenimiento"):


                maquina = st.selectbox(
                    "Máquina",
                    maquinas["Máquina"].tolist()
                )


                tipo = st.selectbox(
                    "Tipo",
                    [
                        "Service",
                        "Cambio de aceite",
                        "Cambio filtros",
                        "Reparación",
                        "Cubiertas",
                        "Otro"
                    ]
                )


                horas_m = st.number_input(
                    "Horas de máquina",
                    min_value=0.0
                )


                descripcion = st.text_area(
                    "Descripción"
                )


                proveedor = st.text_input(
                    "Taller / Proveedor"
                )


                costo = st.number_input(
                    "Costo ($)",
                    min_value=0.0
                )


                guardar_m = st.form_submit_button(
                    "💾 Guardar mantenimiento"
                )


                if guardar_m:


                    nuevo = {

                        "ID": int(datetime.now().timestamp()),

                        "Fecha":
                        datetime.now().strftime("%Y-%m-%d"),

                        "Máquina": maquina,

                        "Tipo": tipo,

                        "Horas Máquina": horas_m,

                        "Descripción": descripcion,

                        "Proveedor": proveedor,

                        "Costo": costo

                    }


                    mantenimientos = pd.concat(
                        [
                            mantenimientos,
                            pd.DataFrame([nuevo])
                        ],
                        ignore_index=True
                    )


                    mantenimientos.to_csv(
                        ARCHIVO_MANTENIMIENTO,
                        index=False
                    )


                    st.success(
                        "Mantenimiento guardado"
                    )

                    st.rerun()



        if not mantenimientos.empty:

            st.dataframe(
                mantenimientos,
                use_container_width=True
            )