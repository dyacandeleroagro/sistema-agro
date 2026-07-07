import streamlit as st
import pandas as pd
from database import get_conn

def pantalla_productos():

    st.title("📦 Productos")

    conn = get_conn()

    with st.form("nuevo_producto"):

        col1,col2,col3 = st.columns(3)

        with col1:
            codigo = st.text_input("Código")
            nombre = st.text_input("Nombre")

        with col2:
            unidad = st.selectbox(
                "Unidad",
                ["Unidad","Kg","Tonelada","Litro","Bolsa","Ha"]
            )
            precio = st.number_input(
                "Precio",
                min_value=0.0,
                step=100.0
            )

        with col3:
            stock = st.number_input(
                "Stock",
                min_value=0.0
            )

        guardar = st.form_submit_button("Guardar Producto")

        if guardar:

            cur = conn.cursor()

            cur.execute("""
                INSERT INTO productos
                (codigo,nombre,unidad,precio,stock)
                VALUES(%s,%s,%s,%s,%s)
            """,(codigo,nombre,unidad,precio,stock))

            conn.commit()

            st.success("Producto guardado")

            st.rerun()

    st.divider()

    df = pd.read_sql("""
        SELECT *
        FROM productos
        ORDER BY nombre
    """,conn)

    st.dataframe(df,use_container_width=True)