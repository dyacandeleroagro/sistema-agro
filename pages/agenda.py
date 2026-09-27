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
                "Estado",
                "Destinatarios"
            ]
        ).to_csv(
            ARCHIVO_AGENDA,
            index=False
        )

    df = pd.read_csv(
        ARCHIVO_AGENDA
    )

    # ==========================================
    # COMPATIBILIDAD CON EVENTOS ANTERIORES
    # ==========================================

    if "Destinatarios" not in df.columns:

        df["Destinatarios"] = ""

        df.to_csv(
            ARCHIVO_AGENDA,
            index=False
        )

    return df

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

            destinatarios = st.multiselect(
                "👥 ¿Quiénes deben recibir este aviso?",
                [
                    "Dueño",
                    "Administrador",
                    "Contador",
                    "Encargado",
                    "Operario",
                    "Maquinista"
                ],
                default=[]
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
                    estado,

                    "Destinatarios":
                    ", ".join(destinatarios)

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
                df["Fecha"],
                errors="coerce"
            )

            for idx, fila in df.sort_values(
                "Fecha"
            ).iterrows():

                st.divider()

                c1, c2 = st.columns(
                    [5, 1]
                )

                with c1:

                    st.write(
                        f"📅 **{fila['Fecha'].date()}**"
                    )

                    st.write(
                        f"### {fila['Título']}"
                    )

                    st.write(
                        f"**Tipo:** {fila['Tipo']}"
                    )

                    st.write(
                        f"**Descripción:** {fila['Descripción']}"
                    )

                    st.write(
                        f"**Responsable:** {fila['Responsable']}"
                    )

                    st.write(
                        f"**Estado:** {fila['Estado']}"
                    )

                    destinatarios_actuales = fila.get(
                        "Destinatarios",
                        ""
                    )

                    st.write(
                        f"**👥 Destinatarios:** "
                        f"{destinatarios_actuales}"
                    )

                with c2:

                    editar = st.button(
                        "✏️ Editar",
                        key=f"editar_evento_{fila['ID']}_{idx}"
                    )

                if editar:

                    st.session_state[
                        f"editando_evento_{fila['ID']}_{idx}"
                    ] = True

                if st.session_state.get(
                    f"editando_evento_{fila['ID']}_{idx}",
                    False
                ):

                    st.markdown(
                        "### ✏️ Editar evento"
                    )

                    fecha_actual = pd.to_datetime(
                        fila["Fecha"]
                    ).date()

                    tipos_evento = [
                        "🔧 Mantenimiento",
                        "🛡 Seguro",
                        "💰 Pago",
                        "👥 Reunión",
                        "🌾 Trabajo",
                        "📌 Otro"
                    ]

                    estados_evento = [
                        "🟡 Pendiente",
                        "🟢 Realizado",
                        "🔴 Cancelado"
                    ]

                    destinatarios_disponibles = [
                        "Dueño",
                        "Administrador",
                        "Contador",
                        "Encargado",
                        "Operario",
                        "Maquinista"
                    ]

                    destinatarios_guardados = str(
                        fila.get(
                            "Destinatarios",
                            ""
                        )
                    )

                    seleccionados = [
                        x.strip()
                        for x in destinatarios_guardados.split(",")
                        if x.strip()
                    ]

                    with st.form(
                        key=f"form_editar_evento_{fila['ID']}_{idx}"
                    ):

                        nueva_fecha = st.date_input(
                            "Fecha",
                            value=fecha_actual,
                            key=f"fecha_edit_{fila['ID']}_{idx}"
                        )

                        tipo_actual = str(
                            fila["Tipo"]
                        )

                        if tipo_actual not in tipos_evento:
                            tipo_actual = tipos_evento[0]

                        nuevo_tipo = st.selectbox(
                            "Tipo de evento",
                            tipos_evento,
                            index=tipos_evento.index(
                                tipo_actual
                            ),
                            key=f"tipo_edit_{fila['ID']}_{idx}"
                        )

                        nuevo_titulo = st.text_input(
                            "Título",
                            value=str(
                                fila["Título"]
                            ),
                            key=f"titulo_edit_{fila['ID']}_{idx}"
                        )

                        nueva_descripcion = st.text_area(
                            "Descripción",
                            value=str(
                                fila["Descripción"]
                            ),
                            key=f"descripcion_edit_{fila['ID']}_{idx}"
                        )

                        nuevo_responsable = st.text_input(
                            "Responsable",
                            value=str(
                                fila["Responsable"]
                            ),
                            key=f"responsable_edit_{fila['ID']}_{idx}"
                        )

                        estado_actual = str(
                            fila["Estado"]
                        )

                        if estado_actual not in estados_evento:
                            estado_actual = estados_evento[0]

                        nuevo_estado = st.selectbox(
                            "Estado",
                            estados_evento,
                            index=estados_evento.index(
                                estado_actual
                            ),
                            key=f"estado_edit_{fila['ID']}_{idx}"
                        )

                        nuevos_destinatarios = st.multiselect(
                            "👥 ¿Quiénes deben recibir este aviso?",
                            destinatarios_disponibles,
                            default=[
                                x
                                for x in seleccionados
                                if x in destinatarios_disponibles
                            ],
                            key=f"dest_edit_{fila['ID']}_{idx}"
                        )

                        guardar_cambios = st.form_submit_button(
                            "💾 Guardar cambios"
                        )

                        cancelar_edicion = st.form_submit_button(
                            "❌ Cancelar"
                        )

                    if guardar_cambios:

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Fecha"
                        ] = nueva_fecha.strftime(
                            "%Y-%m-%d"
                        )

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Tipo"
                        ] = nuevo_tipo

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Título"
                        ] = nuevo_titulo

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Descripción"
                        ] = nueva_descripcion

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Responsable"
                        ] = nuevo_responsable

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Estado"
                        ] = nuevo_estado

                        df.loc[
                            df["ID"].astype(str)
                            == str(fila["ID"]),
                            "Destinatarios"
                        ] = ", ".join(
                            nuevos_destinatarios
                        )

                        df.to_csv(
                            ARCHIVO_AGENDA,
                            index=False
                        )

                        st.success(
                            "✅ Evento actualizado correctamente."
                        )

                        st.session_state[
                            f"editando_evento_{fila['ID']}_{idx}"
                        ] = False

                        st.rerun()

                    if cancelar_edicion:

                        st.session_state[
                            f"editando_evento_{fila['ID']}_{idx}"
                        ] = False

                        st.rerun()

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