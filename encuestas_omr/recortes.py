"""Recortes de las páginas escaneadas (para revisar dudas y ver los textos escritos a mano)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .almacen import Almacen
from .lector import ResultadoCampo
from .maquetacion import CASILLA_MM, MEDIDA_PX, PX_MM, Maqueta
from .resultados import RefPagina

_MARGEN = (CASILLA_MM * PX_MM - MEDIDA_PX) / 2


@lru_cache(maxsize=64)
def _leer_imagen(ruta: str, _mtime: float) -> np.ndarray | None:
    datos = np.fromfile(ruta, dtype=np.uint8)
    return cv2.imdecode(datos, cv2.IMREAD_GRAYSCALE) if datos.size else None


def imagen_pagina(almacen: Almacen, encuesta_id: str, ref: RefPagina) -> np.ndarray | None:
    ruta = almacen.ruta_lote(encuesta_id, ref.lote) / ref.resultado.imagen
    if not ruta.exists():
        return None
    return _leer_imagen(str(ruta), ruta.stat().st_mtime)


def zona(maqueta: Maqueta, indice: int, pregunta: str, tipo: str = "pregunta", opcion=None) -> list[float] | None:
    for z in maqueta.paginas[indice].zonas:
        if z["pregunta"] == pregunta and z["tipo"] == tipo and (opcion is None or z.get("opcion") == opcion):
            return z["rect"]
    return None


def recortar(img: np.ndarray, rect_mm: list[float], margen_mm: float = 1.5) -> np.ndarray:
    x0, y0, x1, y1 = rect_mm
    h, w = img.shape[:2]
    a = [int((x0 - margen_mm) * PX_MM), int((y0 - margen_mm) * PX_MM), int((x1 + margen_mm) * PX_MM),
         int((y1 + margen_mm) * PX_MM)]
    a = [max(0, a[0]), max(0, a[1]), min(w, a[2]), min(h, a[3])]
    return img[a[1]: a[3], a[0]: a[2]]


def recorte_pregunta(almacen: Almacen, encuesta_id: str, ref: RefPagina, pregunta: str,
                     campos_resaltados: list[tuple[dict, ResultadoCampo]] | None = None) -> np.ndarray | None:
    """Recorte en color de una pregunta, con las casillas detectadas marcadas en verde (y las anuladas en gris)."""
    img = imagen_pagina(almacen, encuesta_id, ref)
    if img is None or ref.resultado.indice is None:
        return None
    m = almacen.maqueta(encuesta_id, ref.resultado.huella)
    if m is None:
        return None
    rect = zona(m, ref.resultado.indice, pregunta)
    color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for campo_maqueta, resultado in campos_resaltados or []:
        dx, dy = resultado.desplazamiento
        for k, (x, y) in enumerate(campo_maqueta["casillas"]):
            x0, y0 = int(x - _MARGEN + dx), int(y - _MARGEN + dy)
            lado = int(CASILLA_MM * PX_MM)
            if k in resultado.seleccion:
                cv2.rectangle(color, (x0 - 4, y0 - 4), (x0 + lado + 4, y0 + lado + 4), (40, 160, 40), 3)
            elif k in resultado.anuladas:
                cv2.rectangle(color, (x0 - 4, y0 - 4), (x0 + lado + 4, y0 + lado + 4), (150, 150, 150), 2)
    if rect is None:
        return cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
    return cv2.cvtColor(recortar(color, rect), cv2.COLOR_BGR2RGB)


def recorte_texto(almacen: Almacen, encuesta_id: str, ref: RefPagina, pregunta: str, tipo: str,
                  opcion) -> np.ndarray | None:
    img = imagen_pagina(almacen, encuesta_id, ref)
    if img is None or ref.resultado.indice is None:
        return None
    m = almacen.maqueta(encuesta_id, ref.resultado.huella)
    rect = zona(m, ref.resultado.indice, pregunta, tipo, opcion) if m else None
    return recortar(img, rect, margen_mm=0.5) if rect else None


def guardar_png(img: np.ndarray, ruta: Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", img)
    buf.tofile(str(ruta))
    return ruta
