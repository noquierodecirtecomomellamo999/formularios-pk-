"""Genera la «Guía rápida» en PDF para las personas que usan el programa.

    python instalador/guia_rapida.py "Guía rápida.pdf"

Las capturas de pantalla están en instalador/capturas/.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)

from encuestas_omr import fuentes  # noqa: E402
from encuestas_omr.fuentes import NEGRITA, NORMAL  # noqa: E402

CAPTURAS = RAIZ / "instalador" / "capturas"
LOGO = RAIZ / "ejemplos" / "logos" / "logo_cirenc.png"
AZUL = colors.HexColor("#1c5cab")
VERDE = colors.HexColor("#8db92e")
GRIS = colors.HexColor("#52514e")
FONDO = colors.HexColor("#f0f4fa")


def estilos():
    fuentes.registrar()
    base = ParagraphStyle("base", fontName=NORMAL, fontSize=10.5, leading=15)
    return {
        "base": base,
        "titulo": ParagraphStyle("t", base, fontName=NEGRITA, fontSize=24, leading=30, alignment=TA_CENTER,
                                 textColor=AZUL),
        "sub": ParagraphStyle("s", base, fontSize=13, leading=18, alignment=TA_CENTER, textColor=GRIS),
        "h1": ParagraphStyle("h1", base, fontName=NEGRITA, fontSize=16, leading=21, textColor=AZUL,
                             spaceBefore=4 * mm, spaceAfter=2.5 * mm),
        "h2": ParagraphStyle("h2", base, fontName=NEGRITA, fontSize=12.5, leading=17, spaceBefore=3 * mm,
                             spaceAfter=1.5 * mm),
        "paso": ParagraphStyle("paso", base, leftIndent=8 * mm, firstLineIndent=-6 * mm, spaceAfter=1.6 * mm),
        "nota": ParagraphStyle("nota", base, fontSize=9.5, leading=13.5, textColor=GRIS),
        "celda": ParagraphStyle("celda", base, fontSize=9.5, leading=13),
        "celda_n": ParagraphStyle("celda_n", base, fontName=NEGRITA, fontSize=9.5, leading=13),
    }


E = estilos()


def p(texto, estilo="base"):
    return Paragraph(texto, E[estilo])


def pasos(lista):
    return [Paragraph(f"<b>{i}.</b>&nbsp;&nbsp;{t}", E["paso"]) for i, t in enumerate(lista, start=1)]


def vinetas(lista):
    return [Paragraph(f"•&nbsp;&nbsp;{t}", E["paso"]) for t in lista]


def captura(nombre, ancho_mm=165):
    ruta = CAPTURAS / nombre
    if not ruta.exists():
        return Spacer(1, 1)
    from PIL import Image as PILImage

    with PILImage.open(ruta) as im:
        w, h = im.size
    ancho = ancho_mm * mm
    img = Image(str(ruta), width=ancho, height=ancho * h / w)
    marco = Table([[img]], colWidths=[ancho + 2])
    marco.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c3c2b7")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return marco


def recuadro(contenido, color=FONDO):
    t = Table([[contenido]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def tabla_problemas(filas):
    datos = [[Paragraph("<b>Si pasa esto…</b>", E["celda"]), Paragraph("<b>Haz esto</b>", E["celda"])]]
    datos += [[Paragraph(a, E["celda_n"]), Paragraph(b, E["celda"])] for a, b in filas]
    t = Table(datos, colWidths=[62 * mm, 108 * mm], repeatRows=1)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), FONDO),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#c3c2b7")),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def contenido():
    h = []
    # Portada
    if LOGO.exists():
        from PIL import Image as PILImage

        with PILImage.open(LOGO) as im:
            w, hh = im.size
        h += [Spacer(1, 25 * mm), Image(str(LOGO), width=110 * mm, height=110 * mm * hh / w), Spacer(1, 15 * mm)]
    h += [p("Encuestas CIRENC", "titulo"), Spacer(1, 3 * mm),
          p("Guía rápida", "sub"), p("Encuestas en papel con lectura automática", "sub"), Spacer(1, 20 * mm)]
    h.append(recuadro(p(
        "Con este programa se <b>diseña</b> el cuestionario, se <b>imprime</b>, se <b>escanean</b> las hojas "
        "rellenadas y el programa <b>lee las casillas solo</b> y prepara las <b>tablas, gráficos y el informe "
        "en PDF</b>. Funciona en tu ordenador y sin internet.")))
    h.append(PageBreak())

    # 1. Instalar
    h.append(p("1. Instalar el programa (solo la primera vez)", "h1"))
    h += pasos([
        "Guarda en tu ordenador el archivo <b>Instalar-Encuestas-CIRENC.exe</b> que te han enviado.",
        "Haz doble clic en él. Si aparece el aviso azul <b>«Windows protegió su PC»</b>, pulsa "
        "<b>«Más información»</b> y después <b>«Ejecutar de todas formas»</b>. (Sale porque el programa es de la "
        "asociación y no está firmado por una empresa de software.)",
        "Deja marcada la casilla <b>«Crear un icono en el escritorio»</b>, pulsa <b>Instalar</b> y luego "
        "<b>Finalizar</b>.",
    ])
    h.append(recuadro(p("No necesita internet ni permisos de administrador. Para desinstalarlo: <i>Configuración "
                        "→ Aplicaciones → Encuestas CIRENC</i>. Al desinstalar o actualizar <b>no se borra "
                        "ninguna encuesta ni resultado</b>.", "nota")))

    # 2. Abrir y cerrar
    h.append(p("2. Abrir y cerrar", "h1"))
    h += vinetas([
        "Haz doble clic en el icono <b>Encuestas CIRENC</b> del escritorio (o búscalo en el menú Inicio). "
        "Se abre en el navegador (Edge, Chrome…). La primera vez tarda unos segundos.",
        "A la izquierda está el <b>menú con los 5 pasos</b> y, debajo, la <b>encuesta de trabajo</b>: "
        "elige siempre primero la encuesta con la que vas a trabajar.",
        "Para terminar, pulsa <b>«Cerrar el programa»</b> (abajo a la izquierda). Todo se guarda solo. Si "
        "solo cierras la pestaña del navegador no pasa nada: al pulsar el icono otra vez, vuelve a aparecer.",
    ])
    h.append(KeepTogether([Spacer(1, 2 * mm), captura("1_inicio.jpg", 150)]))

    # 3. Paso a paso
    h.append(PageBreak())
    h.append(p("3. Paso a paso", "h1"))
    h.append(KeepTogether([p("Paso 1 · Diseñar la encuesta", "h2"), *vinetas([
        "Ya vienen preparadas las encuestas de 2026: Centro de Día, Medio Rural, Tratamiento Ambulatorio y "
        "Familiares.",
        "Pulsa una pregunta para desplegarla y cambiar el texto o las opciones. <b>Los cambios se guardan "
        "solos.</b> Con los botones de flecha se cambia el orden y con el de la papelera se borra.",
        "<b>Duplicar</b>: para hacer la encuesta de otro año o de otro programa sin escribirla de nuevo.",
        "<b>Importar de Word</b>: sube un cuestionario en Word y el programa reconoce las preguntas.",
        "En la pestaña <b>Vista previa</b> se ve cómo quedará la hoja impresa.",
    ]), captura("2_disenar.jpg", 135)]))
    h.append(KeepTogether([p("Paso 2 · Imprimir", "h2"), *vinetas([
        "Elige <b>Copias numeradas</b>, escribe cuántos cuestionarios necesitas y pulsa <b>Generar PDF</b>; "
        "después <b>Descargar PDF</b> e imprímelo. Cada cuestionario lleva un número (no identifica a la "
        "persona: la encuesta sigue siendo anónima).",
        "Imprime a <b>tamaño real (100 %)</b> en folios blancos A4. Se puede imprimir a doble cara.",
    ])]))
    h.append(KeepTogether([p("Antes de repartir los cuestionarios", "h2"), recuadro([
        p("Explica a quien rellena:", "base"),
        *vinetas(["Marcar con una <b>X dentro de la casilla</b>, con bolígrafo o lápiz oscuro.",
                  "Si se equivoca: <b>rellenar entera la casilla equivocada</b> y marcar la buena con una X.",
                  "No escribir ni grapar sobre los <b>cuadrados negros de las esquinas</b> ni sobre el "
                  "<b>código QR</b>."])], colors.HexColor("#fff8e1"))]))
    h.append(KeepTogether([p("Paso 3 · Escanear y leer las hojas", "h2"), *vinetas([
        "Escanea todas las hojas rellenadas en un <b>PDF</b> (con la fotocopiadora o escáner: 200 o 300 ppp, en "
        "gris o en blanco y negro). Si las copias están numeradas, el orden da igual.",
        "En <b>3. Leer escaneos</b>, pulsa <b>Upload</b> (subir), elige el PDF y pulsa <b>Leer</b>. "
        "<b>No cambies de página hasta que termine</b> (unos segundos por hoja).",
        "Si alguna hoja no se puede leer, el programa dice por qué (normalmente hay que volver a escanearla "
        "recta y completa).",
    ]), captura("4_leer.jpg", 135)]))
    h.append(KeepTogether([p("Paso 4 · Revisar dudas", "h2"), *vinetas([
        "El programa enseña solo las respuestas que no ha podido leer con seguridad (dos casillas marcadas, una "
        "marca muy débil, un círculo en vez de una X…).",
        "En el recorte, el <b>recuadro verde</b> es lo que ha leído el programa. Elige la respuesta correcta a "
        "la derecha y pulsa <b>Guardar</b>.",
        "En <b>Textos escritos a mano</b> puedes copiar los comentarios (opcional: los que no copies salen como "
        "imagen al final del informe).",
    ]), captura("5_revisar.jpg", 135)]))
    h.append(KeepTogether([p("Paso 5 · Resultados e informe", "h2"), *vinetas([
        "Para cada pregunta aparece el gráfico, la tabla (respuesta, personas y porcentaje) y la frase de "
        "<b>Resultado</b>, que puedes retocar.",
        "Puedes elegir el tipo de gráfico (quesito o barras) y qué respuestas cuentan como <b>favorables</b> "
        "(por ejemplo, «Muy bien» y «Bien»).",
    ]), captura("6_resultados.jpg", 135)]))
    h.append(KeepTogether([*vinetas([
        "En la pestaña <b>Informe y exportación</b> escribe la introducción, revisa las conclusiones (salen "
        "propuestas solas) y el texto final con el lugar y la fecha. Pulsa <b>Generar informe PDF</b> y luego "
        "<b>Descargar</b>. Con <b>Exportar a Excel</b> tienes todas las respuestas en una hoja de cálculo.",
    ]), captura("7_informe.jpg", 135)]))

    # 4. Datos
    h.append(PageBreak())
    h.append(p("4. Dónde se guarda todo y copias de seguridad", "h1"))
    h += vinetas([
        "Todo se guarda en la carpeta <b>Documentos › Encuestas CIRENC</b>: encuestas, hojas escaneadas, "
        "revisiones e informes.",
        "Con el botón <b>«Abrir la carpeta de datos»</b> (a la izquierda) se abre esa carpeta.",
        "<b>Copia de seguridad</b>: copia de vez en cuando esa carpeta entera a un USB o a la nube. Para pasar "
        "las encuestas a otro ordenador, copia la carpeta en el mismo sitio del otro ordenador.",
    ])

    # 5. Problemas
    h.append(p("5. Si algo no va bien", "h1"))
    h.append(tabla_problemas([
        ("Al pulsar el icono no se abre nada",
         "Espera 10 segundos. Si no aparece, abre el navegador y escribe <b>127.0.0.1:8501</b>. Si tampoco, "
         "reinicia el ordenador y prueba otra vez."),
        ("«No se encuentran las marcas de las esquinas»",
         "La hoja está cortada, muy torcida o no es de este programa. Vuelve a escanearla recta y completa."),
        ("Salen muchas dudas",
         "Comprueba que se marca con una X dentro de la casilla y que se escanea a 200 o 300 ppp."),
        ("Aviso «faltan páginas»",
         "Falta escanear alguna hoja de ese cuestionario: escanéala y súbela; el programa la junta sola."),
        ("Una hoja de prueba cuenta en los resultados",
         "En <b>Revisar dudas › Cuestionarios</b>, márcala como «no debe contar»."),
        ("He cambiado la encuesta después de imprimirla",
         "No pasa nada: las hojas ya impresas se leen con su versión. Para cambios grandes, mejor <b>Duplicar</b>."),
        ("Nada de lo anterior funciona",
         "Pide ayuda y envía el archivo <b>registro.txt</b> que está en la carpeta "
         "<i>%LOCALAPPDATA%\\Encuestas CIRENC</i> (escríbelo en la barra del Explorador de archivos)."),
    ]))
    return h


def en_pagina(c, doc):
    c.saveState()
    if doc.page > 1:
        c.setFont(NORMAL, 8.5)
        c.setFillColor(GRIS)
        c.drawString(20 * mm, 12 * mm, "Encuestas CIRENC · Guía rápida")
        c.drawRightString(190 * mm, 12 * mm, f"Página {doc.page}")
        c.setStrokeColor(VERDE)
        c.setLineWidth(1.2)
        c.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
    c.restoreState()


def generar(destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=(210 * mm, 297 * mm), leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=22 * mm, title="Encuestas CIRENC · Guía rápida",
                            author="Asociación de Parkinson de La Roda (CIRENC)")
    doc.build(contenido(), onFirstPage=en_pagina, onLaterPages=en_pagina)
    return destino


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dist" / "Guía rápida.pdf"
    print(generar(salida))
