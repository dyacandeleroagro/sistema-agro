import streamlit as st
import pandas as pd
from database import get_conn


def pantalla_administracion():

    st.title("⚙️ Administración")

    conn = get_conn()

    # ==========================
    # LISTA DE USUARIOS
    # ==========================

    df = pd.read_sql("""
        SELECT id, usuario, nombre, rol
        FROM usuarios
        ORDER BY nombre
    """, conn)

    st.subheader("Usuarios")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ==========================
    # EDITAR USUARIO
    # ==========================

    st.subheader("Editar usuario")

    usuario_sel = st.selectbox(
        "Seleccionar usuario",
        df["usuario"]
    )

    datos = df[df["usuario"] == usuario_sel].iloc[0]

    nuevo_usuario = st.text_input(
        "Usuario",
        value=datos["usuario"]
    )

    nuevo_nombre = st.text_input(
        "Nombre",
        value=datos["nombre"]
    )

    st.subheader("Permisos")

    permisos = [
    "Administracion",
    "Clientes",
    "Facturacion",
    "Servicios",
    "Merch",
    "Ingresos",
    "Labores",
    "Analiticas",
    "Control",
    "Dueño"
]

permisos_usuario = pd.read_sql(
    "SELECT permiso FROM permisos WHERE usuario_id=%s",
    conn,
    params=(datos["id"],)
)["permiso"].tolist()

seleccionados = []

for permiso in permisos:

    if st.checkbox(
        permiso,
        value=permiso in permisos_usuario
    ):
        seleccionados.append(permiso)
    )

    nueva_password = st.text_input(
        "Nueva contraseña (opcional)",
        type="password"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button("💾 Guardar cambios"):

            cur = conn.cursor()

            if nueva_password:

                cur.execute("""
                    UPDATE usuarios
                    SET usuario=%s,
                        nombre=%s,
                        password=%s
                    WHERE id=%s
                """, (
                    nuevo_usuario,
                    nuevo_nombre,
                    nuevo_rol,
                    nueva_password,
                    datos["id"]
                ))

            else:

                cur.execute("""
                    UPDATE usuarios
                    SET usuario=%s,
                        nombre=%s,
                        rol=%s
                    WHERE id=%s
                """, (
                    nuevo_usuario,
                    nuevo_nombre,
                    nuevo_rol,
                    datos["id"]
                ))

            conn.commit()
            cur.execute(
    "DELETE FROM permisos WHERE usuario_id=%s",
    (datos["id"],)
)

for permiso in seleccionados:

    cur.execute(
        """
        INSERT INTO permisos(usuario_id, permiso)
        VALUES(%s,%s)
        """,
        (datos["id"], permiso)
    )

            st.success("✅ Usuario actualizado")

            st.rerun()

    with col2:

        if st.button("🗑 Eliminar usuario"):

            cur = conn.cursor()

            cur.execute(
                "DELETE FROM usuarios WHERE id=%s",
                (datos["id"],)
            )

            conn.commit()

            st.success("✅ Usuario eliminado")

            st.rerun()

    st.divider()

    # ==========================
    # NUEVO USUARIO
    # ==========================

    st.subheader("Crear nuevo usuario")

    with st.form("nuevo_usuario"):

        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        nombre = st.text_input("Nombre completo")

        rol = st.selectbox(
            "Rol",
            ["Operario", "Administrador", "Dueño"]
        )

        guardar = st.form_submit_button("Crear usuario")

        if guardar:

            cur = conn.cursor()

            cur.execute("""
                INSERT INTO usuarios
                (usuario, password, nombre, rol)
                VALUES (%s, %s, %s, %s)
            """, (
                usuario,
                password,
                nombre,
                rol
            ))

            conn.commit()

            st.success("✅ Usuario creado correctamente")

            st.rerun()