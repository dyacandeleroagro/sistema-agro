import streamlit as st
import pandas as pd
from database import get_conn


def pantalla_administracion():

    st.title("⚙️ Administración")

    conn = get_conn()

    ROLES_DISPONIBLES = [
        "Dueño",
        "Administrador",
        "Contador",
        "Encargado",
        "Operario",
        "Maquinista",
        "Deshabilitado"
    ]

    # ==========================
    # LISTA USUARIOS
    # ==========================

    df = pd.read_sql("""
        SELECT id, usuario, nombre, rol
        FROM usuarios
        ORDER BY nombre
    """, conn)

    st.subheader("Usuarios")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

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

    nueva_password = st.text_input(
        "Nueva contraseña (opcional)",
        type="password"
    )


    roles_actuales = []

    if pd.notna(datos["rol"]):
        roles_actuales = [
            r.strip()
            for r in str(datos["rol"]).split(",")
        ]


    nuevo_rol = st.multiselect(
        "Roles",
        ROLES_DISPONIBLES,
        default=roles_actuales
    )


    col1, col2 = st.columns(2)


    with col1:

        if st.button("💾 Guardar cambios"):

            cur = conn.cursor()

            try:

                roles_texto = ",".join(nuevo_rol)

                if nueva_password:

                    cur.execute("""
                        UPDATE usuarios
                        SET usuario=%s,
                            nombre=%s,
                            rol=%s,
                            password=%s
                        WHERE id=%s
                    """, (
                        nuevo_usuario,
                        nuevo_nombre,
                        roles_texto,
                        nueva_password,
                        int(datos["id"])
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
                        roles_texto,
                        int(datos["id"])
                    ))


                conn.commit()

                st.success("✅ Usuario actualizado")
                st.rerun()


            except Exception as e:

                conn.rollback()
                st.error(str(e))


    with col2:

        if st.button("🗑 Eliminar usuario"):

            try:

                cur = conn.cursor()

                cur.execute(
                    "DELETE FROM usuarios WHERE id=%s",
                    (int(datos["id"]),)
                )

                conn.commit()

                st.success("✅ Usuario eliminado")
                st.rerun()


            except Exception as e:

                conn.rollback()
                st.error(str(e))


    st.divider()


    # ==========================
    # CREAR USUARIO
    # ==========================

    st.subheader("Crear nuevo usuario")


    with st.form("nuevo_usuario"):

        usuario = st.text_input("Usuario")

        password = st.text_input(
            "Contraseña",
            type="password"
        )

        nombre = st.text_input(
            "Nombre completo"
        )


        roles_nuevos = st.multiselect(
            "Roles",
            ROLES_DISPONIBLES
        )


        guardar = st.form_submit_button(
            "Crear usuario"
        )


        if guardar:

            try:

                cur = conn.cursor()

                roles_texto = ",".join(roles_nuevos)


                cur.execute("""
                    INSERT INTO usuarios
                    (usuario,password,nombre,rol)
                    VALUES (%s,%s,%s,%s)
                """, (
                    usuario,
                    password,
                    nombre,
                    roles_texto
                ))


                conn.commit()

                st.success(
                    "✅ Usuario creado correctamente"
                )

                st.rerun()


            except Exception as e:

                conn.rollback()
                st.error(str(e))