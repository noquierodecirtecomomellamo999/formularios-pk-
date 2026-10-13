"""Importación de preguntas desde texto pegado o desde un documento de Word (.docx).

El resultado es una primera versión de la encuesta que luego se revisa en el editor.
Formato de texto reconocido (es el de los cuestionarios habituales):

    # 1. Bienvenida y ambiente del Centro      ← sección (empieza por #)
    1.1. ¿Cómo se siente acogido/a?           ← pregunta
    - Muy bien                                  ← opción (también ☐, □, [ ], *, •)
    - Bien
    Transporte: 0 1 2 3 4 5 6 7 8 9 10          ← fila de una tabla de valoración
    0 1 2 3 4 5 6 7 8 9 10                      ← escala de una sola fila
    7. Sugerencias:                             ← pregunta sin opciones = respuesta abierta
"""

from __future__ import annotations

import re
from pathlib import Path

from .modelo import Elemento, Encuesta, asignar_ids

_OPCION = re.compile(r"^\s*(?:[-*•·◦▪o]\s+|☐\s*|□\s*|\[\s?\]\s*|❑\s*)(.+)$")
_ESCALA = re.compile(r"^(.*?)[\s:.\-–]*((?:☐?\s*\d{1,2}\s+){2,}☐?\s*\d{1,2})\s*$")
_NUMERO = re.compile(r"^\s*((?:\d+\.)+\d*\.?|\d+\)|[a-zA-Z]\))\s+(.+)$")
_SUBRAYADO = re.compile(r"_{3,}")


_NEGATIVAS = re.compile(r"\b(mal|nunca|deficiente|negativo|peor|empeorad[oa]|nada|poco|insuficiente|"
                        r"insatisfech[oa]|inadecuad[oa]|aumentado)\b", re.I)


def _es_escala(numeros: list[int]) -> bool:
    return len(numeros) >= 3 and all(b - a == 1 for a, b in zip(numeros, numeros[1:]))


def _limpiar(texto: str) -> str:
    texto = _SUBRAYADO.sub("", texto)
    texto = texto.replace("✍️", "").replace("✍", "").replace("✅", "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", texto).strip()


def _frase(texto: str) -> str:
    """'MUY BIEN' -> 'Muy bien' (respeta siglas cortas como NS/NC)."""
    if texto.isupper() and "/" not in texto and sum(c.isalpha() for c in texto) >= 3:
        texto = texto.lower()
        return texto[:1].upper() + texto[1:]
    return texto


def _opcion(linea: str) -> str | None:
    m = _OPCION.match(linea)
    if not m:
        return None
    texto = m.group(1).strip()
    while True:  # "- ☐ Sí" -> "Sí"
        m2 = _OPCION.match(texto)
        if not m2:
            return texto
        texto = m2.group(1).strip()


def _fila_escala(linea: str) -> tuple[str, list[str]] | None:
    m = _ESCALA.match(linea)
    if not m:
        return None
    numeros = [int(x) for x in re.findall(r"\d{1,2}", m.group(2))]
    if not _es_escala(numeros):
        return None
    etiqueta = (_opcion(m.group(1)) or m.group(1)).strip(" :.-–☐")
    return _frase(etiqueta), [str(n) for n in numeros]


def _es_etiqueta_corta(linea: str) -> bool:
    return "?" not in linea and len(linea.split()) <= 6 and not _NUMERO.match(linea) and not _OPCION.match(linea)


def _preparar_lineas(texto: str) -> list[tuple[str, bool]]:
    """Limpia las líneas y une el formato "ETIQUETA" + "0 1 2 … 10" en una sola línea de escala.

    Devuelve (línea, era_solo_subrayado)."""
    crudas = [l for l in texto.splitlines()]
    res: list[tuple[str, bool]] = []
    i = 0
    while i < len(crudas):
        original = crudas[i]
        linea = _limpiar(original)
        solo_subrayado = not linea and bool(_SUBRAYADO.search(original))
        if linea and i + 1 < len(crudas) and _es_etiqueta_corta(linea):
            siguiente = _limpiar(crudas[i + 1])
            fila = _fila_escala(siguiente)
            if fila and not fila[0]:
                res.append((f"{linea}: {siguiente}", False))
                i += 2
                continue
        res.append((linea, solo_subrayado))
        i += 1
    return res


