"""Consolidación: junta las páginas leídas en cuestionarios y aplica las revisiones manuales.

- Si las copias se imprimieron numeradas, las páginas se juntan por número de
  cuestionario (da igual el orden de escaneo).
- Si se fotocopió un máster sin numerar, se juntan por orden dentro de cada lote:
  una página 1 empieza un cuestionario nuevo.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .almacen import Almacen
from .lector import ResultadoCampo, ResultadoPagina
from .modelo import Encuesta


@dataclass
class RefPagina:
    lote: str
    posicion: int  # posición dentro del lote (0, 1, ...)
    resultado: ResultadoPagina
    hoja: int | None = None  # número de cuestionario (puede venir deducido de las páginas vecinas)


@dataclass
class Cuestionario:
    id: str
    hoja: int | None
    huella: str
    total_paginas: int
    paginas: dict[int, RefPagina] = field(default_factory=dict)

    @property
    def faltan(self) -> list[int]:
        return [i for i in range(self.total_paginas) if i not in self.paginas]


@dataclass
class Respuesta:
    pregunta: str
    tipo: str
    valor: Any = None
    estado: str = "ok"  # ok | dudoso | revisado | sin_datos
    motivo: str = ""
    escrito: bool = False  # abiertas: hay algo escrito
    texto: str = ""  # abiertas: transcripción
    especifique: dict = field(default_factory=dict)  # opción -> {"escrito": bool, "texto": str}


@dataclass
class ItemRevision:
    """Una casilla dudosa (o un texto escrito) que conviene comprobar a mano."""

    cuestionario: str
    pregunta: str
    clave: str  # clave del campo, o "texto:<opcion>" para textos
    ref: RefPagina
    campo: ResultadoCampo | None = None
    opcion: int | None = None
    tipo_texto: str = ""


@dataclass
class Consolidado:
    cuestionarios: list[Cuestionario]
    respuestas: dict[str, dict[str, Respuesta]]
    errores: list[RefPagina]
    avisos: list[str]
    dudas: list[ItemRevision]
    textos: list[ItemRevision]
    descartados: list[str]

    @property
    def validos(self) -> list[Cuestionario]:
        return [c for c in self.cuestionarios if c.id not in self.descartados]

    @property
    def dudas_pendientes(self) -> list[ItemRevision]:
        return [d for d in self.dudas if self.respuestas[d.cuestionario][d.pregunta].estado == "dudoso"
                and d.cuestionario not in self.descartados]


def clave_revision(cuestionario: str, clave: str) -> str:
    return f"{cuestionario}/{clave}"


def clave_texto(cuestionario: str, pregunta: str, opcion: int | None) -> str:
    return f"{cuestionario}/{pregunta}/{'' if opcion is None else opcion}"


# --------------------------------------------------------------------------- agrupación
def _paginas(almacen: Almacen, encuesta_id: str) -> list[RefPagina]:
    refs = []
    for meta in almacen.lotes(encuesta_id):
        for pos, res in enumerate(almacen.lectura(encuesta_id, meta["id"])):
            refs.append(RefPagina(meta["id"], pos, res, res.hoja if res.qr else None))
    return refs


def _deducir_hojas(refs: list[RefPagina]) -> None:
    """Una página sin QR legible hereda el número de la anterior o siguiente del mismo lote si encaja."""
    for k, r in enumerate(refs):
        if r.resultado.error or r.hoja is not None or r.resultado.indice is None:
            continue
        for vecino, salto in ((k - 1, 1), (k + 1, -1)):
            if 0 <= vecino < len(refs):
                v = refs[vecino]
                if (v.lote == r.lote and v.hoja and not v.resultado.error and v.resultado.huella == r.resultado.huella
                        and v.resultado.indice is not None and v.resultado.indice + salto == r.resultado.indice):
                    r.hoja = v.hoja
                    break


def agrupar(almacen: Almacen, encuesta_id: str) -> tuple[list[Cuestionario], list[RefPagina], list[str]]:
    refs = _paginas(almacen, encuesta_id)
    _deducir_hojas(refs)
    errores = [r for r in refs if r.resultado.error]
    avisos: list[str] = []
    total_paginas: dict[str, int] = {}

    def paginas_de(huella: str) -> int:
        if huella not in total_paginas:
            m = almacen.maqueta(encuesta_id, huella)
            total_paginas[huella] = len(m.paginas) if m else 1
        return total_paginas[huella]

    numerados: dict[int, Cuestionario] = {}
    orden: list[Cuestionario] = []
    actual: Cuestionario | None = None
    contador: dict[str, int] = defaultdict(int)
    for r in refs:
        if r.resultado.error:
            continue
        res, indice = r.resultado, r.resultado.indice
        if r.hoja:
            c = numerados.get(r.hoja)
            if c is None:
                c = Cuestionario(f"N{r.hoja:04d}", r.hoja, res.huella, paginas_de(res.huella))
                numerados[r.hoja] = c
                orden.append(c)
            if indice in c.paginas:
                avisos.append(f"La página {indice + 1} del cuestionario nº {r.hoja} está escaneada dos veces "
                              f"({c.paginas[indice].resultado.origen} y {res.origen}); se usa la primera.")
                continue
            c.paginas[indice] = r
            continue
        # Sin numerar: por orden dentro del lote
        nuevo = (actual is None or actual.hoja is not None or actual.paginas.get(min(actual.paginas)).lote != r.lote
                 or actual.huella != res.huella or indice in actual.paginas or indice < max(actual.paginas))
        if nuevo:
            contador[r.lote] += 1
            actual = Cuestionario(f"{r.lote}-{contador[r.lote]:03d}", None, res.huella, paginas_de(res.huella))
            orden.append(actual)
        actual.paginas[indice] = r
    for c in orden:
        if c.faltan:
            nombre = f"nº {c.hoja}" if c.hoja else c.id
            avisos.append(f"Al cuestionario {nombre} le faltan páginas: {', '.join(str(i + 1) for i in c.faltan)}.")
    return orden, errores, avisos


# --------------------------------------------------------------------------- respuestas
def _seleccion(cid: str, campo: ResultadoCampo, revisiones: dict) -> tuple[list[int], str, str]:
    k = clave_revision(cid, campo.clave)
    if k in revisiones["campos"]:
        return list(revisiones["campos"][k]), "revisado", ""
    return list(campo.seleccion), campo.estado, campo.motivo


def _peor(estados: list[str]) -> str:
    for e in ("dudoso", "revisado", "ok"):
        if e in estados:
            return e
    return "ok"


def construir_respuestas(enc: Encuesta, c: Cuestionario, revisiones: dict, preguntas_pagina: dict[int, set[str]]
                         ) -> dict[str, Respuesta]:
    campos: dict[str, list[ResultadoCampo]] = defaultdict(list)
    textos: dict[str, list] = defaultdict(list)
    for ref in c.paginas.values():
        for campo in ref.resultado.campos:
            campos[campo.pregunta].append(campo)
        for t in ref.resultado.textos:
            textos[t.pregunta].append(t)
    presentes = set()
    for indice in c.paginas:
        presentes |= preguntas_pagina.get(indice, set())

    salida: dict[str, Respuesta] = {}
    for e in enc.preguntas:
        r = Respuesta(e.id, e.tipo)
        salida[e.id] = r
        if e.id not in presentes:
            r.estado = "sin_datos"
            continue
        lista = sorted(campos.get(e.id, []), key=lambda x: (x.fila if x.fila is not None else -1))
        selecciones = [(x, *_seleccion(c.id, x, revisiones)) for x in lista]
        r.estado = _peor([s[2] for s in selecciones]) if selecciones else "ok"
        r.motivo = "; ".join(sorted({s[3] for s in selecciones if s[3]}))
        if e.tipo == "unica":
            sel = selecciones[0][1] if selecciones else []
            r.valor = sel[0] if len(sel) == 1 else None
        elif e.tipo == "multiple":
            r.valor = sorted(selecciones[0][1]) if selecciones else []
        elif e.tipo == "escala":
            r.valor = {x.fila: (sel[0] if len(sel) == 1 else None) for x, sel, _, _ in selecciones}
        elif e.tipo == "numero":
            cifras = [sel for _, sel, _, _ in selecciones]
            r.valor = _numero(cifras)
            if r.valor is None and any(cifras) and r.estado == "ok":
                r.estado, r.motivo = "dudoso", "número incompleto"
        elif e.tipo == "abierta":
            ts = [t for t in textos.get(e.id, []) if t.tipo == "texto_libre"]
            r.escrito = any(t.escrito for t in ts)
            r.texto = revisiones["textos"].get(clave_texto(c.id, e.id, None), "")
            r.valor = r.texto or None
            r.estado = "ok"
        for t in textos.get(e.id, []):
            if t.tipo == "especifique":
                r.especifique[t.opcion] = {
                    "escrito": t.escrito, "texto": revisiones["textos"].get(clave_texto(c.id, e.id, t.opcion), "")}
    return salida


def _numero(cifras: list[list[int]]) -> int | None:
    """[[], [7], [2]] -> 72. Las cifras en blanco solo se admiten a la izquierda."""
    digitos = []
    empezado = False
    for sel in cifras:
        if not sel:
            if empezado:
                return None
            continue
        if len(sel) > 1:
            return None
        empezado = True
        digitos.append(str(sel[0]))
    return int("".join(digitos)) if digitos else None


def consolidar(almacen: Almacen, encuesta_id: str, enc: Encuesta | None = None) -> Consolidado:
    enc = enc or almacen.cargar(encuesta_id)
    revisiones = almacen.revisiones(encuesta_id)
    cuestionarios, errores, avisos = agrupar(almacen, encuesta_id)
    maquetas: dict[str, dict[int, set[str]]] = {}
    respuestas: dict[str, dict[str, Respuesta]] = {}
    dudas: list[ItemRevision] = []
    textos: list[ItemRevision] = []
    for c in cuestionarios:
        if c.huella not in maquetas:
            m = almacen.maqueta(encuesta_id, c.huella)
            mapa: dict[int, set[str]] = {}
            if m:
                for p in m.paginas:
                    mapa[p.indice] = {x["pregunta"] for x in p.campos} | {z["pregunta"] for z in p.zonas}
            maquetas[c.huella] = mapa
        respuestas[c.id] = construir_respuestas(enc, c, revisiones, maquetas[c.huella])
        for indice, ref in sorted(c.paginas.items()):
            for campo in ref.resultado.campos:
                if campo.estado == "dudoso" or clave_revision(c.id, campo.clave) in revisiones["campos"]:
                    dudas.append(ItemRevision(c.id, campo.pregunta, campo.clave, ref, campo))
            for t in ref.resultado.textos:
                if t.escrito:
                    textos.append(ItemRevision(c.id, t.pregunta, f"texto:{t.opcion}", ref, opcion=t.opcion,
                                               tipo_texto=t.tipo))
    return Consolidado(cuestionarios, respuestas, errores, avisos, dudas, textos, list(revisiones["descartados"]))
