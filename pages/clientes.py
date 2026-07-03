import streamlit as st
import pandas as pd
from database import get_conn

def pantalla_clientes():

    st.title("👥 Clientes")

    conn = get_conn()

    with st.form("nuevo_cliente"):

        nombre = st.text_input("Nombre")
        cuit = st.text_input("CUIT")
        direccion = st.text_input("Dirección")
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")

        guardar = st.form_submit_button("Guardar")

        if guardar:

            cur = conn.cursor()

            cur.execute("""INSERT INTO clientes 
            (nombre, cuit, direccion, telefono, email)
            VALUES (%s, %s, %s, %s, %s)
         """, (nombre, cuit, direccion, telefono, email))
            conn.commit()

            st.success("Cliente agregado correctamente")

            st.rerun()

    st.divider()

    df = pd.read_sql(
        "SELECT * FROM clientes ORDER BY nombre",
        conn
    )

    st.dataframe(df,use_container_width=True)