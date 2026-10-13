"""Informe de resultados en PDF (ReportLab), con la estructura habitual de los informes de satisfacción:

ficha técnica → por cada pregunta: gráfico, tabla y frase de resultado → comentarios
escritos → conclusiones.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from xml.sax.saxutils import escape

from PIL import Image as PILImage

from . import fuentes, graficos
from .almacen import Almacen
from .analisis import ResumenPregunta, conclusiones_automaticas, num, pct, resumir
from .fuentes import CURSIVA, NEGRITA, NORMAL
from .recortes import guardar_png, recorte_texto
from .resultados import Consolidado, consolidar

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
AZUL = colors.HexColor("#1c5cab")
GRIS_TABLA = colors.HexColor("#f0efec")
LINEA = colors.HexColor("#c3c2b7")
TINTA_2 = colors.HexColor("#52514e")


def _estilos():
    fuentes.registrar()
    base = ParagraphStyle("base", fontName=NORMAL, fontSize=10, leading=13.5)
    return {
        "base": base,
        "titulo": ParagraphStyle("titulo", base, fontName=NEGRITA, fontSize=15, leading=19, alignment=TA_CENTER,
                                 spaceAfter=2 * mm),
        "subtitulo": ParagraphStyle("subtitulo", base, fontSize=11, alignment=TA_CENTER, textColor=TINTA_2,
                                    spaceAfter=5 * mm),
        "seccion": ParagraphStyle("seccion", base, fontName=NEGRITA, fontSize=12.5, leading=16, textColor=AZUL,
                                  spaceBefore=5 * mm, spaceAfter=2 * mm),
        "pregunta": ParagraphStyle("pregunta", base, fontName=NEGRITA, fontSize=10.5, leading=14, spaceBefore=4 * mm,
                                   spaceAfter=1.5 * mm),
        "resultado": ParagraphStyle("resultado", base, spaceBefore=1.5 * mm),
        "nota": ParagraphStyle("nota", base, fontName=CURSIVA, fontSize=8.5, leading=11, textColor=TINTA_2),
        "celda": ParagraphStyle("celda", base, fontSize=9, leading=11.5),
        "celda_n": ParagraphStyle("celda_n", base, fontName=NEGRITA, fontSize=9, leading=11.5),
    }


def _p(texto: str, estilo) -> Paragraph:
    return Paragraph(escape(texto).replace("\n", "<br/>"), estilo)


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def textos_por_defecto(enc, cons: Consolidado, resumenes: list[ResumenPregunta]) -> dict:
    hoy = date.today()
    n = len(cons.validos)
    programa = f" ({enc.subtitulo})" if enc.subtitulo else ""
    return {
        "titulo": f"{enc.titulo} — Resultados",
        "introduccion": (f"Encuesta realizada en {MESES[hoy.month - 1]} de {hoy.year} a {n} "
                         f"{'persona' if n == 1 else 'personas'}{programa}. {enc.introduccion}").strip(),
        "conclusiones": conclusiones_automaticas(resumenes),
        "cierre": "",
        "incluir_recortes": True,
    }


class _CanvasNumerado(canvas_mod.Canvas):
    """Canvas que conoce el número total de páginas (para el pie "Página X de Y")."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont(NORMAL, 8)
            self.setFillColor(TINTA_2)
            self.drawRightString(192 * mm, 10 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _tabla(filas: list[list], anchos: list[float], cabecera: bool = True) -> Table:
    t = Table(filas, colWidths=anchos, hAlign="LEFT", repeatRows=1 if cabecera else 0)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), NORMAL),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if cabecera:
        estilo += [("FONTNAME", (0, 0), (-1, 0), NEGRITA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_TABLA),
                   ("LINEBELOW", (0, 0), (-1, 0), 0.8, TINTA_2)]
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_pregunta(r: ResumenPregunta, est) -> Table | None:
    e = r.elemento
    if e.tipo in ("unica", "multiple"):
        maximo = max((f.n for f in r.tabla), default=0)
        filas = [["Respuesta", "Personas", "Porcentaje"]]
        for f in r.tabla:
            estilo = est["celda_n"] if f.n == maximo and maximo > 0 else est["celda"]
            filas.append([Paragraph(escape(f.etiqueta), estilo), str(f.n), pct(f.pct)])
        if r.n_blanco:
            filas.append([Paragraph("<i>Sin respuesta</i>", est["celda"]), str(r.n_blanco), ""])
        return _tabla(filas, [100 * mm, 28 * mm, 30 * mm])
    if e.tipo == "escala":
        u = r.umbral
        multi = len(r.filas) > 1
        cab = (["Aspecto"] if multi else []) + ["Media", "Mediana", f"% ≥ {num(u)}", "Respuestas"]
        if e.extras:
            cab.append(" / ".join(e.extras))
        filas = [cab]
        for f in r.filas:
            fila = ([Paragraph(escape(f.etiqueta), est["celda"])] if multi else []) + [
                num(f.media), num(f.mediana), pct(f.pct_umbral), str(f.n)]
            if e.extras:
                fila.append(str(f.n_extras))
            filas.append(fila)
        anchos = ([70 * mm] if multi else []) + [20 * mm, 20 * mm, 22 * mm, 24 * mm] + ([22 * mm] if e.extras else [])
        tabla = _tabla(filas, anchos)
        if not multi:
            # Distribución de puntuaciones, como en los informes habituales
            dist = [["Puntuación", "Personas", "Porcentaje"]] + [[d.etiqueta, str(d.n), pct(d.pct)]
                                                                 for d in r.filas[0].distribucion if d.n]
            return [tabla, Spacer(1, 2 * mm), _tabla(dist, [40 * mm, 28 * mm, 30 * mm])]
        return tabla
    if e.tipo == "numero" and r.numeros:
        import statistics

        filas = [["Respuestas", "Media", "Mediana", "Mínimo", "Máximo"],
                 [str(len(r.numeros)), num(statistics.fmean(r.numeros), 1), num(statistics.median(r.numeros), 1),
                  str(min(r.numeros)), str(max(r.numeros))]]
        return _tabla(filas, [28 * mm] * 5)
    return None


