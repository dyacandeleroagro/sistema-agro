"""Persistencia en Neon para labores/lotes y control de combustible."""

import os
import pandas as pd
import streamlit as st
from database import get_conn

ARCHIVO_TELEMETRIA_LEGACY = "registro_telemetria.csv"
ARCHIVO_COMBUSTIBLE_LEGACY = "registro_combustible.csv"


def _fecha_sql(valor):
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.isna(fecha):
        return None
    return fecha.date()


def _numero(valor, default=0.0):
    numero = pd.to_numeric(valor, errors="coerce")
    return default if pd.isna(numero) else float(numero)


def asegurar_tablas_operativas():
    """Crea las tablas necesarias y migra CSV locales solo si Neon está vacío."""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS labores_lotes_registros (
                id BIGSERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                maquinaria TEXT NOT NULL DEFAULT '',
                lote TEXT NOT NULL DEFAULT '',
                has_trabajadas NUMERIC(14,2) NOT NULL DEFAULT 0,
                gasoil_consumido_l NUMERIC(14,2) NOT NULL DEFAULT 0,
                eficiencia_l_ha NUMERIC(14,3) NOT NULL DEFAULT 0,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS control_combustible_registros (
                id BIGSERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                maquina TEXT NOT NULL DEFAULT '',
                proveedor TEXT NOT NULL DEFAULT '',
                litros NUMERIC(14,2) NOT NULL DEFAULT 0,
                precio_litro NUMERIC(14,2) NOT NULL DEFAULT 0,
                total NUMERIC(14,2) NOT NULL DEFAULT 0,
                responsable TEXT NOT NULL DEFAULT '',
                observaciones TEXT NOT NULL DEFAULT '',
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()

        # Migración única práctica: importar CSV solo cuando la tabla destino está vacía.
        cur.execute("SELECT COUNT(*) FROM labores_lotes_registros")
        labores_vacias = cur.fetchone()[0] == 0
        if labores_vacias and os.path.exists(ARCHIVO_TELEMETRIA_LEGACY):
            try:
                df = pd.read_csv(ARCHIVO_TELEMETRIA_LEGACY)
                if not df.empty:
                    for _, fila in df.iterrows():
                        fecha = _fecha_sql(fila.get("Fecha"))
                        if fecha is None:
                            continue
                        has = _numero(fila.get("Has Trabajadas"))
                        eficiencia = _numero(fila.get("Eficiencia (L/Ha)"))
                        litros = _numero(
                            fila.get("Gasoil Consumido (L)"), has * eficiencia
                        )
                        cur.execute(
                            """
                            INSERT INTO labores_lotes_registros
                                (fecha, maquinaria, lote, has_trabajadas,
                                 gasoil_consumido_l, eficiencia_l_ha)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                fecha,
                                str(fila.get("Maquinaria", "") or ""),
                                str(fila.get("Lote", "") or ""),
                                has,
                                litros,
                                eficiencia,
                            ),
                        )
                    conn.commit()
            except Exception:
                conn.rollback()
                # No impedir que la aplicación abra por un CSV viejo mal formado.

        cur.execute("SELECT COUNT(*) FROM control_combustible_registros")
        combustible_vacio = cur.fetchone()[0] == 0
        if combustible_vacio and os.path.exists(ARCHIVO_COMBUSTIBLE_LEGACY):
            try:
                df = pd.read_csv(ARCHIVO_COMBUSTIBLE_LEGACY)
                if not df.empty:
                    for _, fila in df.iterrows():
                        fecha = _fecha_sql(fila.get("Fecha"))
                        if fecha is None:
                            continue
                        cur.execute(
                            """
                            INSERT INTO control_combustible_registros
                                (fecha, maquina, proveedor, litros, precio_litro,
                                 total, responsable, observaciones)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                fecha,
                                str(fila.get("Máquina", "") or ""),
                                str(fila.get("Proveedor", "") or ""),
                                _numero(fila.get("Litros")),
                                _numero(fila.get("Precio Litro")),
                                _numero(fila.get("Total")),
                                str(fila.get("Responsable", "") or ""),
                                str(fila.get("Observaciones", "") or ""),
                            ),
                        )
                    conn.commit()
            except Exception:
                conn.rollback()
                # No impedir que la aplicación abra por un CSV viejo mal formado.

    except Exception as exc:
        if conn:
            conn.rollback()
        raise RuntimeError(f"No se pudieron preparar las tablas operativas de Neon: {exc}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def cargar_labores_desde_neon():
    asegurar_tablas_operativas()
    conn = None
    try:
        conn = get_conn()
        df = pd.read_sql_query(
            """
            SELECT
                id AS "ID",
                TO_CHAR(fecha, 'YYYY-MM-DD') AS "Fecha",
                maquinaria AS "Maquinaria",
                lote AS "Lote",
                has_trabajadas AS "Has Trabajadas",
                gasoil_consumido_l AS "Gasoil Consumido (L)",
                eficiencia_l_ha AS "Eficiencia (L/Ha)"
            FROM labores_lotes_registros
            ORDER BY fecha DESC, id DESC
            """,
            conn,
        )
        for col in ["Has Trabajadas", "Gasoil Consumido (L)", "Eficiencia (L/Ha)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    finally:
        if conn:
            conn.close()


def guardar_labor_neon(fecha, maquinaria, lote, hectareas, eficiencia):
    conn = None
    cur = None
    try:
        asegurar_tablas_operativas()
        conn = get_conn()
        cur = conn.cursor()
        hectareas = _numero(hectareas)
        eficiencia = _numero(eficiencia)
        cur.execute(
            """
            INSERT INTO labores_lotes_registros
                (fecha, maquinaria, lote, has_trabajadas,
                 gasoil_consumido_l, eficiencia_l_ha)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (_fecha_sql(fecha), maquinaria, lote, hectareas,
             round(hectareas * eficiencia, 2), eficiencia),
        )
        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        st.error(f"No se pudo guardar la labor en Neon: {exc}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def actualizar_labor_neon(id_labor, fecha, maquinaria, lote, hectareas, eficiencia):
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        hectareas = _numero(hectareas)
        eficiencia = _numero(eficiencia)
        cur.execute(
            """
            UPDATE labores_lotes_registros
            SET fecha=%s, maquinaria=%s, lote=%s, has_trabajadas=%s,
                gasoil_consumido_l=%s, eficiencia_l_ha=%s
            WHERE id=%s
            """,
            (_fecha_sql(fecha), maquinaria, lote, hectareas,
             round(hectareas * eficiencia, 2), eficiencia, int(id_labor)),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        if conn:
            conn.rollback()
        st.error(f"No se pudieron actualizar los datos de la labor: {exc}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def eliminar_labor_neon(id_labor):
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM labores_lotes_registros WHERE id=%s", (int(id_labor),))
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        if conn:
            conn.rollback()
        st.error(f"No se pudo eliminar la labor: {exc}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def cargar_combustible_desde_neon():
    asegurar_tablas_operativas()
    conn = None
    try:
        conn = get_conn()
        df = pd.read_sql_query(
            """
            SELECT
                id AS "ID",
                TO_CHAR(fecha, 'YYYY-MM-DD') AS "Fecha",
                maquina AS "Máquina",
                proveedor AS "Proveedor",
                litros AS "Litros",
                precio_litro AS "Precio Litro",
                total AS "Total",
                responsable AS "Responsable",
                observaciones AS "Observaciones"
            FROM control_combustible_registros
            ORDER BY fecha DESC, id DESC
            """,
            conn,
        )
        for col in ["Litros", "Precio Litro", "Total"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    finally:
        if conn:
            conn.close()


def guardar_combustible_neon(registro):
    conn = None
    cur = None
    try:
        asegurar_tablas_operativas()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO control_combustible_registros
                (fecha, maquina, proveedor, litros, precio_litro, total,
                 responsable, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _fecha_sql(registro.get("Fecha")),
                str(registro.get("Máquina", "") or ""),
                str(registro.get("Proveedor", "") or ""),
                _numero(registro.get("Litros")),
                _numero(registro.get("Precio Litro")),
                _numero(registro.get("Total")),
                str(registro.get("Responsable", "") or ""),
                str(registro.get("Observaciones", "") or ""),
            ),
        )
        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        st.error(f"No se pudo guardar la carga de combustible en Neon: {exc}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
