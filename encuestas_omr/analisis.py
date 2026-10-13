"""Análisis de resultados: frecuencias, porcentajes, medias y frases de resumen."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .modelo import Elemento, Encuesta
from .resultados import Consolidado


# --------------------------------------------------------------------------- formato numérico (es-ES)
def num(x: float, decimales: int = 2) -> str:
    """8.95 -> '8,95'; 9.0 -> '9'."""
    if x is None:
        return "–"
    s = f"{x:.{decimales}f}".rstrip("0").rstrip(".") if decimales else f"{x:.0f}"
    return s.replace(".", ",")


def pct(p: float | None) -> str:
    """Porcentaje con un decimal como máximo: 86.36 -> '86,4 %', 84.0 -> '84 %'."""
    if p is None:
        return "–"
    return f"{num(round(p, 1), 1)} %"


def _lista_y(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " o " + items[-1]


# --------------------------------------------------------------------------- estructuras
@dataclass
class Fila:
    etiqueta: str
    n: int
    pct: float | None

    @property
    def nombre(self) -> str:
        """Etiqueta para usar dentro de una frase: sin los dos puntos finales de "Sí, ¿cuál?:"."""
        return self.etiqueta.rstrip(": ").strip()


@dataclass
class ResumenFilaEscala:
    etiqueta: str
    n: int  # respuestas con puntuación
    n_extras: int  # "No usa", "NS/NC"...
    n_blanco: int
    media: float | None
    mediana: float | None
    pct_umbral: float | None
    distribucion: list[Fila]  # una por columna (valores + extras), % sobre respuestas


@dataclass
class ResumenPregunta:
    elemento: Elemento
    n_total: int = 0  # cuestionarios que tienen esta pregunta
    n_validas: int = 0  # han respondido
    n_blanco: int = 0
    n_dudosas: int = 0  # dudas sin revisar incluidas en el recuento
    tabla: list[Fila] = field(default_factory=list)
    filas: list[ResumenFilaEscala] = field(default_factory=list)
    numeros: list[int] = field(default_factory=list)
    textos: list[str] = field(default_factory=list)
    n_escritos: int = 0
    especifique: list[str] = field(default_factory=list)
    n_especifique_sin_transcribir: int = 0
    frase: str = ""
    destacado: str = ""  # frase corta para las conclusiones

    @property
    def umbral(self) -> float | None:
        e = self.elemento
        if e.tipo != "escala":
            return None
        if e.umbral is not None:
            return e.umbral
        p = e.puntuaciones()
        return p[0] + (p[-1] - p[0]) * 0.75 if p else None


# --------------------------------------------------------------------------- cálculo
def resumir(enc: Encuesta, cons: Consolidado) -> list[ResumenPregunta]:
    validos = [c.id for c in cons.validos]
    resumenes = []
    for e in enc.preguntas:
        r = ResumenPregunta(e)
        respuestas = [cons.respuestas[cid][e.id] for cid in validos if e.id in cons.respuestas.get(cid, {})]
        respuestas = [x for x in respuestas if x.estado != "sin_datos"]
        r.n_total = len(respuestas)
        r.n_dudosas = sum(1 for x in respuestas if x.estado == "dudoso")
        if e.tipo == "unica":
            cuenta = [0] * len(e.opciones)
            for x in respuestas:
                if x.valor is not None:
                    cuenta[x.valor] += 1
            r.n_validas = sum(cuenta)
            r.n_blanco = r.n_total - r.n_validas
            r.tabla = [Fila(o, n, 100 * n / r.n_validas if r.n_validas else None) for o, n in zip(e.opciones, cuenta)]
        elif e.tipo == "multiple":
            cuenta = [0] * len(e.opciones)
            for x in respuestas:
                for k in x.valor or []:
                    cuenta[k] += 1
            r.n_validas = sum(1 for x in respuestas if x.valor)
            r.n_blanco = r.n_total - r.n_validas
            r.tabla = [Fila(o, n, 100 * n / r.n_validas if r.n_validas else None) for o, n in zip(e.opciones, cuenta)]
        elif e.tipo == "escala":
            r.filas = _resumir_escala(e, respuestas, r.umbral)
            r.n_validas = max((f.n + f.n_extras for f in r.filas), default=0)
            r.n_blanco = r.n_total - r.n_validas
        elif e.tipo == "numero":
            r.numeros = [x.valor for x in respuestas if x.valor is not None]
            r.n_validas = len(r.numeros)
            r.n_blanco = r.n_total - r.n_validas
        elif e.tipo == "abierta":
            r.n_escritos = sum(1 for x in respuestas if x.escrito or x.texto)
            r.textos = [x.texto for x in respuestas if x.texto]
            r.n_validas = r.n_escritos
        if e.tipo in ("unica", "multiple") and e.con_texto:
            for x in respuestas:
                for _, info in x.especifique.items():
                    if info.get("texto"):
                        r.especifique.append(info["texto"])
                    elif info.get("escrito"):
                        r.n_especifique_sin_transcribir += 1
        r.frase, r.destacado = frase_resultado(r)
        resumenes.append(r)
    return resumenes


def _resumir_escala(e: Elemento, respuestas, umbral) -> list[ResumenFilaEscala]:
    puntos = e.puntuaciones()
    nval = len(e.valores)
    filas = []
    for i, etq in enumerate(e.filas):
        cuenta = [0] * (nval + len(e.extras))
        blanco = 0
        for x in respuestas:
            v = (x.valor or {}).get(i)
            if v is None:
                blanco += 1
            else:
                cuenta[v] += 1
        n = sum(cuenta[:nval])
        n_extras = sum(cuenta[nval:])
        valores = [puntos[k] for k in range(nval) for _ in range(cuenta[k])]
        media = statistics.fmean(valores) if valores else None
        mediana = statistics.median(valores) if valores else None
        p_umbral = 100 * sum(1 for v in valores if v >= umbral) / n if (n and umbral is not None) else None
        total = n + n_extras
        etiquetas = list(e.valores) + list(e.extras)
        dist = [Fila(etiquetas[k], cuenta[k], 100 * cuenta[k] / total if total else None) for k in range(len(etiquetas))]
        filas.append(ResumenFilaEscala(etq or e.texto, n, n_extras, blanco, media, mediana, p_umbral, dist))
    return filas


# --------------------------------------------------------------------------- frases
def frase_resultado(r: ResumenPregunta) -> tuple[str, str]:
    """Frase de "Resultado:" para el informe y frase corta para las conclusiones."""
    e = r.elemento
    if r.n_total == 0:
        return "No hay respuestas para esta pregunta.", ""
    if e.tipo in ("unica", "multiple") and r.n_validas == 0:
        return "Nadie ha respondido a esta pregunta.", ""
    if e.tipo == "unica":
        con_datos = [f for f in r.tabla if f.n]
        if e.favorables:
            fav = [r.tabla[k] for k in e.favorables if k < len(r.tabla)]
            p_fav = 100 * sum(f.n for f in fav) / r.n_validas
            nombres = _lista_y([f"«{f.nombre}»" for f in fav])
            frase = f"El {pct(p_fav)} de las personas que responden elige {nombres}."
            resto = [f for f in con_datos if f not in fav]
            if resto:
                partes = [f"un {pct(f.pct)} «{f.nombre}»" for f in resto]
                resto_txt = ", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else partes[0]
                frase += " " + resto_txt[0].upper() + resto_txt[1:] + "."
            else:
                frase += " No hay ninguna otra respuesta."
            destacado = f"{pct(p_fav)}: {nombres}"
            return frase, destacado
        orden = sorted(con_datos, key=lambda f: -f.n)
        frase = f"La respuesta más frecuente es «{orden[0].nombre}» ({pct(orden[0].pct)})"
        if len(orden) > 1:
            frase += f", seguida de «{orden[1].nombre}» ({pct(orden[1].pct)})"
        return frase + ".", f"{pct(orden[0].pct)}: «{orden[0].nombre}»"
    if e.tipo == "multiple":
        orden = sorted([f for f in r.tabla if f.n], key=lambda f: -f.n)
        frase = (f"La opción más marcada es «{orden[0].nombre}» ({pct(orden[0].pct)} de las personas que "
                 f"responden)")
        if len(orden) > 1:
            frase += f", seguida de «{orden[1].nombre}» ({pct(orden[1].pct)})"
        frase += ". Cada persona puede marcar varias opciones, así que los porcentajes no suman 100."
        return frase, f"{pct(orden[0].pct)}: «{orden[0].nombre}»"
    if e.tipo == "escala":
        con_media = [f for f in r.filas if f.media is not None]
        if not con_media:
            return "Nadie ha puntuado esta pregunta.", ""
        maximo = e.puntuaciones()[-1]
        u = r.umbral
        if len(con_media) == 1:
            f = con_media[0]
            frase = f"Puntuación media: {num(f.media)} sobre {num(maximo)}."
            if f.pct_umbral is not None:
                frase += f" El {pct(f.pct_umbral)} puntúa {num(u)} o más."
            return frase, f"media {num(f.media)} sobre {num(maximo)}"
        alta = max(con_media, key=lambda f: f.media)
        baja = min(con_media, key=lambda f: f.media)
        minimo = min(f.media for f in con_media)
        if u is not None and minimo >= u:
            frase = f"Todos los aspectos valorados obtienen una media de {num(u)} o más sobre {num(maximo)}. "
        else:
            frase = ""
        frase += (f"La media más alta es la de «{alta.etiqueta}» ({num(alta.media)}) y la más baja la de "
                  f"«{baja.etiqueta}» ({num(baja.media)}).")
        return frase, f"medias entre {num(baja.media)} y {num(alta.media)} sobre {num(maximo)}"
    if e.tipo == "numero":
        if not r.numeros:
            return "Nadie ha respondido a esta pregunta.", ""
        m = statistics.fmean(r.numeros)
        frase = (f"Media: {num(m, 1)} (mínimo {min(r.numeros)}, máximo {max(r.numeros)}, "
                 f"mediana {num(statistics.median(r.numeros), 1)}).")
        return frase, f"media {num(m, 1)}"
    if e.tipo == "abierta":
        if not r.n_escritos:
            return "Nadie ha escrito nada en esta pregunta.", ""
        personas = "persona ha" if r.n_escritos == 1 else "personas han"
        return f"{r.n_escritos} {personas} escrito una respuesta.", ""
    return "", ""


def conclusiones_automaticas(resumenes: list[ResumenPregunta]) -> str:
    """Lista de puntos clave, como base para el apartado de conclusiones (el usuario puede editarla)."""
    lineas = []
    for r in resumenes:
        if r.destacado and r.elemento.tipo in ("unica", "escala") and (r.elemento.favorables or r.elemento.tipo == "escala"):
            texto = r.elemento.texto.rstrip(":").rstrip()
            lineas.append(f"- {r.elemento.numero} {texto} → {r.destacado}.".replace("  ", " "))
    return "\n".join(lineas)


def grafico_por_defecto(r: ResumenPregunta, elegido: str | None = None) -> str:
    """Tipo de gráfico a usar: el elegido (o el guardado en la pregunta) o, si es «auto», el más adecuado."""
    e = r.elemento
    elegido = elegido or e.grafico or "auto"
    if elegido != "auto":
        return elegido
    if e.tipo == "unica":
        return "quesito" if len(e.opciones) <= 5 else "barras_h"
    if e.tipo == "multiple":
        return "barras_h"
    if e.tipo == "escala":
        return "barras_h" if len(e.filas) > 1 else "barras"
    if e.tipo == "numero":
        return "barras"
    return "ninguno"
