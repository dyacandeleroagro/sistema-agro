import streamlit as st
import pandas as pd
from datetime import datetime
import os

from database import get_conn
from notificaciones import crear_notificacion


ARCHIVO_AGENDA = "agenda.csv"


# ==========================================================
# ROLES
# ==========================================================

def obtener_roles_usuario():

    rol = st.session_state.get(
        "rol",
        ""
    )

    if not rol:

        rol = st.session_state.get(
            "rol_actual",
            ""
        )

    return [
        x.strip()
        for x in str(rol).split(",")
        if x.strip()
    ]


def puede_administrar_agenda():

    roles = obtener_roles_usuario()

    return any(
        rol in roles
        for rol in [
            "Dueño",
            "Administrador",
            "Encargado"
        ]
    )


# ==========================================================
# CARGAR AGENDA DESDE NEON
# ==========================================================

def cargar_agenda_desde_neon():

    conn = None

    try:

        conn = get_conn()

        query = """
            SELECT
                id_evento,
                fecha,
                tipo,
                titulo,
                descripcion,
                responsable,
                estado,
                destinatarios
            FROM agenda
            ORDER BY fecha, id
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        conn.close()

        if df.empty:

            return pd.DataFrame()

        df = df.rename(
            columns={
                "id_evento": "ID",
                "fecha": "Fecha",
                "tipo": "Tipo",
                "titulo": "Título",
                "descripcion": "Descripción",
                "responsable": "Responsable",
                "estado": "Estado",
                "destinatarios": "Destinatarios"
            }
        )

        return df

    except Exception as e:

        if conn:
            conn.close()

        st.error(
            f"❌ No se pudo cargar la Agenda desde Neon: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# MIGRAR AGENDA CSV A NEON
# ==========================================================

def migrar_agenda_csv_a_neon():

    if not os.path.exists(
        ARCHIVO_AGENDA
    ):

        return

    try:

        df_csv = pd.read_csv(
            ARCHIVO_AGENDA,
            encoding="utf-8-sig"
        )

    except Exception:

        return

    if df_csv.empty:

        return

    if "Destinatarios" not in df_csv.columns:

        df_csv["Destinatarios"] = ""

    conn = None
    cursor = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        for _, fila in df_csv.iterrows():

            id_evento = str(
                fila.get(
                    "ID",
                    ""
                )
            )

            if not id_evento:

                continue

            cursor.execute(
                """
                INSERT INTO agenda (
                    id_evento,
                    fecha,
                    tipo,
                    titulo,
                    descripcion,
                    responsable,
                    estado,
                    destinatarios
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (id_evento)
                DO NOTHING
                """,
                (
                    id_evento,
                    fila.get("Fecha") or None,
                    fila.get("Tipo", ""),
                    fila.get("Título", ""),
                    fila.get("Descripción", ""),
                    fila.get("Responsable", ""),
                    fila.get("Estado", ""),
                    fila.get("Destinatarios", "")
                )
            )

        conn.commit()

    except Exception as e:

        if conn:
            conn.rollback()

        st.warning(
            f"⚠️ No se pudo migrar la Agenda anterior: {e}"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ==========================================================
# CARGAR AGENDA
# ==========================================================

def cargar_agenda():

    df = cargar_agenda_desde_neon()

    # Si Neon está vacío, intentamos pasar
    # la agenda anterior a Neon.
    if df.empty:

        migrar_agenda_csv_a_neon()

        df = cargar_agenda_desde_neon()

    return df


# ==========================================================
# GUARDAR EVENTO EN NEON
# ==========================================================

def guardar_evento_en_neon(evento):

    conn = None
    cursor = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO agenda (
                id_evento,
                fecha,
                tipo,
                titulo,
                descripcion,
                responsable,
                estado,
                destinatarios
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (id_evento)
            DO UPDATE SET
                fecha = EXCLUDED.fecha,
                tipo = EXCLUDED.tipo,
                titulo = EXCLUDED.titulo,
                descripcion = EXCLUDED.descripcion,
                responsable = EXCLUDED.responsable,
                estado = EXCLUDED.estado,
                destinatarios = EXCLUDED.destinatarios
            """,
            (
                str(evento["ID"]),
                evento["Fecha"],
                evento["Tipo"],
                evento["Título"],
                evento["Descripción"],
                evento["Responsable"],
                evento["Estado"],
                evento["Destinatarios"]
            )
        )

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        st.error(
            f"❌ No se pudo guardar el evento en Neon: {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ==========================================================
# ELIMINAR EVENTO DE NEON
# ==========================================================

def eliminar_evento_de_neon(id_evento):

    conn = None
    cursor = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM agenda
            WHERE id_evento = %s
            """,
            (
                str(id_evento),
            )
        )

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        st.error(
            f"❌ No se pudo eliminar el evento de Neon: {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ==========================================================
# EVENTO CORRESPONDE AL USUARIO
# ==========================================================

def evento_corresponde_al_usuario(
    fila
):

    # Los administradores pueden ver todo.
    if puede_administrar_agenda():

        return True

    destinatarios = str(
        fila.get(
            "Destinatarios",
            ""
        )
    ).strip()

    # Sin destinatarios = visible para todos.
    if not destinatarios:

        return True

    lista_destinatarios = [
        x.strip()
        for x in destinatarios.split(",")
        if x.strip()
    ]

    if "Todos" in lista_destinatarios:

        return True

    roles_usuario = obtener_roles_usuario()

    return any(
        rol in lista_destinatarios
        for rol in roles_usuario
    )


# ==========================================================
# PANTALLA AGENDA
# ==========================================================

def pantalla_agenda():

    st.header(
        "📅 Agenda y Vencimientos"
    )

    df = cargar_agenda()

    puede_editar = puede_administrar_agenda()

    # ======================================================
    # PESTAÑAS
    # ======================================================

    if puede_editar:

        tab1, tab2, tab3 = st.tabs(
            [
                "➕ Nuevo evento",
                "📋 Agenda completa",
                "🔔 Próximos eventos"
            ]
        )

    else:

        tab1 = None

        tab2, tab3 = st.tabs(
            [
                "📋 Agenda",
                "🔔 Próximos eventos"
            ]
        )

    # ======================================================
    # NUEVO EVENTO
    # ======================================================

    if puede_editar:

        with tab1:

            st.subheader(
                "Crear nuevo evento"
            )

            with st.form(
                "form_agenda"
            ):

                fecha = st.date_input(
                    "Fecha",
                    value=datetime.today().date()
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
                    ]
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

            if guardar:

                if not titulo.strip():

                    st.warning(
                        "⚠️ Escribí un título para el evento."
                    )

                else:

                    id_evento = str(
                        int(
                            datetime.now().timestamp() * 1000
                        )
                    )

                    nuevo = {

                        "ID":
                        id_evento,

                        "Fecha":
                        fecha.strftime(
                            "%Y-%m-%d"
                        ),

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
                        ", ".join(
                            destinatarios
                        )
                    }

                    guardado = guardar_evento_en_neon(
                        nuevo
                    )

                    if guardado:

                        # También mantenemos el CSV
                        # como respaldo local.
                        df_actual = cargar_agenda_desde_neon()

                        df_actual.to_csv(
                            ARCHIVO_AGENDA,
                            index=False,
                            encoding="utf-8-sig"
                        )

                        # Crear notificación
                        destinatarios_notificacion = (
                            destinatarios
                        )

                        if not destinatarios_notificacion:

                            destinatarios_notificacion = [
                                "Todos"
                            ]

                        crear_notificacion(
                            titulo=f"📅 {titulo}",
                            mensaje=(
                                f"Se creó un nuevo evento "
                                f"para el día "
                                f"{fecha.strftime('%d/%m/%Y')}.\n\n"
                                f"Tipo: {tipo}\n\n"
                                f"Responsable: "
                                f"{responsable}\n\n"
                                f"{descripcion}"
                            ),
                            tipo="Agenda",
                            destinatarios=(
                                destinatarios_notificacion
                            )
                        )

                        st.success(
                            "✅ Evento guardado correctamente en Neon."
                        )

                        st.rerun()

    # ======================================================
    # AGENDA COMPLETA
    # ======================================================

    with tab2:

        st.subheader(
            "Todos los eventos"
        )

        if not df.empty:

            df["Fecha"] = pd.to_datetime(
                df["Fecha"],
                errors="coerce"
            )

            df_visible = df[
                df.apply(
                    evento_corresponde_al_usuario,
                    axis=1
                )
            ].copy()

            if df_visible.empty:

                st.info(
                    "No hay eventos asignados a tu usuario."
                )

            else:

                for idx, fila in df_visible.sort_values(
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
                            f"**Descripción:** "
                            f"{fila['Descripción']}"
                        )

                        st.write(
                            f"**Responsable:** "
                            f"{fila['Responsable']}"
                        )

                        st.write(
                            f"**Estado:** "
                            f"{fila['Estado']}"
                        )

                        st.write(
                            f"**👥 Destinatarios:** "
                            f"{fila['Destinatarios']}"
                        )

                    # ======================================
                    # BOTONES SOLO PARA ADMINISTRADORES
                    # ======================================

                    if puede_editar:

                        with c2:

                            editar = st.button(
                                "✏️ Editar",
                                key=(
                                    f"editar_evento_"
                                    f"{fila['ID']}_{idx}"
                                )
                            )

                            eliminar = st.button(
                                "🗑 Eliminar",
                                key=(
                                    f"eliminar_evento_"
                                    f"{fila['ID']}_{idx}"
                                )
                            )

                        # ==================================
                        # ELIMINAR
                        # ==================================

                        if eliminar:

                            eliminado = (
                                eliminar_evento_de_neon(
                                    fila["ID"]
                                )
                            )

                            if eliminado:

                                df_actual = (
                                    cargar_agenda_desde_neon()
                                )

                                df_actual.to_csv(
                                    ARCHIVO_AGENDA,
                                    index=False,
                                    encoding="utf-8-sig"
                                )

                                st.success(
                                    "🗑️ Evento eliminado correctamente."
                                )

                                st.rerun()

                        # ==================================
                        # EDITAR
                        # ==================================

                        if editar:

                            st.session_state[
                                f"editando_evento_"
                                f"{fila['ID']}_{idx}"
                            ] = True

                    # ======================================
                    # FORMULARIO DE EDICIÓN
                    # ======================================

                    if puede_editar and st.session_state.get(
                        f"editando_evento_"
                        f"{fila['ID']}_{idx}",
                        False
                    ):

                        st.markdown(
                            "### ✏️ Editar evento"
                        )

                        fecha_actual = (
                            pd.to_datetime(
                                fila["Fecha"]
                            ).date()
                        )

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
                            for x in (
                                destinatarios_guardados
                                .split(",")
                            )
                            if x.strip()
                        ]

                        with st.form(
                            key=(
                                f"form_editar_evento_"
                                f"{fila['ID']}_{idx}"
                            )
                        ):

                            nueva_fecha = st.date_input(
                                "Fecha",
                                value=fecha_actual
                            )

                            tipo_actual = str(
                                fila["Tipo"]
                            )

                            if tipo_actual not in tipos_evento:

                                tipo_actual = (
                                    tipos_evento[0]
                                )

                            nuevo_tipo = st.selectbox(
                                "Tipo de evento",
                                tipos_evento,
                                index=tipos_evento.index(
                                    tipo_actual
                                )
                            )

                            nuevo_titulo = st.text_input(
                                "Título",
                                value=str(
                                    fila["Título"]
                                )
                            )

                            nueva_descripcion = st.text_area(
                                "Descripción",
                                value=str(
                                    fila["Descripción"]
                                )
                            )

                            nuevo_responsable = st.text_input(
                                "Responsable",
                                value=str(
                                    fila["Responsable"]
                                )
                            )

                            estado_actual = str(
                                fila["Estado"]
                            )

                            if estado_actual not in estados_evento:

                                estado_actual = (
                                    estados_evento[0]
                                )

                            nuevo_estado = st.selectbox(
                                "Estado",
                                estados_evento,
                                index=estados_evento.index(
                                    estado_actual
                                )
                            )

                            nuevos_destinatarios = (
                                st.multiselect(
                                    "👥 ¿Quiénes deben "
                                    "recibir este aviso?",
                                    destinatarios_disponibles,
                                    default=[
                                        x
                                        for x in seleccionados
                                        if x in (
                                            destinatarios_disponibles
                                        )
                                    ]
                                )
                            )

                            guardar_cambios = (
                                st.form_submit_button(
                                    "💾 Guardar cambios"
                                )
                            )

                            cancelar_edicion = (
                                st.form_submit_button(
                                    "❌ Cancelar"
                                )
                            )

                        if guardar_cambios:

                            evento_editado = {

                                "ID":
                                str(fila["ID"]),

                                "Fecha":
                                nueva_fecha.strftime(
                                    "%Y-%m-%d"
                                ),

                                "Tipo":
                                nuevo_tipo,

                                "Título":
                                nuevo_titulo,

                                "Descripción":
                                nueva_descripcion,

                                "Responsable":
                                nuevo_responsable,

                                "Estado":
                                nuevo_estado,

                                "Destinatarios":
                                ", ".join(
                                    nuevos_destinatarios
                                )
                            }

                            actualizado = (
                                guardar_evento_en_neon(
                                    evento_editado
                                )
                            )

                            if actualizado:

                                df_actual = (
                                    cargar_agenda_desde_neon()
                                )

                                df_actual.to_csv(
                                    ARCHIVO_AGENDA,
                                    index=False,
                                    encoding="utf-8-sig"
                                )

                                st.success(
                                    "✅ Evento actualizado correctamente en Neon."
                                )

                                st.session_state[
                                    f"editando_evento_"
                                    f"{fila['ID']}_{idx}"
                                ] = False

                                st.rerun()

                        if cancelar_edicion:

                            st.session_state[
                                f"editando_evento_"
                                f"{fila['ID']}_{idx}"
                            ] = False

                            st.rerun()

        else:

            st.info(
                "No hay eventos cargados."
            )

    # ======================================================
    # PRÓXIMOS EVENTOS
    # ======================================================

    with tab3:

        st.subheader(
            "🔔 Próximos vencimientos"
        )

        if not df.empty:

            df["Fecha"] = pd.to_datetime(
                df["Fecha"],
                errors="coerce"
            )

            df_visible = df[
                df.apply(
                    evento_corresponde_al_usuario,
                    axis=1
                )
            ].copy()

            hoy = pd.Timestamp.today().normalize()

            proximos = df_visible[
                df_visible["Fecha"] >= hoy
            ].sort_values(
                "Fecha"
            )

            if not proximos.empty:

                for _, fila in proximos.iterrows():

                    dias = (
                        fila["Fecha"] - hoy
                    ).days

                    st.warning(
                        f"""
📅 {fila['Fecha'].date()}

**{fila['Título']}**

Tipo: {fila['Tipo']}

Responsable: {fila['Responsable']}

Estado: {fila['Estado']}

Faltan {dias} días
"""
                    )

            else:

                st.success(
                    "No hay próximos eventos."
                )

        else:

            st.info(
                "No hay eventos cargados."
            )