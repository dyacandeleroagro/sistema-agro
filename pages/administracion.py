import streamlit as st
import pandas as pd
from database import get_conn

def pantalla_administracion():

    st.title("⚙️ Administración")

    conn = get_conn()

    usuarios = pd.read_sql("""
        SELECT id, usuario, nombre, rol
        FROM usuarios
        ORDER BY nombre
    """, conn)

    st.subheader("Usuarios")

    st.dataframe(
        usuarios,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("Crear nuevo usuario")

    with st.form("nuevo_usuario"):

        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña")
        nombre = st.text_input("Nombre completo")

        rol = st.selectbox(
            "Rol",
            [
                "Operario",
                "Administrador",
                "Dueño"
            ]
        )

        guardar = st.form_submit_button("Crear usuario")

        if guardar:

            cur = conn.cursor()

            cur.execute("""
                INSERT INTO usuarios
                (usuario,password,nombre,rol)
                VALUES (%s,%s,%s,%s)
            """,(
                usuario,
                password,
                nombre,
                rol
            ))

            conn.commit()

            st.success("Usuario creado correctamente")
            st.rerun()