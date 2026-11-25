"""
Escala estacional de gastos y proyección del año próximo.

Es pandas puro (no usa Streamlit ni la base), así que se puede probar solo.

Idea general:
  1. Se suman los gastos por mes calendario (solo meses COMPLETOS: el mes
     en curso se descarta porque todavía no terminó).
  2. Opcionalmente se llevan todos los meses a "pesos del último mes" con
     una inflación mensual estimada, para que un mes no parezca caro solo
     porque el peso valía menos.
  3. Para cada año se compara cada mes contra el promedio mensual de ESE
     año. Ese cociente es el índice: 1,00 = mes típico, 1,30 = 30 % más
     gasto que un mes típico, 0,70 = 30 % menos.
  4. El índice de cada mes calendario (enero, febrero, ...) es el promedio
     de todos los años disponibles.
  5. La proyección reparte el gasto anual esperado según ese índice.
"""

import pandas as pd

NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

UMBRAL_ALTO = 1.15
UMBRAL_BAJO = 0.85
MIN_MESES_POR_ANIO = 3


def _nivel(indice):
    if pd.isna(indice):
        return "Sin datos"
    if indice >= UMBRAL_ALTO:
        return "🔴 Alto"
    if indice <= UMBRAL_BAJO:
        return "🟢 Bajo"
    return "🟡 Normal"


def _etiqueta(indice):
    """Palabra simple para mostrarle a una persona."""
    if pd.isna(indice):
        return "Sin datos"
    if indice >= UMBRAL_ALTO:
        return "Mes caro"
    if indice <= UMBRAL_BAJO:
        return "Mes barato"
    return "Mes normal"


def fmt_pesos(valor, con_signo=False):
    """Formato argentino sin decimales: $ 1.234.567 (negativos: -$ 1.234)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(v):
        return "-"
    r = int(round(v))
    texto = f"{abs(r):,}".replace(",", ".")
    if r < 0:
        return f"-$ {texto}"
    if con_signo and r > 0:
        return f"+$ {texto}"
    return f"$ {texto}"


def fmt_corto(valor):
    """Para ejes de gráficos: 1,5 M / 800 mil."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    signo = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000:
        return f"{signo}{a / 1_000_000:.1f} M".replace(".", ",")
    if a >= 1_000:
        return f"{signo}{a / 1_000:.0f} mil"
    return f"{signo}{a:.0f}"


def resumen_escala_texto(escala, max_meses=3):
    """
    Devuelve {'caros': 'Marzo (+46 %), ...', 'baratos': 'Julio (-41 %)'}
    con los meses más pesados y más livianos. Vacío si no hay ninguno.
    """
    con = escala.dropna(subset=["indice"])

    caros = con[con["etiqueta"] == "Mes caro"].sort_values(
        "indice", ascending=False
    ).head(max_meses)

    baratos = con[con["etiqueta"] == "Mes barato"].sort_values(
        "indice"
    ).head(max_meses)

    def lista(d):
        return ", ".join(
            f"{r['nombre']} ({r['variacion_pct']:+.0f} %)"
            for _, r in d.iterrows()
        )

    return {"caros": lista(caros), "baratos": lista(baratos)}


