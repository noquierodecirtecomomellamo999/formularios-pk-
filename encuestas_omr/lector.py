"""Lectura de hojas escaneadas.

Para cada página escaneada:

1. Se buscan los 4 marcadores de esquina (ArUco): dicen qué página es y permiten
   enderezarla (aunque esté torcida, girada 180º o escaneada a otra resolución).
2. Se lee el QR: versión impresa de la encuesta y número de cuestionario.
3. Se afina la posición de cada grupo de casillas buscando su borde impreso.
4. **OMRChecker** decide qué casillas están marcadas.
5. Como segunda comprobación se mide la proporción de tinta de cada casilla, que
   además distingue una X de una casilla rellena (anulada).
6. Si ambos coinciden, la respuesta se da por buena; si no, o si hay dobles
   marcas o marcas débiles, la pregunta queda como *dudosa* para revisarla a mano.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import cv2
import numpy as np

from .maquetacion import CASILLA_MM, MEDIDA_PX, PAGINA_PX, PX_MM, Maqueta
from .marcadores import detectar_marcadores, esquinas_canonicas, leer_qr
from .motor_omrchecker import PlantillaPagina

# Umbrales de la proporción de tinta dentro de una casilla (0-1)
TINTA_VACIA = 0.045  # por debajo: casilla vacía
TINTA_MARCA = 0.11  # por encima: casilla marcada con seguridad
TINTA_RELLENO = 0.80  # por encima: casilla rellena (anulada si hay otra marcada)

DPI_LECTURA = 200
_MARGEN_MEDIDA = (CASILLA_MM * PX_MM - MEDIDA_PX) / 2
_LADO_CASILLA_PX = int(round(CASILLA_MM * PX_MM))
_BUSQUEDA_PX = 7  # desplazamiento máximo que se busca al afinar cada grupo de casillas


# --------------------------------------------------------------------------- resultados
@dataclass
class ResultadoCampo:
    clave: str
    pregunta: str
    tipo: str
    fila: int | None
    omr: str  # letras que marcó OMRChecker
    tinta: list[float]
    seleccion: list[int]  # decisión final (índices de las casillas)
    estado: str  # "ok" | "dudoso"
    motivo: str = ""
    anuladas: list[int] = field(default_factory=list)
    desplazamiento: tuple[int, int] = (0, 0)


@dataclass
class ResultadoTexto:
    pregunta: str
    tipo: str  # "texto_libre" | "especifique"
    opcion: int | None
    escrito: bool
    tinta: int


@dataclass
class ResultadoPagina:
    origen: str  # "archivo.pdf, pág. 3"
    imagen: str = ""  # imagen enderezada guardada (ruta relativa al lote)
    huella: str | None = None
    indice: int | None = None  # página del cuestionario (0, 1, ...)
    hoja: int | None = None  # número de cuestionario impreso (0 = sin numerar)
    qr: bool = False
    marcadores: int = 0
    error: str = ""
    aviso: str = ""
    campos: list[ResultadoCampo] = field(default_factory=list)
    textos: list[ResultadoTexto] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ResultadoPagina:
        d = dict(d)
        d["campos"] = [ResultadoCampo(**{**c, "desplazamiento": tuple(c.get("desplazamiento", (0, 0)))})
                       for c in d.get("campos", [])]
        d["textos"] = [ResultadoTexto(**t) for t in d.get("textos", [])]
        return cls(**d)


# --------------------------------------------------------------------------- entrada de imágenes
def paginas_de_archivo(ruta: Path, dpi: int = DPI_LECTURA) -> Iterator[tuple[str, np.ndarray]]:
    """Devuelve (descripción, imagen en gris) de cada página de un PDF o imagen."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(ruta))
        try:
            for i in range(len(pdf)):
                pagina = pdf[i]
                img = pagina.render(scale=dpi / 72, grayscale=True).to_numpy()
                if img.ndim == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                yield f"{ruta.name}, pág. {i + 1}", np.ascontiguousarray(img)
        finally:
            pdf.close()
    else:
        datos = np.fromfile(str(ruta), dtype=np.uint8)  # admite rutas con tildes en Windows
        ok, multipagina = cv2.imdecodemulti(datos, cv2.IMREAD_GRAYSCALE)
        if ok and multipagina:
            for i, img in enumerate(multipagina):
                yield (f"{ruta.name}, pág. {i + 1}" if len(multipagina) > 1 else ruta.name), img
        else:
            raise ValueError(f"No se puede abrir la imagen {ruta.name}")


