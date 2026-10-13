"""Marcadores de esquina (ArUco) y código QR de cada hoja.

Cada página lleva 4 marcadores ArUco distintos (ids 4·p … 4·p+3 para la página p),
de modo que, aunque el QR no se pueda leer, se sabe qué página es y cómo está
girada. El QR identifica la versión impresa de la encuesta (huella), la página y el
número de hoja (para juntar las páginas de un mismo cuestionario).
"""

from __future__ import annotations

import cv2
import numpy as np

from .maquetacion import MARCA_MM, MARCAS_MM, MAX_PAGINAS, PX_MM, QR_MM, QR_TAM_MM

DICCIONARIO = cv2.aruco.DICT_4X4_50
PREFIJO_QR = "E1"  # contenido corto y en mayúsculas: QR más pequeño (versión 1) y robusto


def diccionario():
    return cv2.aruco.getPredefinedDictionary(DICCIONARIO)


def ids_pagina(indice: int) -> list[int]:
    """Ids de los marcadores de una página: sup-izq, sup-der, inf-der, inf-izq."""
    if not 0 <= indice < MAX_PAGINAS:
        raise ValueError(f"Página fuera de rango: {indice}")
    return [4 * indice + k for k in range(4)]


def bits_marcador(id_marcador: int) -> np.ndarray:
    """Matriz 6x6 (con el borde) donde 1 = celda negra."""
    img = cv2.aruco.generateImageMarker(diccionario(), id_marcador, 6, borderBits=1)
    return (img < 128).astype(np.uint8)


def texto_qr(huella: str, indice_pagina: int, hoja: int) -> str:
    return f"{PREFIJO_QR}:{huella.upper()}:{indice_pagina + 1}:{hoja}"


def interpretar_qr(texto: str) -> tuple[str, int, int] | None:
    """'E1:A1B2C3D4:2:15' -> ('a1b2c3d4', 1, 15). Devuelve None si no es un QR de este programa."""
    partes = (texto or "").strip().split(":")
    if len(partes) != 4 or partes[0] != PREFIJO_QR:
        return None
    try:
        return partes[1].lower(), int(partes[2]) - 1, int(partes[3])
    except ValueError:
        return None


def esquinas_canonicas(indice_pagina: int) -> dict[int, np.ndarray]:
    """Posición (px de la imagen normalizada) de las 4 esquinas de cada marcador de la página."""
    s = MARCA_MM * PX_MM
    res = {}
    for k, id_m in enumerate(ids_pagina(indice_pagina)):
        x, y = MARCAS_MM[k][0] * PX_MM, MARCAS_MM[k][1] * PX_MM
        res[id_m] = np.array([[x, y], [x + s, y], [x + s, y + s], [x, y + s]], dtype=np.float32)
    return res


def _detector():
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.adaptiveThreshWinSizeMax = 53
    params.adaptiveThreshWinSizeStep = 6
    return cv2.aruco.ArucoDetector(diccionario(), params)


def detectar_marcadores(gris: np.ndarray) -> dict[int, np.ndarray]:
    """Devuelve {id: esquinas 4x2} de los marcadores encontrados en la imagen."""
    esquinas, ids, _ = _detector().detectMarkers(gris)
    encontrados: dict[int, np.ndarray] = {}
    if ids is None:
        return encontrados
    for c, i in zip(esquinas, ids.flatten()):
        i = int(i)
        if i < 4 * MAX_PAGINAS and i not in encontrados:
            encontrados[i] = c.reshape(4, 2).astype(np.float32)
    return encontrados


def leer_qr(pagina_normalizada: np.ndarray) -> tuple[str, int, int] | None:
    """Lee el QR en su posición conocida dentro de la página ya enderezada."""
    m = 4 * PX_MM
    x0 = int(QR_MM[0] * PX_MM - m)
    y0 = int(QR_MM[1] * PX_MM - m)
    lado = int(QR_TAM_MM * PX_MM + 2 * m)
    h, w = pagina_normalizada.shape[:2]
    recorte = pagina_normalizada[max(0, y0): min(h, y0 + lado), max(0, x0): min(w, x0 + lado)]
    if recorte.size == 0:
        return None
    detector = cv2.QRCodeDetector()
    for escala in (2.0, 3.0, 1.0):
        img = cv2.resize(recorte, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
        _, binaria = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        for candidata in (img, binaria):
            try:
                texto, _, _ = detector.detectAndDecode(candidata)
            except cv2.error:
                texto = ""
            datos = interpretar_qr(texto)
            if datos:
                return datos
    return None