def generar_informe(almacen: Almacen, encuesta_id: str, destino: Path, textos: dict | None = None,
                    graficos_elegidos: dict[str, str] | None = None) -> Path:
    fuentes.registrar()
    enc = almacen.cargar(encuesta_id)
    cons = consolidar(almacen, encuesta_id, enc)
    resumenes = resumir(enc, cons)
    por_id = {r.elemento.id: r for r in resumenes}
    t = textos_por_defecto(enc, cons, resumenes)
    t.update({k: v for k, v in (textos or almacen.textos_informe(encuesta_id)).items() if v is not None})
    elegidos = graficos_elegidos or {}
    frases = t.get("frases") or {}
    est = _estilos()
    recursos = almacen.recursos(encuesta_id)
    tmp = Path(tempfile.mkdtemp(prefix="informe_"))

    historia = [_p(t["titulo"], est["titulo"])]
    if enc.subtitulo:
        historia.append(_p(enc.subtitulo, est["subtitulo"]))
    if t.get("introduccion"):
        historia += [_p(t["introduccion"], est["base"]), Spacer(1, 3 * mm)]

    # Ficha técnica
    revisadas = sum(1 for d in cons.dudas if cons.respuestas[d.cuestionario][d.pregunta].estado == "revisado")
    ficha = [["Cuestionarios analizados", str(len(cons.validos))],
             ["Fecha del informe", fecha_larga(date.today())]]
    if cons.errores:
        ficha.append(["Páginas escaneadas que no se pudieron leer", str(len(cons.errores))])
    if revisadas:
        ficha.append(["Respuestas comprobadas a mano", str(revisadas)])
    if cons.dudas_pendientes:
        ficha.append(["Respuestas dudosas sin revisar (se usa la lectura automática)", str(len(cons.dudas_pendientes))])
    tf = Table(ficha, colWidths=[110 * mm, 50 * mm], hAlign="LEFT")
    tf.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), NORMAL), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                            ("FONTNAME", (1, 0), (1, -1), NEGRITA), ("BACKGROUND", (0, 0), (-1, -1), GRIS_TABLA),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.white),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    historia += [tf, Spacer(1, 2 * mm)]

    textos_manuscritos = []
    pendientes: list = []
    for e in enc.elementos:
        if e.tipo == "seccion":
            pendientes.append(_p(e.etiqueta, est["seccion"]))
            continue
        if e.tipo == "texto":
            pendientes.append(_p(e.etiqueta, est["pregunta"]))
            continue
        r = por_id[e.id]
        # Los títulos de sección (y textos) van en el mismo bloque que la pregunta siguiente,
        # para que nunca queden solos al final de una página.
        bloque = pendientes + [_p(e.etiqueta, est["pregunta"])]
        pendientes = []
        if e.tipo == "abierta":
            if r.textos:
                bloque.append(ListFlowable([ListItem(_p(x, est["base"]), leftIndent=8) for x in r.textos],
                                           bulletType="bullet", start="•", leftIndent=10))
            bloque.append(Paragraph(f"<b>Resultado:</b> {escape(frases.get(e.id) or r.frase)}", est["resultado"]))
            if r.n_escritos > len(r.textos):
                textos_manuscritos.append(e.id)
            historia.append(KeepTogether(bloque))
            continue
        img = graficos.grafico(r, tmp / f"{e.id}.png", elegidos.get(e.id))
        if img:
            with PILImage.open(img) as im:
                w, h = im.size
            ancho = min(160 * mm, w / 200 * 25.4 * mm)
            alto = ancho * h / w
            if alto > 95 * mm:
                ancho, alto = ancho * 95 * mm / alto, 95 * mm
            bloque.append(Image(str(img), width=ancho, height=alto, hAlign="LEFT"))
            bloque.append(Spacer(1, 2 * mm))
        tabla = _tabla_pregunta(r, est)
        if isinstance(tabla, list):
            bloque += tabla
        elif tabla is not None:
            bloque.append(tabla)
        bloque.append(Paragraph(f"<b>Resultado:</b> {escape(frases.get(e.id) or r.frase)}", est["resultado"]))
        if r.especifique:
            bloque.append(_p("Respuestas escritas: " + "; ".join(r.especifique), est["nota"]))
        if r.n_especifique_sin_transcribir:
            textos_manuscritos.append(e.id)
        if r.n_dudosas:
            bloque.append(_p(f"Incluye {r.n_dudosas} respuesta(s) dudosa(s) sin revisar.", est["nota"]))
        historia.append(KeepTogether(bloque))

    historia += pendientes  # (por si la encuesta termina en un título)

    # Anexo: comentarios escritos a mano sin transcribir
    if t.get("incluir_recortes", True) and textos_manuscritos:
        recortes = []
        for item in cons.textos:
            if item.pregunta not in textos_manuscritos or item.cuestionario in cons.descartados:
                continue
            resp = cons.respuestas[item.cuestionario][item.pregunta]
            ya = resp.texto if item.opcion is None else resp.especifique.get(item.opcion, {}).get("texto")
            if ya:
                continue
            img = recorte_texto(almacen, encuesta_id, item.ref, item.pregunta, item.tipo_texto, item.opcion)
            if img is None:
                continue
            ruta = guardar_png(img, tmp / f"rec_{item.cuestionario}_{item.pregunta}_{item.opcion}.png")
            h, w = img.shape[:2]
            ancho = min(160 * mm, w / 8 * mm)
            e = enc.pregunta(item.pregunta)
            recortes.append(KeepTogether([
                _p(f"{e.numero} {e.texto[:80]} — cuestionario {item.cuestionario}".strip(), est["nota"]),
                Image(str(ruta), width=ancho, height=ancho * h / w, hAlign="LEFT"), Spacer(1, 3 * mm)]))
        if recortes:
            historia += [PageBreak(), _p("Anexo: comentarios escritos a mano", est["seccion"]),
                         _p("Recortes de los cuestionarios escaneados con texto escrito que no se ha transcrito.",
                            est["nota"]), Spacer(1, 3 * mm)] + recortes

    if t.get("conclusiones"):
        historia += [_p("Conclusiones", est["seccion"])]
        for linea in t["conclusiones"].splitlines():
            linea = linea.strip()
            if not linea:
                historia.append(Spacer(1, 2 * mm))
            elif linea.startswith(("- ", "• ", "* ")):
                historia.append(Paragraph("•&nbsp;&nbsp;" + escape(linea[2:]),
                                          ParagraphStyle("vi", est["base"], leftIndent=10, firstLineIndent=-8,
                                                         spaceAfter=1.2 * mm)))
            else:
                historia.append(_p(linea, ParagraphStyle("pc", est["base"], spaceAfter=2 * mm)))
    if t.get("cierre"):
        historia += [Spacer(1, 8 * mm), _p(t["cierre"], est["base"])]

    cab = enc.cabecera
    logos = [recursos / n for n in cab.logos if (recursos / n).exists()]

    def en_pagina(c, doc):
        c.saveState()
        y = 287 * mm
        for i, linea in enumerate(cab.lineas_izquierda[:4]):
            c.setFont(NEGRITA if i == 0 else NORMAL, 7.5)
            c.setFillColor(colors.black if i == 0 else TINTA_2)
            c.drawString(18 * mm, y, linea[:110])
            y -= 3.4 * mm
        x = 192 * mm
        for logo in reversed(logos):
            with PILImage.open(logo) as im:
                w, h = im.size
            alto = 14 * mm
            ancho = min(40 * mm, alto * w / h)
            alto = ancho * h / w
            c.drawImage(str(logo), x - ancho, 291 * mm - alto, ancho, alto, mask="auto", preserveAspectRatio=True)
            x -= ancho + 3 * mm
        c.setStrokeColor(LINEA)
        c.setLineWidth(0.6)
        c.line(18 * mm, 274 * mm, 192 * mm, 274 * mm)
        c.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
        c.setFont(NORMAL, 8)
        c.setFillColor(TINTA_2)
        if enc.pie:
            c.drawString(18 * mm, 10 * mm, enc.pie)
        c.restoreState()

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=(210 * mm, 297 * mm), leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=28 * mm, bottomMargin=20 * mm, title=t["titulo"], author=cab.lineas_izquierda[0]
                            if cab.lineas_izquierda else "", creator="Encuestas OMR")
    doc.build(historia, onFirstPage=en_pagina, onLaterPages=en_pagina, canvasmaker=_CanvasNumerado)
    return destino
