"""
Informe PDF del negocio (A4, listo para imprimir o compartir).

No usa Streamlit ni la base: recibe los datos ya calculados.
Colores (y además textos, para que se entienda impreso en blanco y negro):
  VERDE   = ingresos (lo que entró)
  ROJO    = gastos   (lo que salió)
  AZUL    = ganancia  /  NARANJA = pérdida
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analitica_gastos import fmt_corto, fmt_pesos, resumen_escala_texto

VERDE = colors.HexColor("#2E7D32")
VERDE_CLARO = colors.HexColor("#E8F5E9")
ROJO = colors.HexColor("#C62828")
ROJO_CLARO = colors.HexColor("#FFEBEE")
AZUL = colors.HexColor("#1565C0")
AZUL_CLARO = colors.HexColor("#E3F2FD")
NARANJA = colors.HexColor("#E65100")
NARANJA_CLARO = colors.HexColor("#FFF3E0")
AMARILLO = colors.HexColor("#F9A825")
AMARILLO_CLARO = colors.HexColor("#FFF8E1")
VERDE_OSCURO = colors.HexColor("#1E4620")
GRIS = colors.HexColor("#616161")
GRIS_CLARO = colors.HexColor("#F5F5F5")
GRIS_LINEA = colors.HexColor("#BDBDBD")

MESES_CORTOS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]

ANCHO = A4[0] - 36 * mm  # ancho útil entre márgenes


# ----------------------------------------------------------
# Estilos
# ----------------------------------------------------------

def _estilos():
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13)

    return {
        "normal": ParagraphStyle("normal", **base),
        "chico": ParagraphStyle(
            "chico", fontName="Helvetica", fontSize=8, leading=10.5,
            textColor=GRIS,
        ),
        "titulo": ParagraphStyle(
            "titulo", fontName="Helvetica-Bold", fontSize=22, leading=26,
            textColor=colors.white,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", fontName="Helvetica", fontSize=10.5, leading=14,
            textColor=colors.white,
        ),
        "seccion": ParagraphStyle(
            "seccion", fontName="Helvetica-Bold", fontSize=13, leading=16,
            textColor=colors.white,
        ),
        "kpi_titulo": ParagraphStyle(
            "kpi_titulo", fontName="Helvetica-Bold", fontSize=9, leading=11,
            alignment=TA_CENTER,
        ),
        "kpi_valor": ParagraphStyle(
            "kpi_valor", fontName="Helvetica-Bold", fontSize=17, leading=21,
            alignment=TA_CENTER,
        ),
        "kpi_nota": ParagraphStyle(
            "kpi_nota", fontName="Helvetica", fontSize=8, leading=10,
            alignment=TA_CENTER, textColor=GRIS,
        ),
        "celda": ParagraphStyle(
            "celda", fontName="Helvetica", fontSize=8.5, leading=10.5,
        ),
        "celda_der": ParagraphStyle(
            "celda_der", fontName="Helvetica", fontSize=8.5, leading=10.5,
            alignment=TA_RIGHT,
        ),
    }


def _barra_seccion(texto, color, est):
    """Título de sección: franja de color con texto blanco."""
    t = Table(
        [[Paragraph(escape(texto), est["seccion"])]],
        colWidths=[ANCHO],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ----------------------------------------------------------
# Pie y encabezado de cada página
# ----------------------------------------------------------

def _decorar_pagina(nombre_negocio, anio, generado):

    def dibujar(canvas, doc):
        canvas.saveState()

        ancho, alto = A4

        canvas.setStrokeColor(VERDE_OSCURO)
        canvas.setLineWidth(2)
        canvas.line(18 * mm, alto - 11 * mm, ancho - 18 * mm, alto - 11 * mm)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRIS)
        canvas.drawString(
            18 * mm, alto - 9 * mm,
            f"{nombre_negocio}  |  Informe del negocio {anio}",
        )

        canvas.setStrokeColor(GRIS_LINEA)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 13 * mm, ancho - 18 * mm, 13 * mm)

        canvas.drawString(18 * mm, 8.5 * mm, f"Generado el {generado}")
        canvas.drawRightString(
            ancho - 18 * mm, 8.5 * mm, f"Página {doc.page}"
        )

        canvas.restoreState()

    return dibujar


# ----------------------------------------------------------
# Bloques
# ----------------------------------------------------------

def _tarjetas_resumen(ingresos, gastos, resultado, anio, est):

    ganancia = resultado >= 0

    def tarjeta(titulo, valor, nota, color, fondo):
        st_t = ParagraphStyle("t", parent=est["kpi_titulo"], textColor=color)
        st_v = ParagraphStyle("v", parent=est["kpi_valor"], textColor=color)
        return [
            Paragraph(escape(titulo), st_t),
            Paragraph(escape(valor), st_v),
            Paragraph(escape(nota), est["kpi_nota"]),
        ]

    celdas = [[
        tarjeta("INGRESOS", fmt_pesos(ingresos),
                f"Lo que entró en {anio}", VERDE, VERDE_CLARO),
        tarjeta("GASTOS", fmt_pesos(gastos),
                f"Lo que salió en {anio}", ROJO, ROJO_CLARO),
        tarjeta(
            "RESULTADO: GANANCIA" if ganancia else "RESULTADO: PÉRDIDA",
            fmt_pesos(resultado),
            "Ingresos menos gastos",
            AZUL if ganancia else NARANJA,
            AZUL_CLARO if ganancia else NARANJA_CLARO,
        ),
    ]]

    sep = 4 * mm
    ancho_col = (ANCHO - 2 * sep) / 3

    t = Table(celdas, colWidths=[ancho_col, ancho_col, ancho_col])

    color_res = AZUL if ganancia else NARANJA
    fondo_res = AZUL_CLARO if ganancia else NARANJA_CLARO

    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), VERDE_CLARO),
        ("BACKGROUND", (1, 0), (1, 0), ROJO_CLARO),
        ("BACKGROUND", (2, 0), (2, 0), fondo_res),
        ("BOX", (0, 0), (0, 0), 1.4, VERDE),
        ("BOX", (1, 0), (1, 0), 1.4, ROJO),
        ("BOX", (2, 0), (2, 0), 1.4, color_res),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # Separación entre tarjetas con columnas "vacías" no hace falta:
    # se logra con un borde blanco grueso entre celdas.
    t.setStyle(TableStyle([
        ("LINEAFTER", (0, 0), (0, 0), sep, colors.white),
        ("LINEAFTER", (1, 0), (1, 0), sep, colors.white),
    ]))

    return t


def _leyenda(est):
    texto = (
        f'<font color="#2E7D32"><b>VERDE = INGRESO</b></font> (lo que entró)'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'<font color="#C62828"><b>ROJO = GASTO</b></font> (lo que salió)'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'<font color="#1565C0"><b>AZUL = GANANCIA</b></font>'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'<font color="#E65100"><b>NARANJA = PÉRDIDA</b></font>'
    )
    return Paragraph(texto, est["chico"])


def _leyenda_grafico(items, ancho=ANCHO, alto=14):
    """items: [(color, texto), ...] -> mini leyenda dibujada."""
    d = Drawing(ancho, alto)
    x = 0
    for color, texto in items:
        d.add(Rect(x, 2, 9, 9, fillColor=color, strokeColor=color))
        d.add(String(x + 13, 3, texto, fontName="Helvetica", fontSize=8,
                     fillColor=colors.black))
        x += 13 + 5.2 * len(texto) + 14
    return d


def _grafico_mes_a_mes(ingresos, gastos):

    ancho = float(ANCHO)
    alto = 170

    d = Drawing(ancho, alto)

    bc = VerticalBarChart()
    bc.x = 42
    bc.y = 22
    bc.width = ancho - 52
    bc.height = alto - 34

    bc.data = [list(map(float, ingresos)), list(map(float, gastos))]

    maximo = max(max(ingresos or [0]), max(gastos or [0]), 1.0)

    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = maximo * 1.1
    bc.valueAxis.labelTextFormat = lambda v: fmt_corto(v)
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.gridStrokeColor = colors.HexColor("#E0E0E0")
    bc.valueAxis.visibleGrid = True

    bc.categoryAxis.categoryNames = MESES_CORTOS
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fontSize = 8

    bc.bars[0].fillColor = VERDE
    bc.bars[1].fillColor = ROJO
    bc.bars[0].strokeColor = VERDE
    bc.bars[1].strokeColor = ROJO

    bc.groupSpacing = 6
    bc.barSpacing = 1

    d.add(bc)

    return d


def _tabla_mes_a_mes(df_evolucion, est):

    filas = [[
        Paragraph("<b>Mes</b>", est["celda"]),
        Paragraph("<b>INGRESOS</b>", est["celda_der"]),
        Paragraph("<b>GASTOS</b>", est["celda_der"]),
        Paragraph("<b>RESULTADO</b>", est["celda_der"]),
    ]]

    estilos = [
        ("BACKGROUND", (0, 0), (0, 0), GRIS),
        ("BACKGROUND", (1, 0), (1, 0), VERDE),
        ("BACKGROUND", (2, 0), (2, 0), ROJO),
        ("BACKGROUND", (3, 0), (3, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    # El texto de la cabecera es blanco (Paragraph ignora TEXTCOLOR).
    for i in range(4):
        base = est["celda"] if i == 0 else est["celda_der"]
        p = ParagraphStyle("h", parent=base, textColor=colors.white)
        filas[0][i] = Paragraph(
            ["Mes", "INGRESOS", "GASTOS", "RESULTADO"][i], ParagraphStyle(
                "hb", parent=p, fontName="Helvetica-Bold"
            )
        )

    for i, (mes, fila) in enumerate(df_evolucion.iterrows(), start=1):

        ing = float(fila["Ingresos"])
        gas = float(fila["Gastos comerciales"])
        res = ing - gas

        vacio = ing == 0 and gas == 0

        color_res = AZUL if res >= 0 else NARANJA

        def celda(valor, color, bold=False):
            texto = "-" if vacio else fmt_pesos(valor)
            return Paragraph(
                texto,
                ParagraphStyle(
                    "c", parent=est["celda_der"], textColor=color,
                    fontName="Helvetica-Bold" if bold else "Helvetica",
                ),
            )

        filas.append([
            Paragraph(escape(str(mes)), est["celda"]),
            celda(ing, VERDE),
            celda(gas, ROJO),
            celda(res, color_res, bold=True),
        ])

        if i % 2 == 0:
            estilos.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))

    total_ing = float(df_evolucion["Ingresos"].sum())
    total_gas = float(df_evolucion["Gastos comerciales"].sum())
    total_res = total_ing - total_gas

    n = len(filas)

    def total(valor, color):
        return Paragraph(
            fmt_pesos(valor),
            ParagraphStyle(
                "tt", parent=est["celda_der"], textColor=color,
                fontName="Helvetica-Bold", fontSize=9.5,
            ),
        )

    filas.append([
        Paragraph("<b>TOTAL DEL AÑO</b>", est["celda"]),
        total(total_ing, VERDE),
        total(total_gas, ROJO),
        total(total_res, AZUL if total_res >= 0 else NARANJA),
    ])

    estilos += [
        ("LINEABOVE", (0, n), (-1, n), 1.2, VERDE_OSCURO),
        ("BACKGROUND", (0, n), (-1, n), colors.HexColor("#ECEFF1")),
    ]

    t = Table(
        filas,
        colWidths=[ANCHO * 0.22, ANCHO * 0.26, ANCHO * 0.26, ANCHO * 0.26],
        repeatRows=1,
    )
    t.setStyle(TableStyle(estilos))

    return t


def _grafico_categorias(cat_df):
    """Barras horizontales rojas: en qué se gasta."""

    n = len(cat_df)
    alto = 22 + 17 * n
    ancho = float(ANCHO)

    d = Drawing(ancho, alto)

    bc = HorizontalBarChart()
    bc.x = 118
    bc.y = 8
    bc.width = ancho - 170
    bc.height = alto - 14

    # Se dibuja de abajo hacia arriba: se invierte para que el mayor quede arriba.
    valores = list(map(float, cat_df["Monto"]))[::-1]
    nombres = [str(c)[:28] for c in cat_df["Categoría"]][::-1]

    bc.data = [valores]
    bc.categoryAxis.categoryNames = nombres
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.boxAnchor = "e"
    bc.categoryAxis.labels.dx = -4

    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = max(valores + [1.0]) * 1.12
    bc.valueAxis.labelTextFormat = lambda v: fmt_corto(v)
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.gridStrokeColor = colors.HexColor("#E0E0E0")
    bc.valueAxis.visibleGrid = True

    bc.bars[0].fillColor = ROJO
    bc.bars[0].strokeColor = ROJO
    bc.barWidth = 9
    bc.groupSpacing = 6

    d.add(bc)
    return d


def _tabla_categorias(cat_df, total, est):

    filas = [[
        Paragraph("Categoría", ParagraphStyle(
            "h1", parent=est["celda"], textColor=colors.white,
            fontName="Helvetica-Bold")),
        Paragraph("GASTO", ParagraphStyle(
            "h2", parent=est["celda_der"], textColor=colors.white,
            fontName="Helvetica-Bold")),
        Paragraph("% del total", ParagraphStyle(
            "h3", parent=est["celda_der"], textColor=colors.white,
            fontName="Helvetica-Bold")),
    ]]

    for _, r in cat_df.iterrows():
        pct = (r["Monto"] / total * 100.0) if total else 0.0
        filas.append([
            Paragraph(escape(str(r["Categoría"])), est["celda"]),
            Paragraph(fmt_pesos(r["Monto"]), ParagraphStyle(
                "m", parent=est["celda_der"], textColor=ROJO)),
            Paragraph(f"{pct:.1f} %".replace(".", ","), est["celda_der"]),
        ])

    t = Table(
        filas,
        colWidths=[ANCHO * 0.50, ANCHO * 0.28, ANCHO * 0.22],
        repeatRows=1,
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROJO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ]))
    return t


def _grafico_escala(escala):
    """Barras por mes: rojo = se gasta más de lo normal, verde = menos."""

    ancho = float(ANCHO)
    alto = 150

    d = Drawing(ancho, alto)

    bc = VerticalBarChart()
    bc.x = 38
    bc.y = 26
    bc.width = ancho - 48
    bc.height = alto - 38

    valores = []
    for m in range(1, 13):
        v = escala.loc[m, "variacion_pct"]
        valores.append(0.0 if pd.isna(v) else float(v))

    bc.data = [valores]

    tope = max(max(abs(v) for v in valores), 20.0) * 1.15
    bc.valueAxis.valueMin = -tope
    bc.valueAxis.valueMax = tope
    bc.valueAxis.labelTextFormat = (
        lambda v: "0 %" if abs(v) < 0.5 else f"{v:+.0f} %"
    )
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.gridStrokeColor = colors.HexColor("#E0E0E0")
    bc.valueAxis.visibleGrid = True

    bc.categoryAxis.categoryNames = MESES_CORTOS
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labelAxisMode = "low"

    for i, m in enumerate(range(1, 13)):
        etiqueta = escala.loc[m, "etiqueta"]
        color = {
            "Mes caro": ROJO,
            "Mes barato": VERDE,
            "Mes normal": AMARILLO,
        }.get(etiqueta, colors.HexColor("#E0E0E0"))
        bc.bars[(0, i)].fillColor = color
        bc.bars[(0, i)].strokeColor = color

    bc.groupSpacing = 8

    d.add(bc)
    return d


def _tabla_plan(escala, anio_proy, est):

    h = lambda txt, der=False: Paragraph(
        txt,
        ParagraphStyle(
            "hp", parent=est["celda_der"] if der else est["celda"],
            textColor=colors.white, fontName="Helvetica-Bold",
        ),
    )

    filas = [[
        h("Mes"),
        h("Qué esperar"),
        h(f"Gasto estimado {anio_proy}", True),
        h("Juntar hasta ese mes", True),
    ]]

    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), ROJO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    fondos = {
        "Mes caro": (ROJO_CLARO, ROJO),
        "Mes normal": (AMARILLO_CLARO, colors.HexColor("#8D6E00")),
        "Mes barato": (VERDE_CLARO, VERDE),
        "Sin datos": (GRIS_CLARO, GRIS),
    }

    for i, m in enumerate(range(1, 13), start=1):

        et = escala.loc[m, "etiqueta"]
        fondo, texto_color = fondos.get(et, fondos["Sin datos"])

        pct = escala.loc[m, "variacion_pct"]
        extra = "" if pd.isna(pct) else f"  ({pct:+.0f} %)"

        filas.append([
            Paragraph(escape(escala.loc[m, "nombre"]), est["celda"]),
            Paragraph(
                f"<b>{escape(et.upper())}</b>{extra}",
                ParagraphStyle("q", parent=est["celda"], textColor=texto_color),
            ),
            Paragraph(fmt_pesos(escala.loc[m, "proyeccion"]),
                      est["celda_der"]),
            Paragraph(fmt_pesos(escala.loc[m, "proyeccion_acumulada"]),
                      est["celda_der"]),
        ])
        estilos.append(("BACKGROUND", (1, i), (1, i), fondo))

    t = Table(
        filas,
        colWidths=[ANCHO * 0.20, ANCHO * 0.30, ANCHO * 0.25, ANCHO * 0.25],
        repeatRows=1,
    )
    t.setStyle(TableStyle(estilos))
    return t


# ----------------------------------------------------------
# Función principal
# ----------------------------------------------------------

def generar_informe_pdf(
    anio,
    df_evolucion,
    gastos_categoria=None,
    resultado_escala=None,
    inflacion_mensual_pct=0.0,
    nombre_negocio="D&A Candelero Agro",
    ahora=None,
):
    """
    anio              int
    df_evolucion      DataFrame con índice = nombre del mes (12 filas) y
                      columnas 'Ingresos' y 'Gastos comerciales'
    gastos_categoria  DataFrame con columnas 'Categoría' y 'Monto'
                      (ya filtrado al año), o None
    resultado_escala  lo que devuelve calcular_escala_gastos(), o None
    Devuelve los bytes del PDF.
    """

    est = _estilos()
    if ahora is None:
        try:
            from zoneinfo import ZoneInfo
            ahora = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        except Exception:
            ahora = datetime.now()
    generado = ahora.strftime("%d/%m/%Y %H:%M")

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Informe del negocio {anio}",
        author=nombre_negocio,
    )

    ingresos = [float(v) for v in df_evolucion["Ingresos"]]
    gastos = [float(v) for v in df_evolucion["Gastos comerciales"]]

    total_ing = sum(ingresos)
    total_gas = sum(gastos)
    resultado = total_ing - total_gas

    story = []

    # --- Portada / título ---
    titulo = Table(
        [[Paragraph("INFORME DEL NEGOCIO", est["titulo"])],
         [Paragraph(
             escape(f"{nombre_negocio}   |   Ejercicio {anio}"),
             est["subtitulo"])]],
        colWidths=[ANCHO],
    )
    titulo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), VERDE_OSCURO),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
    ]))
    story += [titulo, Spacer(1, 8 * mm)]

    # --- Resumen en 3 tarjetas ---
    story += [
        _barra_seccion("RESUMEN DEL AÑO", VERDE_OSCURO, est),
        Spacer(1, 3 * mm),
        _tarjetas_resumen(total_ing, total_gas, resultado, anio, est),
        Spacer(1, 3 * mm),
        _leyenda(est),
        Spacer(1, 2 * mm),
    ]

    if resultado >= 0:
        frase = (
            f"En {anio} el negocio cerró con una <b>ganancia de "
            f"{fmt_pesos(resultado)}</b>: entraron {fmt_pesos(total_ing)} y "
            f"salieron {fmt_pesos(total_gas)}."
        )
    else:
        frase = (
            f"En {anio} el negocio cerró con una <b>pérdida de "
            f"{fmt_pesos(abs(resultado))}</b>: entraron "
            f"{fmt_pesos(total_ing)} y salieron {fmt_pesos(total_gas)}."
        )

    story += [Paragraph(frase, est["normal"]), Spacer(1, 5 * mm)]

    # --- 1. Mes a mes ---
    story += [
        _barra_seccion("1. MES A MES: INGRESOS Y GASTOS", VERDE_OSCURO, est),
        Spacer(1, 2 * mm),
        _leyenda_grafico([(VERDE, "Ingresos (lo que entró)"),
                          (ROJO, "Gastos (lo que salió)")]),
        _grafico_mes_a_mes(ingresos, gastos),
        Spacer(1, 2 * mm),
        _tabla_mes_a_mes(df_evolucion, est),
        Spacer(1, 6 * mm),
    ]

    # --- 2. En qué se gasta ---
    if gastos_categoria is not None and not gastos_categoria.empty:

        cat = gastos_categoria.copy()
        cat["Monto"] = pd.to_numeric(cat["Monto"], errors="coerce").fillna(0)
        cat = cat[cat["Monto"] > 0].sort_values("Monto", ascending=False)

        total_cat = float(cat["Monto"].sum())

        if total_cat > 0:

            if len(cat) > 8:
                resto = float(cat["Monto"].iloc[8:].sum())
                cat = cat.iloc[:8]
                cat = pd.concat([
                    cat,
                    pd.DataFrame([{"Categoría": "Otras", "Monto": resto}]),
                ], ignore_index=True)

            story.append(KeepTogether([
                _barra_seccion("2. EN QUÉ SE GASTA", ROJO, est),
                Spacer(1, 2 * mm),
                Paragraph(
                    f"Los gastos de {anio} agrupados por categoría. "
                    "Las más grandes están arriba.",
                    est["normal"]),
                Spacer(1, 1 * mm),
                _grafico_categorias(cat),
                Spacer(1, 2 * mm),
                _tabla_categorias(cat, total_cat, est),
                Spacer(1, 6 * mm),
            ]))

    # --- 3 y 4. Escala y plan ---
    if resultado_escala is not None:

        escala = resultado_escala["escala"]
        anio_proy = resultado_escala["anio_proyectado"]
        textos = resumen_escala_texto(escala)

        bloque = [
            _barra_seccion(
                "3. ¿EN QUÉ MESES SE GASTA MÁS O MENOS?", ROJO, est),
            Spacer(1, 2 * mm),
            Paragraph(
                "Cada mes se compara con un mes normal (el promedio de "
                "gasto de ese año), usando todo el historial disponible. "
                "<b>Rojo</b>: se gasta más de lo normal. "
                "<b>Verde</b>: se gasta menos. "
                "<b>Amarillo</b>: parecido a lo normal.",
                est["normal"]),
            Spacer(1, 2 * mm),
            _leyenda_grafico([
                (ROJO, "Mes caro (15 % o más sobre lo normal)"),
                (AMARILLO, "Normal"),
                (VERDE, "Mes barato (15 % o más debajo)"),
            ]),
            _grafico_escala(escala),
        ]

        if textos["caros"]:
            bloque.append(Paragraph(
                f'<font color="#C62828"><b>Meses más pesados:</b></font> '
                f'{escape(textos["caros"])}.', est["normal"]))

        if textos["baratos"]:
            bloque.append(Paragraph(
                f'<font color="#2E7D32"><b>Meses más livianos:</b></font> '
                f'{escape(textos["baratos"])}.', est["normal"]))

        if resultado_escala["provisoria"]:
            bloque += [
                Spacer(1, 1.5 * mm),
                Paragraph(
                    f"<b>Atención:</b> hay solo "
                    f"{resultado_escala['meses_completos']} meses completos "
                    "de historia, así que esta escala es provisoria. Mejora "
                    "a medida que se cargan más resúmenes del banco.",
                    est["chico"]),
            ]

        story.append(KeepTogether(bloque))
        story.append(Spacer(1, 6 * mm))

        plan = [
            _barra_seccion(
                f"4. PLAN PARA {anio_proy}: CUÁNTO JUNTAR", ROJO, est),
            Spacer(1, 2 * mm),
            Paragraph(
                f"Gasto total estimado para {anio_proy}: "
                f"<b>{fmt_pesos(resultado_escala['proyeccion_anual'])}</b>. "
                f"Se calcula con el gasto mensual típico de hoy "
                f"({fmt_pesos(resultado_escala['base_mensual_actual'])}) "
                "repartido según los meses caros y baratos.",
                est["normal"]),
            Spacer(1, 2 * mm),
            _tabla_plan(escala, anio_proy, est),
            Spacer(1, 2 * mm),
        ]

        nota = (
            "Es una guía para saber en qué meses conviene tener plata "
            "reservada, no una predicción exacta."
        )
        if inflacion_mensual_pct and inflacion_mensual_pct > 0:
            nota += (
                f" Se consideró una inflación de "
                f"{inflacion_mensual_pct:.1f} % mensual."
            ).replace(".", ",", 1)

        plan.append(Paragraph(nota, est["chico"]))

        story.append(KeepTogether(plan))

    doc.build(
        story,
        onFirstPage=_decorar_pagina(nombre_negocio, anio, generado),
        onLaterPages=_decorar_pagina(nombre_negocio, anio, generado),
    )

    return buffer.getvalue()