# --------------------------------------------------------------------------- enderezado
def enderezar(gris: np.ndarray) -> tuple[np.ndarray | None, int | None, int, str]:
    """Busca los marcadores y devuelve (página normalizada, índice de página, nº marcadores, error)."""
    marcas = detectar_marcadores(gris)
    if len(marcas) < 2:
        # Segundo intento con la imagen a otra escala (escaneos a muy alta o baja resolución)
        h, w = gris.shape[:2]
        factor = 1600.0 / max(h, w) if max(h, w) > 3200 else (2.0 if max(h, w) < 1400 else None)
        if factor:
            reesc = cv2.resize(gris, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
            marcas = {k: v / factor for k, v in detectar_marcadores(reesc).items()}
    if len(marcas) < 2:
        return None, None, len(marcas), "No se encuentran las marcas de las esquinas (¿es una hoja de esta aplicación?)."
    grupos: dict[int, list[int]] = {}
    for id_m in marcas:
        grupos.setdefault(id_m // 4, []).append(id_m)
    indice = max(grupos, key=lambda k: len(grupos[k]))
    ids = grupos[indice]
    if len(ids) < 2:
        return None, None, len(ids), "Solo se ha encontrado una marca de esquina; no se puede enderezar la hoja."
    canon = esquinas_canonicas(indice)
    origen = np.concatenate([marcas[i] for i in ids]).astype(np.float32)
    destino = np.concatenate([canon[i] for i in ids]).astype(np.float32)
    if len(ids) == 4:
        matriz, _ = cv2.findHomography(origen, destino, cv2.RANSAC, 4.0)
        normal = cv2.warpPerspective(gris, matriz, PAGINA_PX, flags=cv2.INTER_AREA, borderValue=255)
        proy = cv2.perspectiveTransform(origen.reshape(-1, 1, 2), matriz).reshape(-1, 2)
    else:
        if len(ids) == 3:
            matriz, _ = cv2.estimateAffine2D(origen, destino, method=cv2.RANSAC, ransacReprojThreshold=4.0)
        else:
            # Con solo dos marcadores, una transformación de semejanza (giro + escala + traslación),
            # que es lo que hace un escáner, extrapola mucho mejor al resto de la hoja.
            matriz, _ = cv2.estimateAffinePartial2D(origen, destino, method=cv2.RANSAC, ransacReprojThreshold=4.0)
        if matriz is None:
            return None, indice, len(ids), "No se ha podido calcular la posición de la hoja."
        normal = cv2.warpAffine(gris, matriz, PAGINA_PX, flags=cv2.INTER_AREA, borderValue=255)
        proy = cv2.transform(origen.reshape(-1, 1, 2), matriz).reshape(-1, 2)
    if matriz is None:
        return None, indice, len(ids), "No se ha podido calcular la posición de la hoja."
    error = float(np.median(np.linalg.norm(proy - destino, axis=1)))
    if error > 6.0:
        return None, indice, len(ids), f"Las marcas de esquina no encajan (error {error:.1f} px); hoja doblada o dañada."
    return normal, indice, len(ids), ""


# --------------------------------------------------------------------------- medidas
def nivel_papel(pagina: np.ndarray) -> float:
    return float(np.percentile(pagina, 80))


def _umbral_tinta(papel: float) -> float:
    return papel * 0.80


def ajustar_niveles(pagina: np.ndarray, papel: float) -> np.ndarray:
    """Estira el contraste para OMRChecker: el blanco del papel pasa a 255 y el gris de un lápiz
    suave queda claramente oscuro (equivale a su preprocesador "Levels")."""
    bajo, alto = papel - 110.0, papel - 15.0
    estirada = (pagina.astype(np.float32) - bajo) * (255.0 / (alto - bajo))
    return np.clip(estirada, 0, 255).astype(np.uint8)


def afinar_campo(pagina: np.ndarray, campo: dict) -> tuple[int, int]:
    """Busca el pequeño desplazamiento que mejor encaja los bordes impresos de las casillas del campo.

    Corrige pequeñas deformaciones del escaneo (papel que avanza irregular, etc.)
    que el enderezado general por las 4 esquinas no recoge.
    """
    casillas = np.array(campo["casillas"], dtype=float) - _MARGEN_MEDIDA  # esquina sup-izq de cada casilla
    x0, y0 = casillas.min(axis=0)
    x1, y1 = casillas.max(axis=0) + _LADO_CASILLA_PX
    pad, r = 4, _BUSQUEDA_PX
    ancho, alto = int(x1 - x0) + 2 * pad, int(y1 - y0) + 2 * pad
    plantilla = np.full((alto, ancho), 255, np.uint8)
    for cx, cy in casillas:
        px, py = int(round(cx - x0)) + pad, int(round(cy - y0)) + pad
        cv2.rectangle(plantilla, (px, py), (px + _LADO_CASILLA_PX - 1, py + _LADO_CASILLA_PX - 1), 0, 3)
    xa, ya = int(round(x0)) - pad - r, int(round(y0)) - pad - r
    h, w = pagina.shape
    if xa < 0 or ya < 0 or xa + ancho + 2 * r > w or ya + alto + 2 * r > h:
        return 0, 0
    zona = pagina[ya: ya + alto + 2 * r, xa: xa + ancho + 2 * r]
    plantilla = cv2.GaussianBlur(plantilla, (0, 0), 1.2)
    zona = cv2.GaussianBlur(zona, (0, 0), 1.2)
    res = cv2.matchTemplate(zona, plantilla, cv2.TM_CCOEFF_NORMED)
    _, maximo, _, pos = cv2.minMaxLoc(res)
    dx, dy = pos[0] - r, pos[1] - r
    # Sin un encaje claro, o si el máximo cae en el borde de la búsqueda, no se toca nada.
    if maximo < 0.3 or abs(dx) >= r or abs(dy) >= r or maximo - res[r, r] < 0.02:
        return 0, 0
    return dx, dy


def medir_tinta(pagina: np.ndarray, campo: dict, desp: tuple[int, int], umbral: float) -> list[float]:
    """Proporción de píxeles oscuros en el interior de cada casilla (0 = vacía, 1 = rellena)."""
    dx, dy = desp
    valores = []
    for x, y in campo["casillas"]:
        recorte = pagina[y + dy: y + dy + MEDIDA_PX, x + dx: x + dx + MEDIDA_PX]
        valores.append(float(np.mean(recorte < umbral)) if recorte.size else 0.0)
    return valores


def corregir_fondo(tintas: dict[str, list[float]]) -> dict[str, list[float]]:
    """Resta el nivel de una casilla vacía típica de la página.

    Con escaneos borrosos o de baja resolución el borde impreso "mancha" un poco
    el interior de todas las casillas; como la mayoría de casillas de una página
    están vacías, un percentil bajo de todas ellas da ese nivel de fondo.
    """
    todos = [t for vals in tintas.values() for t in vals]
    if len(todos) < 8:
        return {k: [round(t, 4) for t in v] for k, v in tintas.items()}
    fondo = min(float(np.percentile(todos, 25)), 0.3)
    return {k: [round(max(0.0, (t - fondo) / (1 - fondo)), 4) for t in v] for k, v in tintas.items()}


def tinta_texto(pagina: np.ndarray, rect_mm: list[float], umbral: float) -> int:
    """Píxeles de escritura a mano en una zona de texto libre (sin contar líneas ni bordes impresos)."""
    x0, y0, x1, y1 = (int(round(v * PX_MM)) for v in rect_mm)
    m = 10
    zona = pagina[max(0, y0 + m): y1 - m, max(0, x0 + m): x1 - m]
    if zona.size == 0:
        return 0
    tinta = (zona < umbral).astype(np.uint8)
    horiz = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (70, 1)))
    vert = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 70)))
    lineas = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((5, 5), np.uint8))
    resto = cv2.bitwise_and(tinta, cv2.bitwise_not(lineas))
    resto = cv2.morphologyEx(resto, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))  # quita motas sueltas
    return int(resto.sum())