def desde_texto(texto: str, titulo: str = "Encuesta importada") -> Encuesta:
    enc = Encuesta(id="importada", titulo=titulo)
    actual: Elemento | None = None  # pregunta en construcción

    def cerrar():
        nonlocal actual
        if actual is None:
            return
        if actual.tipo == "pendiente":
            actual.tipo = "abierta"
            actual.lineas = 3
        if actual.tipo in ("unica", "multiple"):
            t = actual.texto.lower()
            if "más de una" in t or "varias" in t or "mas de una" in t:
                actual.tipo = "multiple"
            actual.opciones = [_frase(o) for o in actual.opciones]
            if (actual.tipo == "unica" and len(actual.opciones) >= 4 and not actual.con_texto
                    and _NEGATIVAS.search(actual.opciones[-1])):
                actual.favorables = [0, 1]
        if actual.tipo == "escala":
            actual.filas = [f for f in actual.filas if f] or [""]
            if actual.valores[0] == "0" and actual.valores[-1] == "10":
                actual.umbral = 8
        enc.elementos.append(actual)
        actual = None

    lineas = _preparar_lineas(texto)
    for k, (linea, solo_subrayado) in enumerate(lineas):
        if solo_subrayado:
            # Líneas para escribir tras un título de sección: respuesta abierta
            if actual is None and enc.elementos and enc.elementos[-1].tipo == "seccion":
                actual = Elemento("pendiente", texto="Escriba aquí sus comentarios:")
            continue
        if not linea or re.fullmatch(r"[-_=·.]+", linea):
            continue
        if re.match(r"^(fecha\s*:?\s*)$", linea, re.I):
            continue
        if re.match(r"^\s*(muchas\s+)?gracias\b", linea, re.I):
            cerrar()
            enc.despedida = linea
            continue
        if linea.startswith("#"):
            cerrar()
            enc.elementos.append(Elemento("seccion", texto=linea.lstrip("#").strip()))
            continue
        fila = _fila_escala(linea)
        if fila:
            etiqueta, valores = fila
            m_num = _NUMERO.match(etiqueta)
            es_pregunta = bool(m_num) or "?" in etiqueta
            if not es_pregunta and actual is not None and actual.tipo == "escala" and actual.valores == valores:
                actual.filas.append(etiqueta)
                continue
            if not es_pregunta and actual is not None and actual.tipo == "pendiente":
                actual.tipo, actual.valores, actual.filas = "escala", valores, [etiqueta]
                continue
            cerrar()
            if es_pregunta or len(etiqueta.split()) >= 6:
                # "6.3. Puntúe de 0 a 10 la calidad global: 0 1 2 … 10" -> pregunta de una sola fila
                numero, cuerpo = (m_num.group(1), m_num.group(2)) if m_num else ("", etiqueta)
                actual = Elemento("escala", numero=numero, texto=cuerpo, valores=valores, filas=[""])
            else:
                actual = Elemento("escala", texto="Valoración", valores=valores, filas=[etiqueta])
            continue
        op = _opcion(linea)
        if op is not None and actual is not None and actual.tipo in ("pendiente", "unica", "multiple"):
            if actual.tipo == "pendiente":
                actual.tipo = "unica"
            if re.search(r"especifique|¿\s*cu[aá]l|cu[aá]l\s*\?", op, re.I):
                actual.con_texto.append(len(actual.opciones))
            actual.opciones.append(op)
            continue
        # Subtítulo dentro de una tabla de valoración ("TRATAMIENTO QUE RECIBE"): se ignora
        if actual is not None and actual.tipo == "escala" and _es_etiqueta_corta(linea) and k + 1 < len(lineas):
            siguiente = _fila_escala(lineas[k + 1][0])
            if siguiente and siguiente[0] and siguiente[1] == actual.valores:
                continue
        # Nueva pregunta
        cerrar()
        m_num = _NUMERO.match(linea)
        numero, cuerpo = (m_num.group(1), m_num.group(2)) if m_num else ("", linea)
        actual = Elemento("pendiente", numero=numero, texto=cuerpo.strip())
    cerrar()
    # Un enunciado sin opciones seguido de a), b), c)... es un texto introductorio, no una pregunta abierta
    for i, e in enumerate(enc.elementos[:-1]):
        if e.tipo == "abierta" and re.match(r"^[a-zA-Z]\)$", enc.elementos[i + 1].numero or ""):
            e.tipo = "texto"
    for e in enc.elementos:
        if re.match(r"^[A-Z]\)$", e.numero or ""):
            e.numero = e.numero.lower()
    asignar_ids(enc)
    return enc


