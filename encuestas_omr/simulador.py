"""Simulador de cuestionarios rellenados y escaneados.

Sirve para probar el programa sin imprimir nada: rellena al azar los PDF
generados (con X de bolígrafo, de lápiz, ticks, casillas anuladas...) y los
"escanea" con pequeños giros, desplazamientos y ruido.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .maquetacion import CASILLA_MM, MEDIDA_PX, PX_MM, Maqueta

_MARGEN = (CASILLA_MM * PX_MM - MEDIDA_PX) / 2


@dataclass
class EstiloMarca:
    tipo: str = "x"  # "x" | "tick" | "relleno" | "circulo"
    gris: int = 40  # 40 ≈ bolígrafo; 120-150 ≈ lápiz
    grosor_mm: float = 0.5
    tamano: float = 0.8  # tamaño relativo a la casilla
    temblor: float = 0.0  # mm de temblor en el trazo


ESTILOS = {
    "boligrafo": EstiloMarca("x", 40, 0.5, 0.85),
    "boligrafo_fino": EstiloMarca("x", 60, 0.3, 0.75),
    "lapiz": EstiloMarca("x", 135, 0.45, 0.8),
    "tick": EstiloMarca("tick", 50, 0.45, 0.8),
    "temblor": EstiloMarca("x", 50, 0.5, 1.1, temblor=0.5),
    "circulo": EstiloMarca("circulo", 50, 0.45, 0.9),
    # Casos difíciles
    "lapiz_claro": EstiloMarca("x", 170, 0.4, 0.8),
    "x_pequena": EstiloMarca("x", 50, 0.4, 0.45),
    "tick_lapiz": EstiloMarca("tick", 150, 0.35, 0.7),
}


def rasterizar_pdf(ruta: Path, dpi: int = 200) -> list[np.ndarray]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(ruta))
    try:
        imgs = []
        for i in range(len(pdf)):
            img = pdf[i].render(scale=dpi / 72, grayscale=True).to_numpy()
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            imgs.append(np.ascontiguousarray(img))
        return imgs
    finally:
        pdf.close()


def _trazo(img, puntos, gris, grosor_px, temblor_px, rng):
    pts = np.array(puntos, dtype=float)
    # Se subdivide el trazo para poder añadirle temblor
    finos = []
    for a, b in zip(pts[:-1], pts[1:]):
        for t in np.linspace(0, 1, 12, endpoint=False):
            finos.append(a + (b - a) * t)
    finos.append(pts[-1])
    finos = np.array(finos)
    if temblor_px:
        finos += rng.normal(0, temblor_px, finos.shape)
    cv2.polylines(img, [np.round(finos).astype(np.int32)], False, int(gris), max(1, int(round(grosor_px))),
                  lineType=cv2.LINE_AA)


def dibujar_marca(img: np.ndarray, cx: float, cy: float, lado_px: float, estilo: EstiloMarca, rng) -> None:
    """Dibuja una marca centrada en (cx, cy) sobre una imagen en gris."""
    r = lado_px * estilo.tamano / 2
    g = estilo.grosor_mm * lado_px / CASILLA_MM
    tem = estilo.temblor * lado_px / CASILLA_MM
    jx, jy = rng.normal(0, lado_px * 0.06, 2)
    cx, cy = cx + jx, cy + jy
    if estilo.tipo == "x":
        _trazo(img, [(cx - r, cy - r), (cx + r, cy + r)], estilo.gris, g, tem, rng)
        _trazo(img, [(cx + r, cy - r), (cx - r, cy + r)], estilo.gris, g, tem, rng)
    elif estilo.tipo == "tick":
        _trazo(img, [(cx - r, cy), (cx - r * 0.2, cy + r * 0.8), (cx + r, cy - r)], estilo.gris, g, tem, rng)
    elif estilo.tipo == "relleno":
        x0, y0 = int(cx - lado_px / 2 + 1), int(cy - lado_px / 2 + 1)
        x1, y1 = int(cx + lado_px / 2 - 1), int(cy + lado_px / 2 - 1)
        cv2.rectangle(img, (x0, y0), (x1, y1), int(estilo.gris), -1)
    elif estilo.tipo == "circulo":
        cv2.circle(img, (int(cx), int(cy)), int(r), int(estilo.gris), max(1, int(round(g))), lineType=cv2.LINE_AA)


def rellenar(paginas: list[np.ndarray], maqueta: Maqueta, respuestas: dict[str, list[int]], dpi: int,
             estilo: EstiloMarca, rng, anuladas: dict[str, list[int]] | None = None,
             textos: set[str] | None = None) -> list[np.ndarray]:
    """Marca las casillas indicadas: ``respuestas = {clave_campo: [índices]}``."""
    esc = dpi / 25.4 / PX_MM  # px de la imagen por px normalizado
    lado = CASILLA_MM * PX_MM * esc
    salida = []
    for img, pag in zip(paginas, maqueta.paginas):
        img = img.copy()
        for c in pag.campos:
            for k in respuestas.get(c["clave"], []):
                x, y = c["casillas"][k]
                cx = (x - _MARGEN + CASILLA_MM * PX_MM / 2) * esc
                cy = (y - _MARGEN + CASILLA_MM * PX_MM / 2) * esc
                dibujar_marca(img, cx, cy, lado, estilo, rng)
            for k in (anuladas or {}).get(c["clave"], []):
                x, y = c["casillas"][k]
                cx = (x - _MARGEN + CASILLA_MM * PX_MM / 2) * esc
                cy = (y - _MARGEN + CASILLA_MM * PX_MM / 2) * esc
                dibujar_marca(img, cx, cy, lado, EstiloMarca("relleno", estilo.gris), rng)
        for z in pag.zonas:
            if z["tipo"] in ("texto_libre", "especifique") and textos and f"{z['pregunta']}:{z.get('opcion')}" in textos:
                x0, y0, x1, y1 = (v * esc * PX_MM for v in z["rect"])
                y = y0 + (y1 - y0) * 0.55
                texto = "Mas actividades por la tarde" if z["tipo"] == "texto_libre" else "Musicoterapia"
                cv2.putText(img, texto, (int(x0 + 25 * esc), int(y)), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
                            1.1 * esc, int(estilo.gris), max(1, int(2 * esc)), cv2.LINE_AA)
        salida.append(img)
    return salida


def escanear(img: np.ndarray, rng, angulo: float = 0.0, desplazamiento=(0, 0), escala: float = 1.0,
             ruido: float = 4.0, desenfoque: float = 0.6, girar_180: bool = False) -> np.ndarray:
    """Simula un escaneo: giro, desplazamiento, cambio de escala, ruido y desenfoque."""
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, escala)
    m[:, 2] += desplazamiento
    out = cv2.warpAffine(img, m, (w, h), borderValue=255, flags=cv2.INTER_LINEAR)
    if desenfoque:
        out = cv2.GaussianBlur(out, (0, 0), desenfoque)
    if ruido:
        out = np.clip(out.astype(np.float32) * rng.uniform(0.9, 1.0) + rng.normal(0, ruido, out.shape), 0, 255)
        out = out.astype(np.uint8)
    if girar_180:
        out = cv2.rotate(out, cv2.ROTATE_180)
    return out


def guardar_pdf(imagenes: list[np.ndarray], ruta: Path, dpi: int = 200, calidad_jpeg: int = 80) -> Path:
    """Guarda las imágenes como un PDF de varias páginas (como el que genera un escáner)."""
    from PIL import Image

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pil = [Image.fromarray(i).convert("L") for i in imagenes]
    pil[0].save(ruta, "PDF", resolution=dpi, save_all=True, append_images=pil[1:], quality=calidad_jpeg)
    return ruta


def respuestas_aleatorias(maqueta: Maqueta, rng: random.Random, prob_blanco: float = 0.05) -> dict[str, list[int]]:
    """Elige una respuesta al azar para cada campo (varias en las preguntas de respuesta múltiple)."""
    res: dict[str, list[int]] = {}
    for pag in maqueta.paginas:
        for c in pag.campos:
            n = len(c["casillas"])
            if rng.random() < prob_blanco:
                res[c["clave"]] = []
            elif c["tipo"] == "multiple":
                k = rng.randint(1, min(3, n))
                res[c["clave"]] = sorted(rng.sample(range(n), k))
            else:
                # sesgo hacia las primeras opciones (las encuestas de satisfacción suelen salir positivas)
                pesos = [1.0 / (i + 1) for i in range(n)]
                res[c["clave"]] = [rng.choices(range(n), weights=pesos)[0]]
    return res