# --------------------------------------------------------------------------- decisión
def decidir(tipo: str, omr: str, tinta: list[float]) -> tuple[list[int], str, str, list[int]]:
    """Combina OMRChecker y la medida de tinta. Devuelve (selección, estado, motivo, anuladas)."""
    n = len(tinta)
    por_omr = {ord(ch) - 65 for ch in omr if "A" <= ch <= "Z" and ord(ch) - 65 < n}
    rellenas = [k for k in range(n) if tinta[k] >= TINTA_RELLENO]
    marcadas = [k for k in range(n) if TINTA_MARCA <= tinta[k] < TINTA_RELLENO]
    debiles = [k for k in range(n) if TINTA_VACIA <= tinta[k] < TINTA_MARCA]

    if tipo == "multiple":
        if marcadas:
            seleccion, anuladas = marcadas, rellenas
        else:
            seleccion, anuladas = rellenas, []
        motivos = []
        if debiles:
            motivos.append("marca débil")
        if rellenas and marcadas:
            motivos.append("casilla rellena (¿anulada?)")
        desacuerdo = (por_omr - set(rellenas)) != set(marcadas) if marcadas else por_omr != set(seleccion)
        if desacuerdo:
            motivos.append("los dos métodos de lectura no coinciden")
        return sorted(seleccion), ("dudoso" if motivos else "ok"), "; ".join(motivos), anuladas

    # Respuesta única (pregunta, fila de una escala o cifra de un número)
    anuladas: list[int] = []
    if len(marcadas) == 1:
        seleccion, anuladas = marcadas, rellenas
    elif not marcadas and len(rellenas) == 1:
        seleccion = rellenas
    elif not marcadas and not rellenas:
        seleccion = []
    else:
        seleccion = sorted(marcadas or rellenas)
    motivos = []
    if len(seleccion) > 1:
        motivos.append("más de una casilla marcada")
    if debiles:
        motivos.append("marca débil" if seleccion else "marca débil o borrón")
    esperado_omr = set(seleccion) | set(anuladas)
    if anuladas and len(seleccion) == 1:
        # Corrección: OMRChecker suele quedarse con la casilla rellena (la más oscura);
        # basta con que no vea marcas fuera de la X y de las anuladas.
        if not por_omr or por_omr - esperado_omr - set(debiles):
            motivos.append("los dos métodos de lectura no coinciden")
    elif seleccion and not por_omr & set(seleccion):
        motivos.append("los dos métodos de lectura no coinciden")
    elif not seleccion and por_omr:
        motivos.append("los dos métodos de lectura no coinciden")
    elif por_omr - esperado_omr - set(debiles):
        motivos.append("los dos métodos de lectura no coinciden")
    return seleccion, ("dudoso" if motivos else "ok"), "; ".join(motivos), anuladas


