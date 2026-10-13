"""Procesado de un lote de escaneos: lee cada página y guarda imágenes y resultados."""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np

from .almacen import Almacen
from .lector import Lector, ResultadoPagina, paginas_de_archivo


def contar_paginas(almacen: Almacen, encuesta_id: str, lote: str) -> int:
    import pypdfium2 as pdfium

    total = 0
    for ruta in sorted((almacen.ruta_lote(encuesta_id, lote) / "originales").iterdir()):
        if ruta.suffix.lower() == ".pdf":
            pdf = pdfium.PdfDocument(str(ruta))
            total += len(pdf)
            pdf.close()
        else:
            total += 1
    return total


def procesar_lote(almacen: Almacen, encuesta_id: str, lote: str,
                  progreso: Callable[[int, int, str], None] | None = None) -> list[ResultadoPagina]:
    """Lee todas las páginas de los archivos del lote y guarda los resultados."""
    base = almacen.ruta_lote(encuesta_id, lote)
    dir_paginas = base / "paginas"
    dir_paginas.mkdir(parents=True, exist_ok=True)

    def buscar(huella: str):
        return almacen.maqueta(encuesta_id, huella)

    huellas = almacen.huellas(encuesta_id)
    por_defecto = almacen.maqueta(encuesta_id, huellas[-1]) if huellas else almacen.maqueta_actual(encuesta_id)
    lector = Lector(buscar, por_defecto, almacen.ruta(encuesta_id) / "cache_omr")

    total = contar_paginas(almacen, encuesta_id, lote)
    resultados: list[ResultadoPagina] = []
    for ruta in sorted((base / "originales").iterdir()):
        try:
            paginas = list(paginas_de_archivo(ruta))
        except Exception as e:  # archivo dañado o formato no admitido
            resultados.append(ResultadoPagina(origen=ruta.name, error=f"No se puede abrir el archivo: {e}"))
            continue
        for descripcion, gris in paginas:
            n = len(resultados) + 1
            if progreso:
                progreso(n, total, descripcion)
            try:
                res, normal = lector.leer_pagina(gris, descripcion)
            except Exception as e:  # nunca debe parar todo el lote por una hoja
                res, normal = ResultadoPagina(origen=descripcion, error=f"Error inesperado al leer: {e}"), None
            nombre = f"{n:04d}.jpg"
            imagen = normal if normal is not None else _miniatura(gris)
            cv2.imwrite(str(dir_paginas / nombre), imagen, [cv2.IMWRITE_JPEG_QUALITY, 82])
            res.imagen = f"paginas/{nombre}"
            if res.error and res.huella and not res.campos:
                otra = almacen.buscar_maqueta(res.huella)
                if otra and otra[0] != encuesta_id:
                    titulo = otra[1].encuesta.get("titulo", "")
                    sub = otra[1].encuesta.get("subtitulo", "")
                    res.error = f"Esta hoja es de otra encuesta: «{titulo} {sub}». Súbala en esa encuesta."
            resultados.append(res)
    almacen.guardar_lectura(encuesta_id, lote, resultados)
    return resultados


def _miniatura(gris: np.ndarray) -> np.ndarray:
    h, w = gris.shape[:2]
    f = 1600 / max(h, w)
    return cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else gris
