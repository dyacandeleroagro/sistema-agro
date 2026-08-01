import streamlit as st
import pandas as pd
from datetime import datetime, date
import os


ARCHIVO_AGENDA = "agenda.csv"


def cargar_agenda():

    if not os.path.exists(ARCHIVO_AGENDA):

        pd.DataFrame(
            columns=[
                "ID",
                "Fecha",
                "Tipo",
                "Título",
                "Descripción",
                "Responsable",
                "Estado"
            ]
        ).to_csv(
            ARCHIVO_AGENDA,
            index=False
        )


    return pd.read_csv(
        ARCHIVO_AGENDA
    )



def pantalla_agenda():

    st.header("📅 Agenda y Vencimientos")


    df = cargar_agenda()


    tab1, tab2, tab3 = st.tabs(
        [
            "➕ Nuevo evento",
            "📋 Agenda completa",
            "🔔 Próximos eventos"
        ]
    )


    # ==========================
    # NUEVO EVENTO
    # ==========================

    with tab1:

        st.subheader(
            "Crear nuevo evento"
        )


        with st.form("form_agenda"):

            fecha = st.date_input(
                "Fecha",
                value=datetime.today()
            )


            tipo = st.selectbox(
                "Tipo de evento",
                [
                    "🔧 Mantenimiento",
                    "🛡 Seguro",
                    "💰 Pago",
                    "👥 Reunión",
                    "🌾 Trabajo",
                    "📌 Otro"
                ]
            )


            titulo = st.text_input(
                "Título"
            )


            descripcion = st.text_area(
                "Descripción"
            )


            responsable = st.text_input(
                "Responsable"
            )


            estado = st.selectbox(
                "Estado",
                [
                    "🟡 Pendiente",
                    "🟢 Realizado",
                    "🔴 Cancelado"
                ]
            )


            guardar = st.form_submit_button(
                "💾 Guardar evento"
            )


            if guardar and titulo:


                nuevo = {

                    "ID":
                    int(datetime.now().timestamp()),

                    "Fecha":
                    fecha.strftime("%Y-%m-%d"),

                    "Tipo":
                    tipo,

                    "Título":
                    titulo,

                    "Descripción":
                    descripcion,

                    "Responsable":
                    responsable,

                    "Estado":
                    estado

                }


                df = pd.concat(
                    [
                        df,
                        pd.DataFrame([nuevo])
                    ],
                    ignore_index=True
                )


                df.to_csv(
                    ARCHIVO_AGENDA,
                    index=False
                )


                st.success(
                    "Evento creado correctamente"
                )

                st.rerun()



    # ==========================
    # AGENDA COMPLETA
    # ==========================

    with tab2:

        st.subheader(
            "Todos los eventos"
        )


        if not df.empty:

            df["Fecha"] = pd.to_datetime(
                df["Fecha"]
            )


            st.dataframe(
                df.sort_values("Fecha"),
                use_container_width=True
            )


        else:

            st.info(
                "No hay eventos cargados"
            )



    # ==========================
    # PROXIMOS
    # ==========================

    with tab3:

        st.subheader(
            "🔔 Próximos vencimientos"
        )


        if not df.empty:


            hoy = pd.Timestamp.today()


            proximos = df[
                pd.to_datetime(df["Fecha"]) >= hoy
            ]


            proximos = proximos.sort_values(
                "Fecha"
            )


            if not proximos.empty:


                for _, fila in proximos.iterrows():

                    dias = (
                        pd.to_datetime(
                            fila["Fecha"]
                        )
                        -
                        hoy
                    ).days


                    st.warning(
                        f"""
                        📅 {fila['Fecha'].date()}
                        
                        **{fila['Título']}**
                        
                        Tipo: {fila['Tipo']}
                        
                        Responsable: {fila['Responsable']}
                        
                        Faltan {dias} días
                        """
                    )


            else:

                st.success(
                    "No hay próximos eventos"
                )


        else:

            st.info(
                "No hay eventos cargados"
            )