# --------------------------------------------------------------------------- lector
class Lector:
    """Lee páginas escaneadas.

    ``buscar_maqueta(huella)`` devuelve la :class:`Maqueta` impresa con esa huella (o None).
    ``maqueta_por_defecto`` se usa cuando el QR no se puede leer.
    """

    def __init__(self, buscar_maqueta: Callable[[str], Maqueta | None], maqueta_por_defecto: Maqueta | None,
                 carpeta_cache: Path):
        self.buscar_maqueta = buscar_maqueta
        self.por_defecto = maqueta_por_defecto
        self.cache = Path(carpeta_cache)
        self._plantillas: dict[tuple[str, int], PlantillaPagina] = {}

    def _plantilla(self, maqueta: Maqueta, indice: int) -> PlantillaPagina:
        clave = (maqueta.huella, indice)
        if clave not in self._plantillas:
            self._plantillas[clave] = PlantillaPagina(
                maqueta.paginas[indice].campos, self.cache, f"{maqueta.huella}_p{indice + 1}")
        return self._plantillas[clave]

    def leer_pagina(self, gris: np.ndarray, origen: str) -> tuple[ResultadoPagina, np.ndarray | None]:
        res = ResultadoPagina(origen=origen)
        normal, indice, n_marcas, error = enderezar(gris)
        res.marcadores, res.indice = n_marcas, indice
        if error:
            res.error = error
            return res, None
        qr = leer_qr(normal)
        maqueta = None
        if qr:
            huella, indice_qr, hoja = qr
            res.qr, res.huella, res.hoja = True, huella, hoja
            if indice_qr != indice:
                res.aviso = f"El QR indica la página {indice_qr + 1} pero las marcas la página {indice + 1}."
            maqueta = self.buscar_maqueta(huella)
            if maqueta is None:
                res.error = (f"La hoja pertenece a otra encuesta o a una versión que no está en este programa "
                             f"(ref. {huella}).")
                return res, normal
        else:
            maqueta = self.por_defecto
            if maqueta is None:
                res.error = "No se puede leer el código QR y no hay una encuesta seleccionada."
                return res, normal
            res.huella = maqueta.huella
            res.aviso = "No se ha podido leer el QR; se asume la última versión impresa de la encuesta."
        if indice >= len(maqueta.paginas):
            res.error = f"La encuesta solo tiene {len(maqueta.paginas)} páginas y esta hoja es la página {indice + 1}."
            return res, normal

        pag = maqueta.paginas[indice]
        papel = nivel_papel(normal)
        umbral = _umbral_tinta(papel)
        desplazamientos = {c["clave"]: afinar_campo(normal, c) for c in pag.campos}
        respuesta_omr = self._plantilla(maqueta, indice).leer(ajustar_niveles(normal, papel), desplazamientos)
        tintas = corregir_fondo({c["clave"]: medir_tinta(normal, c, desplazamientos[c["clave"]], umbral)
                                 for c in pag.campos})
        for c in pag.campos:
            desp = desplazamientos[c["clave"]]
            tinta = tintas[c["clave"]]
            omr = respuesta_omr.get(c["clave"], "")
            seleccion, estado, motivo, anuladas = decidir(c["tipo"], omr, tinta)
            res.campos.append(ResultadoCampo(
                clave=c["clave"], pregunta=c["pregunta"], tipo=c["tipo"], fila=c["fila"], omr=omr, tinta=tinta,
                seleccion=seleccion, estado=estado, motivo=motivo, anuladas=anuladas, desplazamiento=desp))
        umbral_texto = papel * 0.62
        for z in pag.zonas:
            if z["tipo"] in ("texto_libre", "especifique"):
                n = tinta_texto(normal, z["rect"], umbral_texto)
                area = (z["rect"][2] - z["rect"][0]) * (z["rect"][3] - z["rect"][1]) * PX_MM * PX_MM
                escrito = n > max(120, 0.0025 * area)
                res.textos.append(ResultadoTexto(z["pregunta"], z["tipo"], z.get("opcion"), escrito, n))
        return res, normal
