"""Dibujo del formulario en PDF (ReportLab) a partir de una maqueta."""

from __future__ import annotations

from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from . import fuentes
from .fuentes import NORMAL
from .maquetacion import MARCA_MM, MARCAS_MM, PAGINA_MM, QR_MM, QR_TAM_MM, Maqueta, PaginaMaqueta
from .marcadores import bits_marcador, ids_pagina, texto_qr

_ALTO = PAGINA_MM[1]


def _y(y_mm: float) -> float:
    """Coordenada Y de ReportLab (origen abajo) para una Y en mm desde arriba."""
    return (_ALTO - y_mm) * mm


def _dibujar_op(c: canvas.Canvas, op: dict, recursos: Path | None) -> None:
    t = op["op"]
    if t == "texto":
        c.setFillGray(op.get("g", 0.0))
        c.setFont(op["f"], op["s"])
        x, y = op["x"] * mm, _y(op["y"])
        if op["al"] == "centro":
            c.drawCentredString(x, y, op["t"])
        elif op["al"] == "der":
            c.drawRightString(x, y, op["t"])
        else:
            c.drawString(x, y, op["t"])
    elif t in ("rect", "casilla"):
        if t == "casilla":
            relleno, borde, grosor, radio = 1.0, 0.0, 1.0, 0.0
        else:
            relleno, borde, grosor, radio = op["relleno"], op["borde"], op["grosor"], op.get("radio", 0)
        if relleno is not None:
            c.setFillGray(relleno)
        if borde is not None:
            c.setStrokeGray(borde)
            c.setLineWidth(grosor)
        args = (op["x"] * mm, _y(op["y"] + op["h"]), op["w"] * mm, op["h"] * mm)
        kw = {"stroke": int(borde is not None), "fill": int(relleno is not None)}
        if radio:
            c.roundRect(*args, radio * mm, **kw)
        else:
            c.rect(*args, **kw)
    elif t == "linea":
        c.setStrokeGray(op.get("g", 0.0))
        c.setLineWidth(op["grosor"])
        c.line(op["x0"] * mm, _y(op["y0"]), op["x1"] * mm, _y(op["y1"]))
    elif t == "aspa":
        c.setStrokeGray(0.1)
        c.setLineWidth(1.6)
        m = 0.6
        x0, x1 = (op["x"] + m) * mm, (op["x"] + op["w"] - m) * mm
        y0, y1 = _y(op["y"] + m), _y(op["y"] + op["h"] - m)
        c.line(x0, y0, x1, y1)
        c.line(x0, y1, x1, y0)
    elif t == "imagen":
        ruta = (recursos / op["ruta"]) if recursos else Path(op["ruta"])
        if ruta.exists():
            c.drawImage(str(ruta), op["x"] * mm, _y(op["y"] + op["h"]), op["w"] * mm, op["h"] * mm,
                        mask="auto", preserveAspectRatio=True)


def _dibujar_marcador(c: canvas.Canvas, id_marcador: int, x_mm: float, y_mm: float) -> None:
    bits = bits_marcador(id_marcador)
    n = bits.shape[0]
    celda = MARCA_MM / n
    c.setFillGray(0.0)
    c.rect(x_mm * mm, _y(y_mm + MARCA_MM), MARCA_MM * mm, MARCA_MM * mm, stroke=0, fill=1)
    c.setFillGray(1.0)
    solape = 0.03
    for fila in range(n):
        col = 0
        while col < n:
            if bits[fila, col] == 0:
                inicio = col
                while col < n and bits[fila, col] == 0:
                    col += 1
                x = x_mm + inicio * celda
                y = y_mm + fila * celda
                c.rect(x * mm, _y(y + celda + solape), (col - inicio) * celda * mm, (celda + 2 * solape) * mm,
                       stroke=0, fill=1)
            else:
                col += 1


def _dibujar_qr(c: canvas.Canvas, contenido: str) -> None:
    w = QrCodeWidget(contenido, barLevel="M", barBorder=2)
    x0, y0, x1, y1 = w.getBounds()
    ancho, alto = x1 - x0, y1 - y0
    d = Drawing(QR_TAM_MM * mm, QR_TAM_MM * mm, transform=[QR_TAM_MM * mm / ancho, 0, 0, QR_TAM_MM * mm / alto, 0, 0])
    d.add(w)
    renderPDF.draw(d, c, QR_MM[0] * mm, _y(QR_MM[1] + QR_TAM_MM))


def dibujar_pagina(c: canvas.Canvas, maqueta: Maqueta, pag: PaginaMaqueta, hoja: int,
                   recursos: Path | None) -> None:
    for op in pag.ops:
        _dibujar_op(c, op, recursos)
    for k, id_m in enumerate(ids_pagina(pag.indice)):
        _dibujar_marcador(c, id_m, *MARCAS_MM[k])
    _dibujar_qr(c, texto_qr(maqueta.huella, pag.indice, hoja))
    # Pie de página
    total = len(maqueta.paginas)
    pie = maqueta.encuesta.get("pie", "")
    c.setFillGray(0.0)
    if pie:
        c.setFont(NORMAL, 8)
        c.drawString(20 * mm, _y(284.5), pie)
    datos = f"Página {pag.indice + 1} de {total}"
    if hoja:
        datos += f"   ·   Cuestionario nº {hoja:04d}"
    datos += f"   ·   Ref. {maqueta.huella}"
    c.setFont(NORMAL, 7.5)
    c.setFillGray(0.3)
    c.drawString(20 * mm, _y(288.5), datos)


def generar_pdf(maqueta: Maqueta, destino: Path, recursos: Path | None = None,
                hojas: list[int] | None = None) -> Path:
    """Genera el PDF imprimible.

    ``hojas``: números de cuestionario a imprimir (uno por copia). ``[0]`` (por defecto)
    genera una única copia sin numerar, pensada para fotocopiar.
    """
    fuentes.registrar()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(destino), pagesize=(PAGINA_MM[0] * mm, PAGINA_MM[1] * mm))
    enc = maqueta.encuesta
    c.setTitle(enc.get("titulo", "Encuesta"))
    c.setSubject(enc.get("subtitulo", ""))
    c.setCreator("Encuestas OMR")
    for hoja in hojas or [0]:
        for pag in maqueta.paginas:
            dibujar_pagina(c, maqueta, pag, hoja, recursos)
            c.showPage()
    c.save()
    return destino