def calcular_escala_gastos(
    df,
    col_fecha="_fecha_grafica",
    col_monto="_monto_grafica",
    inflacion_mensual=0.0,
    hoy=None,
):
    """
    Devuelve None si todavía no hay datos suficientes, o un diccionario con:
      escala      DataFrame de 12 filas (una por mes calendario)
      historico   DataFrame año x mes con los totales en pesos corrientes
      meses_completos, anios_usados, provisoria, base_mensual_actual,
      proyeccion_anual, anio_proyectado
    """

    if df is None or df.empty:
        return None
    if col_fecha not in df.columns or col_monto not in df.columns:
        return None

    d = df[[col_fecha, col_monto]].copy()
    d[col_fecha] = pd.to_datetime(d[col_fecha], errors="coerce")
    d[col_monto] = pd.to_numeric(d[col_monto], errors="coerce")
    d = d.dropna()

    if d.empty:
        return None

    hoy = pd.Timestamp(hoy) if hoy is not None else pd.Timestamp.today()
    mes_actual = hoy.to_period("M")

    d["_periodo"] = d[col_fecha].dt.to_period("M")

    # Solo meses completos.
    d = d[d["_periodo"] < mes_actual]

    if d.empty:
        return None

    mensual = d.groupby("_periodo")[col_monto].sum()

    rango = pd.period_range(mensual.index.min(), mensual.index.max(), freq="M")
    mensual = mensual.reindex(rango, fill_value=0.0)

    if len(mensual) < MIN_MESES_POR_ANIO:
        return None

    ultimo = rango.max()

    # Pesos del último mes completo.
    factor = [
        (1.0 + inflacion_mensual) ** (ultimo.ordinal - p.ordinal)
        for p in rango
    ]
    real = mensual * pd.Series(factor, index=rango)

    tabla = pd.DataFrame({
        "periodo": rango,
        "anio": [p.year for p in rango],
        "mes": [p.month for p in rango],
        "nominal": mensual.values,
        "real": real.values,
    })

    # Índice de cada mes contra el promedio de su propio año.
    anios_validos = [
        a for a, g in tabla.groupby("anio") if len(g) >= MIN_MESES_POR_ANIO
    ]

    if not anios_validos:
        return None

    base = tabla[tabla["anio"].isin(anios_validos)].copy()
    promedio_anio = base.groupby("anio")["real"].transform("mean")
    base["indice"] = base["real"] / promedio_anio

    por_mes = base.groupby("mes").agg(
        indice=("indice", "mean"),
        promedio=("nominal", "mean"),
        anios_con_datos=("anio", "nunique"),
    )

    escala = por_mes.reindex(range(1, 13))
    escala.index.name = "mes"

    # Para proyectar, los meses sin historia valen 1,00 y el conjunto se
    # re-normaliza para que el promedio de los 12 índices sea 1.
    indice_proy = escala["indice"].fillna(1.0)
    indice_proy = indice_proy / indice_proy.mean()

    # Nivel de gasto mensual actual: promedio de hasta los últimos 12 meses.
    ventana = tabla.tail(12)
    base_mensual_actual = float(ventana["real"].mean())

    anio_proyectado = hoy.year + 1
    proyeccion = []
    for m in range(1, 13):
        periodo = pd.Period(year=anio_proyectado, month=m, freq="M")
        meses_adelante = periodo.ordinal - ultimo.ordinal
        valor = (
            base_mensual_actual
            * indice_proy[m]
            * (1.0 + inflacion_mensual) ** meses_adelante
        )
        proyeccion.append(valor)

    escala["indice_proyeccion"] = indice_proy
    escala["proyeccion"] = proyeccion
    escala["proyeccion_acumulada"] = pd.Series(
        proyeccion, index=escala.index
    ).cumsum()
    escala["nivel"] = escala["indice"].apply(_nivel)
    escala["etiqueta"] = escala["indice"].apply(_etiqueta)
    escala["variacion_pct"] = (escala["indice"] - 1.0) * 100.0
    escala["nombre"] = [NOMBRES_MESES[m - 1] for m in escala.index]

    historico = tabla.pivot_table(
        index="anio", columns="mes", values="nominal", aggfunc="sum"
    ).reindex(columns=range(1, 13))
    historico.columns = NOMBRES_MESES
    historico.index.name = "Año"

    return {
        "escala": escala,
        "historico": historico.sort_index(ascending=False),
        "meses_completos": len(tabla),
        "anios_usados": anios_validos,
        "provisoria": len(tabla) < 12,
        "base_mensual_actual": base_mensual_actual,
        "proyeccion_anual": float(sum(proyeccion)),
        "anio_proyectado": anio_proyectado,
    }