# --------------------------------------------------------------------------- Word
def _formatos_numeracion(doc) -> dict[tuple[str, str], str]:
    """{(numId, ilvl): 'bullet' | 'decimal' | ...} a partir de numbering.xml."""
    try:
        numbering = doc.part.numbering_part.element
    except (KeyError, AttributeError, NotImplementedError):
        return {}
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    w = "{%s}" % ns["w"]
    abstractos = {}
    for an in numbering.findall("w:abstractNum", ns):
        niveles = {}
        for lvl in an.findall("w:lvl", ns):
            fmt = lvl.find("w:numFmt", ns)
            niveles[lvl.get(w + "ilvl")] = fmt.get(w + "val") if fmt is not None else "decimal"
        abstractos[an.get(w + "abstractNumId")] = niveles
    res = {}
    for num in numbering.findall("w:num", ns):
        ref = num.find("w:abstractNumId", ns)
        if ref is None:
            continue
        for ilvl, fmt in abstractos.get(ref.get(w + "val"), {}).items():
            res[(num.get(w + "numId"), ilvl)] = fmt
    return res


def _numeracion_parrafo(p):
    """numPr del párrafo, o el heredado de su estilo (listas aplicadas con estilos como «List Number»)."""
    ppr = p._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return ppr.numPr
    estilo = p.style
    while estilo is not None:
        ppr = estilo.element.pPr
        if ppr is not None and ppr.numPr is not None:
            return ppr.numPr
        estilo = estilo.base_style
    return None


def docx_a_texto(ruta_o_bytes) -> str:
    """Convierte un .docx en el formato de texto que entiende :func:`desde_texto`."""
    import io

    import docx

    fuente = io.BytesIO(ruta_o_bytes) if isinstance(ruta_o_bytes, (bytes, bytearray)) else str(ruta_o_bytes)
    doc = docx.Document(fuente)
    formatos = _formatos_numeracion(doc)
    contadores: dict[tuple[str, str], int] = {}
    lineas = []
    for p in doc.paragraphs:
        texto = re.sub(r"\s*\n\s*", " ", p.text).strip()
        if not texto:
            continue
        numpr = _numeracion_parrafo(p)
        negrita = bool(p.runs) and all(r.bold for r in p.runs if r.text.strip())
        if numpr is not None and numpr.numId is not None:
            clave = (str(numpr.numId.val), str(numpr.ilvl.val if numpr.ilvl is not None else 0))
            fmt = formatos.get(clave, "bullet")
            if fmt == "bullet":
                lineas.append(f"- {texto}")
            else:
                contadores[clave] = contadores.get(clave, 0) + 1
                n = contadores[clave]
                marca = f"{chr(96 + n)})" if fmt.startswith("lower") else f"{n}."
                lineas.append(f"{marca} {texto}")
            continue
        # Títulos de sección: "1. Bienvenida..." en negrita y sin interrogación, con texto corto
        if negrita and re.match(r"^\d+\.\s+\S", texto) and "?" not in texto and len(texto) < 70:
            lineas.append(f"# {texto}")
            continue
        lineas.append(texto)
    return "\n".join(lineas)


def desde_docx(ruta_o_bytes, titulo: str | None = None) -> Encuesta:
    texto = docx_a_texto(ruta_o_bytes)
    primera = next((l for l in texto.splitlines() if l.strip()), "Encuesta importada")
    titulo = titulo or re.sub(r"\s*fecha\s*:?\s*$", "", primera, flags=re.I).strip() or "Encuesta importada"
    resto = "\n".join(texto.splitlines()[1:]) if not titulo or primera.startswith(titulo[:10]) else texto
    enc = desde_texto(resto, titulo=titulo)
    # El primer párrafo largo sin opciones suele ser la introducción
    if enc.elementos and enc.elementos[0].tipo == "abierta" and len(enc.elementos[0].texto) > 120:
        enc.introduccion = enc.elementos.pop(0).texto
    return enc


def importar_archivo(nombre: str, contenido: bytes) -> Encuesta:
    if Path(nombre).suffix.lower() == ".docx":
        return desde_docx(contenido)
    return desde_texto(contenido.decode("utf-8", errors="replace"), titulo=Path(nombre).stem)
