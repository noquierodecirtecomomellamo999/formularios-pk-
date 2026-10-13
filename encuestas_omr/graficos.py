"""Gráficos de resultados (matplotlib → PNG) para el informe y la pantalla de resultados.

Criterios:
- Opciones ordenadas (con respuestas "favorables" definidas, p. ej. Muy bien → Mal):
  rampa de un solo tono azul, de oscuro (primera opción) a claro.
- Opciones sin orden (Sí/No/No lo sé, tratamientos...): paleta categórica en orden
  fijo; el color sigue a la opción, no a su posición en el ranking.
- Barras: un solo color (es una sola serie) con el valor en la punta.
- Quesitos solo con 6 porciones o menos; si hay más, se usan barras.
Las paletas están validadas (separación para daltonismo y contraste).
"""

from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from .analisis import ResumenPregunta, grafico_por_defecto, num, pct  # noqa: E402

# Paleta (fondo blanco del PDF)
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_SUAVE = "#898781"
REJILLA = "#e1e0d9"
EJE = "#c3c2b7"
GRIS_EXTRA = "#c3c2b7"  # columnas no puntuables ("No usa", "NS/NC")
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SERIE = CATEGORICA[0]
RAMPAS = {  # rampas ordinales validadas (pasos de un mismo azul, de oscuro a claro)
    1: ["#2a78d6"],
    2: ["#104281", "#86b6ef"],
    3: ["#104281", "#2a78d6", "#86b6ef"],
    4: ["#104281", "#256abf", "#5598e7", "#86b6ef"],
    5: ["#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"],
}
ANCHO_IN = 6.3  # ≈ 16 cm, el ancho útil de un A4

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": EJE,
    "axes.labelcolor": TINTA_2,
    "xtick.color": TINTA_SUAVE,
    "ytick.color": TINTA_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def _texto_sobre(color_hex: str) -> str:
    """Blanco o tinta según la luminosidad del relleno."""
    r, g, b = (int(color_hex[i: i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "white" if lum < 0.5 else TINTA


def _corto(texto: str, n: int = 38) -> str:
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _guardar(fig, ruta: Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return ruta


# --------------------------------------------------------------------------- primitivas
def quesito(etiquetas: list[str], valores: list[int], colores: list[str], ruta: Path, titulo: str = "") -> Path:
    total = sum(valores)
    datos = [(e, v, c) for e, v, c in zip(etiquetas, valores, colores) if v > 0]
    fig, ax = plt.subplots(figsize=(ANCHO_IN, 2.5))
    cuñas, _ = ax.pie([v for _, v, _ in datos], colors=[c for _, _, c in datos], startangle=90, counterclock=False,
                      wedgeprops={"linewidth": 2, "edgecolor": "white"}, radius=1.0)
    # Porcentaje dentro de la porción solo si cabe y no choca con otro (de mayor a menor porción);
    # el valor siempre está en la leyenda y en la tabla.
    etiquetas = []
    for cuña, (_, v, c) in sorted(zip(cuñas, datos), key=lambda x: -x[1][1]):
        p = 100 * v / total
        if p < 8:
            continue
        ang = math.radians((cuña.theta1 + cuña.theta2) / 2)
        texto = ax.text(0.64 * math.cos(ang), 0.64 * math.sin(ang), pct(p), ha="center", va="center", fontsize=8,
                        color=_texto_sobre(c), fontweight="bold")
        etiquetas.append(texto)
    fig.canvas.draw()
    colocadas = []
    for texto in etiquetas:
        caja = texto.get_window_extent().expanded(1.35, 1.4)
        if any(caja.overlaps(otra) for otra in colocadas):
            texto.remove()
        else:
            colocadas.append(caja)
    ax.set_aspect("equal")
    leyenda = [Patch(facecolor=c, edgecolor="none", label=f"{_corto(e)}  ·  {v} ({pct(100 * v / total)})")
               for e, v, c in datos]
    ax.legend(handles=leyenda, loc="center left", bbox_to_anchor=(1.05, 0.5), frameon=False, fontsize=9,
              labelcolor=TINTA, handlelength=1.0, handleheight=1.0)
    if titulo:
        ax.set_title(titulo, fontsize=9.5, color=TINTA, loc="left")
    return _guardar(fig, ruta)


def barras_h(etiquetas: list[str], valores: list[float], textos: list[str], ruta: Path, xmax: float | None = None,
             xmin: float = 0.0, eje: str = "", colores: list[str] | None = None) -> Path:
    n = len(etiquetas)
    fig, ax = plt.subplots(figsize=(ANCHO_IN, 0.42 * n + 0.6))
    y = list(range(n))[::-1]
    ax.barh(y, [v - xmin for v in valores], left=xmin, height=0.56, color=colores or SERIE)
    tope = xmax if xmax is not None else max(valores + [1])
    for yy, v, t in zip(y, valores, textos):
        ax.text(v + (tope - xmin) * 0.012, yy, t, va="center", ha="left", fontsize=8.5, color=TINTA)
    ax.set_yticks(y)
    ax.set_yticklabels([_corto(e, 45) for e in etiquetas], fontsize=9, color=TINTA)
    ax.set_xlim(xmin, tope * 1.18 if xmax is None else xmax + (xmax - xmin) * 0.16)
    ax.xaxis.grid(True, color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0, labelsize=8)
    if eje:
        ax.set_xlabel(eje, fontsize=8.5, color=TINTA_2)
    return _guardar(fig, ruta)


def columnas(etiquetas: list[str], valores: list[float], textos: list[str], ruta: Path, eje: str = "",
             colores: list[str] | None = None) -> Path:
    n = len(etiquetas)
    fig, ax = plt.subplots(figsize=(ANCHO_IN, 2.4))
    x = list(range(n))
    ancho = 0.6 if n > 3 else 0.4
    ax.bar(x, valores, width=ancho, color=colores or SERIE)
    tope = max(valores + [1])
    for xx, v, t in zip(x, valores, textos):
        if v > 0:
            ax.text(xx, v + tope * 0.03, t, ha="center", va="bottom", fontsize=8, color=TINTA)
    ax.set_xticks(x)
    ax.set_xticklabels([_corto(e, 16) for e in etiquetas], fontsize=8.5 if n <= 8 else 8, color=TINTA)
    ax.set_ylim(0, tope * 1.22)
    ax.yaxis.grid(True, color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=8)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.get_major_locator().set_params(integer=True)
    if eje:
        ax.set_ylabel(eje, fontsize=8.5, color=TINTA_2)
    return _guardar(fig, ruta)


def quesitos_multiples(titulos: list[str], series: list[tuple[list[str], list[int], list[str]]], ruta: Path) -> Path:
    """Varios quesitos pequeños (uno por fila de una escala), con una leyenda común."""
    n = len(series)
    cols = min(3, n)
    filas = (n + cols - 1) // cols
    fig, ejes = plt.subplots(filas, cols, figsize=(ANCHO_IN, 2.0 * filas + 0.5), squeeze=False)
    leyenda: dict[str, str] = {}
    for k, ax in enumerate(ejes.flat):
        if k >= n:
            ax.axis("off")
            continue
        etqs, vals, cols_ = series[k]
        datos = [(e, v, c) for e, v, c in zip(etqs, vals, cols_) if v > 0]
        if datos:
            ax.pie([v for _, v, _ in datos], colors=[c for _, _, c in datos], startangle=90, counterclock=False,
                   wedgeprops={"linewidth": 1.5, "edgecolor": "white"})
        ax.set_aspect("equal")
        ax.set_title(_corto(titulos[k], 30), fontsize=8.5, color=TINTA)
        for e, _, c in datos:
            leyenda.setdefault(e, c)
    fig.legend(handles=[Patch(facecolor=c, label=e) for e, c in leyenda.items()], loc="lower center",
               ncol=min(8, len(leyenda)), frameon=False, fontsize=8, handlelength=1.0)
    fig.subplots_adjust(bottom=0.12)
    return _guardar(fig, ruta)


# --------------------------------------------------------------------------- por pregunta
def colores_opciones(r: ResumenPregunta) -> list[str] | None:
    """Colores por opción para un quesito, o None si no hay paleta adecuada (demasiadas opciones)."""
    e = r.elemento
    n = len(e.opciones)
    if e.tipo == "unica" and e.favorables and n in RAMPAS:
        return RAMPAS[n]
    if n <= len(CATEGORICA):
        return CATEGORICA[:n]
    return None


def _colores_escala(etiquetas_valor: list[str], puntos: list[float], n_extras: int, presentes: list[int]):
    """Colores para un quesito de puntuaciones: rampa por puntuación (alta = oscuro) y gris para extras."""
    valores_presentes = [k for k in presentes if k < len(puntos)]
    if len(valores_presentes) > 5:
        return None
    rampa = RAMPAS.get(len(valores_presentes), [])
    orden = sorted(valores_presentes, key=lambda k: -puntos[k])
    colores = {k: rampa[i] for i, k in enumerate(orden)}
    total = len(etiquetas_valor) + n_extras
    return [colores.get(k, GRIS_EXTRA) for k in range(total)]


def grafico(r: ResumenPregunta, ruta: Path, tipo: str | None = None) -> Path | None:
    """Genera el gráfico de una pregunta. Devuelve la ruta o None si no procede."""
    e = r.elemento
    tipo = grafico_por_defecto(r, tipo)
    if tipo == "ninguno" or r.n_validas == 0:
        return None
    if e.tipo in ("unica", "multiple"):
        etiquetas = [f.etiqueta for f in r.tabla]
        valores = [f.n for f in r.tabla]
        textos = [f"{f.n} ({pct(f.pct)})" for f in r.tabla]
        colores = colores_opciones(r)
        if tipo == "quesito" and e.tipo == "unica" and colores and sum(1 for v in valores if v) <= 6:
            return quesito(etiquetas, valores, colores, ruta)
        if tipo == "barras":
            return columnas(etiquetas, valores, textos, ruta, eje="Personas")
        return barras_h(etiquetas, valores, textos, ruta, eje="Personas")
    if e.tipo == "escala":
        puntos = e.puntuaciones()
        etq_cols = list(e.valores) + list(e.extras)
        if len(r.filas) == 1 or tipo == "quesito":
            if tipo == "quesito":
                series, titulos = [], []
                for f in r.filas:
                    presentes = [k for k, d in enumerate(f.distribucion) if d.n]
                    colores = _colores_escala(e.valores, puntos, len(e.extras), presentes)
                    if colores is None:
                        break
                    series.append((etq_cols, [d.n for d in f.distribucion], colores))
                    titulos.append(f"{f.etiqueta} (media {num(f.media)})" if f.media is not None else f.etiqueta)
                else:
                    if len(series) == 1:
                        return quesito(*series[0], ruta)
                    return quesitos_multiples(titulos, series, ruta)
            if len(r.filas) == 1:
                f = r.filas[0]
                colores = [SERIE] * len(e.valores) + [GRIS_EXTRA] * len(e.extras)
                return columnas(etq_cols, [d.n for d in f.distribucion], [str(d.n) for d in f.distribucion], ruta,
                                eje="Personas", colores=colores)
        filas = [f for f in r.filas if f.media is not None]
        if not filas:
            return None
        textos = [num(f.media) + (f"  ·  {pct(f.pct_umbral)} ≥ {num(r.umbral)}" if f.pct_umbral is not None else "")
                  for f in filas]
        return barras_h([f.etiqueta for f in filas], [f.media for f in filas], textos, ruta, xmax=puntos[-1],
                        xmin=min(0.0, puntos[0]), eje=f"Puntuación media (de {num(puntos[0])} a {num(puntos[-1])})")
    if e.tipo == "numero":
        if not r.numeros:
            return None
        lo, hi = min(r.numeros), max(r.numeros)
        if hi - lo <= 15:
            etiquetas = [str(v) for v in range(lo, hi + 1)]
            valores = [r.numeros.count(v) for v in range(lo, hi + 1)]
        else:
            paso = 5 if hi - lo <= 60 else 10
            inicio = lo - lo % paso
            etiquetas, valores = [], []
            for a in range(inicio, hi + 1, paso):
                etiquetas.append(f"{a}–{a + paso - 1}")
                valores.append(sum(1 for v in r.numeros if a <= v < a + paso))
        return columnas(etiquetas, valores, [str(v) for v in valores], ruta, eje="Personas")
    return None
