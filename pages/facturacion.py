import streamlit as st
import pandas as pd
from database import get_conn


def pantalla_servicios():

    st.title("🛠 Servicios")

    conn = get_conn()

    st.subheader("Servicios registrados")

    df = pd.read_sql("""
        SELECT id,nombre,descripcion,precio,activo
        FROM servicios
        ORDER BY nombre
    """, conn)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("Nuevo servicio")

    with st.form("nuevo_servicio"):

        nombre = st.text_input("Nombre")

        descripcion = st.text_area("Descripción")

        precio = st.number_input(
            "Precio",
            min_value=0.0,
            step=100.0
        )

        activo = st.checkbox(
            "Servicio activo",
            value=True
        )

        guardar = st.form_submit_button(
            "Guardar servicio"
        )

        if guardar:

            try:

                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO servicios
                    (nombre,descripcion,precio,activo)
                    VALUES(%s,%s,%s,%s)
                """,(
                    nombre,
                    descripcion,
                    precio,
                    activo
                ))

                conn.commit()

                st.success("✅ Servicio agregado")

                st.rerun()

            except Exception as e:

                conn.rollback()
                st.error(str(e))

    st.divider()

    st.subheader("Editar servicio")

    if len(df) > 0:

        servicio = st.selectbox(
            "Servicio",
            df["nombre"]
        )

        datos = df[df["nombre"] == servicio].iloc[0]

        nombre = st.text_input(
            "Nombre del servicio",
            value=datos["nombre"]
        )

        descripcion = st.text_area(
            "Descripción",
            value=datos["descripcion"]
        )

        precio = st.number_input(
            "Precio",
            value=float(datos["precio"])
        )

        activo = st.checkbox(
            "Activo",
            value=bool(datos["activo"])
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button("💾 Guardar cambios"):

                try:

                    cur = conn.cursor()

                    cur.execute("""
                        UPDATE servicios
                        SET nombre=%s,
                            descripcion=%s,
                            precio=%s,
                            activo=%s
                        WHERE id=%s
                    """,(
                        nombre,
                        descripcion,
                        precio,
                        activo,
                        int(datos["id"])
                    ))

                    conn.commit()

                    st.success("Servicio actualizado")

                    st.rerun()

                except Exception as e:

                    conn.rollback()

                    st.error(str(e))

        with col2:

            if st.button("🗑 Eliminar servicio"):

                try:

                    cur = conn.cursor()

                    cur.execute("""
                        DELETE FROM servicios
                        WHERE id=%s
                    """,(
                        int(datos["id"]),
                    ))

                    conn.commit()

                    st.success("Servicio eliminado")

                    st.rerun()

                except Exception as e:

                    conn.rollback()

                    st.error(str(e))