"""Maquetación del formulario en hojas A4.

Convierte una :class:`~encuestas_omr.modelo.Encuesta` en una :class:`Maqueta`:
la lista de páginas con

- las operaciones de dibujo (textos, casillas, líneas, logos) en milímetros,
- los *campos* OMR: la posición exacta de cada casilla en la imagen normalizada
  de la página (8 píxeles por milímetro), que es lo que lee OMRChecker,
- las *zonas* de recorte de cada pregunta (para revisar dudas y textos libres).

Las coordenadas usan el origen en la esquina superior izquierda y el eje Y hacia
abajo. Los marcadores de esquina y el código QR se añaden al generar el PDF
(dependen del número de hoja), pero sus posiciones son fijas y están aquí.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.utils import simpleSplit

from . import fuentes
from .fuentes import CURSIVA, NEGRITA, NORMAL
from .modelo import Elemento, Encuesta

# --------------------------------------------------------------------------- geometría fija
PX_MM = 8  # resolución de la imagen normalizada: 8 px/mm (≈203 ppp)
PAGINA_MM = (210.0, 297.0)
PAGINA_PX = (int(PAGINA_MM[0] * PX_MM), int(PAGINA_MM[1] * PX_MM))

MARCA_MM = 10.0  # lado de los marcadores ArUco
# Esquina superior izquierda de cada marcador, en el orden: sup-izq, sup-der, inf-der, inf-izq
MARCAS_MM = ((7.0, 7.0), (193.0, 7.0), (193.0, 280.0), (7.0, 280.0))
MAX_PAGINAS = 12  # 4 marcadores distintos por página (diccionario ArUco 4x4_50)

QR_MM = (172.0, 271.5)  # esquina superior izquierda del QR (incluye su margen blanco)
QR_TAM_MM = 18.0

X_IZQ, X_DER = 16.0, 194.0  # márgenes del contenido
ANCHO = X_DER - X_IZQ
Y_LIMITE = 268.5  # el contenido no baja de aquí (debajo va el pie y el QR)

CASILLA_MM = 5.0  # lado de cada casilla impresa
MEDIDA_PX = 24  # lado del cuadrado interior que se mide (sin el borde impreso)
_MARGEN_MEDIDA_PX = (CASILLA_MM * PX_MM - MEDIDA_PX) / 2  # 8 px

SANGRIA = 6.0  # sangría de las casillas respecto al texto de la pregunta
ESPACIO_ENTRE_BLOQUES = 4.0
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

PT_MM = 25.4 / 72  # 1 punto tipográfico en mm


def _mm_a_pt(v: float) -> float:
    return v / PT_MM


def alto_linea(tam: float) -> float:
    """Interlineado (mm) para un tamaño de letra en puntos."""
    return tam * 1.28 * PT_MM


def _subida(tam: float) -> float:
    """Distancia (mm) desde la parte superior de una línea hasta su línea base."""
    return tam * 0.93 * PT_MM


def envolver(texto: str, fuente: str, tam: float, ancho_mm: float) -> list[str]:
    fuentes.registrar()
    lineas: list[str] = []
    for parrafo in (texto or "").split("\n"):
        lineas.extend(simpleSplit(parrafo, fuente, tam, _mm_a_pt(ancho_mm)) or [""])
    return lineas


def ancho_texto(texto: str, fuente: str, tam: float) -> float:
    return fuentes.ancho(texto, fuente, tam) * PT_MM


# --------------------------------------------------------------------------- estructuras
@dataclass
class Bloque:
    """Trozo de formulario que se coloca entero en una página. Coordenadas relativas (y=0 arriba)."""

    alto: float
    ops: list[dict] = field(default_factory=list)
    campos: list[dict] = field(default_factory=list)
    zonas: list[dict] = field(default_factory=list)
    con_siguiente: bool = False  # no dejarlo solo al final de una página


@dataclass
class PaginaMaqueta:
    indice: int
    ops: list[dict] = field(default_factory=list)
    campos: list[dict] = field(default_factory=list)
    zonas: list[dict] = field(default_factory=list)


@dataclass
class Maqueta:
    encuesta: dict
    paginas: list[PaginaMaqueta]
    huella: str = ""

    @property
    def encuesta_id(self) -> str:
        return self.encuesta["id"]

    def to_dict(self) -> dict:
        return {
            "formato": "maqueta-omr/1",
            "huella": self.huella,
            "px_mm": PX_MM,
            "pagina_px": list(PAGINA_PX),
            "medida_px": MEDIDA_PX,
            "encuesta": self.encuesta,
            "paginas": [
                {"indice": p.indice, "ops": p.ops, "campos": p.campos, "zonas": p.zonas} for p in self.paginas
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Maqueta:
        return cls(
            encuesta=d["encuesta"],
            huella=d["huella"],
            paginas=[PaginaMaqueta(p["indice"], p["ops"], p["campos"], p["zonas"]) for p in d["paginas"]],
        )

    def guardar(self, ruta: Path) -> None:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        Path(ruta).write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def cargar(cls, ruta: Path) -> Maqueta:
        return cls.from_dict(json.loads(Path(ruta).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- operaciones de dibujo
def op_texto(x, y, t, fuente=NORMAL, tam=11.0, al="izq", gris=0.0):
    return {"op": "texto", "x": round(x, 3), "y": round(y, 3), "t": t, "f": fuente, "s": tam, "al": al, "g": gris}


def op_rect(x, y, w, h, relleno=None, borde=None, grosor=0.5, radio=0.0):
    return {"op": "rect", "x": round(x, 3), "y": round(y, 3), "w": round(w, 3), "h": round(h, 3),
            "relleno": relleno, "borde": borde, "grosor": grosor, "radio": radio}


def op_linea(x0, y0, x1, y1, grosor=0.5, gris=0.0):
    return {"op": "linea", "x0": round(x0, 3), "y0": round(y0, 3), "x1": round(x1, 3), "y1": round(y1, 3),
            "grosor": grosor, "g": gris}


def _lineas_texto(ops, lineas, x, y, fuente, tam, al="izq", gris=0.0, ancho_caja=None):
    """Añade varias líneas de texto que empiezan en ``y`` (parte superior). Devuelve el alto usado."""
    lh = alto_linea(tam)
    for i, linea in enumerate(lineas):
        xx = x
        if al == "centro" and ancho_caja is not None:
            xx = x + ancho_caja / 2
        elif al == "der" and ancho_caja is not None:
            xx = x + ancho_caja
        ops.append(op_texto(xx, y + _subida(tam) + i * lh, linea, fuente, tam, al, gris))
    return len(lineas) * lh


# --------------------------------------------------------------------------- maquetador
class Maquetador:
    def __init__(self, encuesta: Encuesta, carpeta_recursos: Path | None = None):
        self.enc = encuesta
        self.carpeta = Path(carpeta_recursos) if carpeta_recursos else None
        self.t = float(encuesta.tamano_letra)  # tamaño base
        fuentes.registrar()

    # ------------------------------------------------------------ cabeceras
    def _cabecera_primera(self) -> tuple[list[dict], float]:
        enc, ops = self.enc, []
        y = 8.0
        # Logos a la derecha (entre el texto y el marcador superior derecho)
        x_logo_der = 189.0
        alto_logos = 0.0
        for nombre in reversed(enc.cabecera.logos):
            info = self._tam_logo(nombre, alto_max=17.0, ancho_max=45.0)
            if info is None:
                continue
            w, h = info
            ops.append({"op": "imagen", "ruta": nombre, "x": x_logo_der - w, "y": y, "w": w, "h": h})
            x_logo_der -= w + 3
            alto_logos = max(alto_logos, h)
        # Texto de la organización a la izquierda
        x_txt, ancho_txt = 20.0, max(40.0, x_logo_der - 22.0)
        yy = y
        for i, linea in enumerate(enc.cabecera.lineas_izquierda):
            f = NEGRITA if i == 0 else NORMAL
            yy += _lineas_texto(ops, envolver(linea, f, 7.8, ancho_txt), x_txt, yy, f, 7.8)
        if enc.cabecera.lineas_derecha:
            yd = y + alto_logos + 1 if alto_logos else y
            for linea in enc.cabecera.lineas_derecha:
                yd += _lineas_texto(ops, [linea], 120, yd, NORMAL, 7.8, "der", ancho_caja=69)
            yy = max(yy, yd)
        y = max(yy, y + alto_logos, 19.0) + 2.0
        ops.append(op_linea(X_IZQ, y, X_DER, y, 0.6, 0.55))
        y += 3.0
        # Título y subtítulo
        y += _lineas_texto(ops, envolver(enc.titulo.upper(), NEGRITA, 13.5, ANCHO), X_IZQ, y, NEGRITA, 13.5,
                           "centro", ancho_caja=ANCHO)
        if enc.subtitulo:
            y += 0.5
            y += _lineas_texto(ops, envolver(enc.subtitulo, NORMAL, 11, ANCHO), X_IZQ, y, NORMAL, 11,
                               "centro", ancho_caja=ANCHO)
        if enc.mostrar_fecha:
            y += 1.5
            ops.append(op_texto(X_DER, y + _subida(10), "Fecha: ______ / ______ / __________", NORMAL, 10, "der"))
            y += alto_linea(10)
        y += 2.5
        if enc.introduccion:
            y += _lineas_texto(ops, envolver(enc.introduccion, NORMAL, self.t - 0.5, ANCHO), X_IZQ, y, NORMAL,
                               self.t - 0.5)
            y += 3.0
        if enc.instrucciones:
            y = self._caja_instrucciones(ops, y)
        return ops, y + 3.0

    def _caja_instrucciones(self, ops, y) -> float:
        tam = self.t - 1.5
        ancho_ejemplos = 52.0
        lineas = envolver(self.enc.instrucciones, NORMAL, tam, ANCHO - ancho_ejemplos - 8)
        alto = max(len(lineas) * alto_linea(tam), 16.0) + 4.0
        ops.append(op_rect(X_IZQ, y, ANCHO, alto, relleno=0.95, borde=0.6, grosor=0.6, radio=1.5))
        _lineas_texto(ops, lineas, X_IZQ + 3, y + 2, NORMAL, tam)
        # Ejemplos: casilla marcada con X y casilla anulada
        xe = X_DER - ancho_ejemplos + 2
        ye = y + alto / 2 - CASILLA_MM - 0.5
        ops.append(op_rect(xe, ye, CASILLA_MM, CASILLA_MM, relleno=1.0, borde=0.0, grosor=1.0))
        ops.append({"op": "aspa", "x": xe, "y": ye, "w": CASILLA_MM, "h": CASILLA_MM})
        ops.append(op_texto(xe + CASILLA_MM + 2, ye + 3.8, "Respuesta marcada", NORMAL, tam - 0.5))
        ye2 = ye + CASILLA_MM + 2.0
        ops.append(op_rect(xe, ye2, CASILLA_MM, CASILLA_MM, relleno=0.15, borde=0.0, grosor=1.0))
        ops.append(op_texto(xe + CASILLA_MM + 2, ye2 + 3.8, "Respuesta anulada", NORMAL, tam - 0.5))
        return y + alto

    def _cabecera_siguientes(self) -> tuple[list[dict], float]:
        enc, ops = self.enc, []
        titulo = enc.titulo + (f" · {enc.subtitulo}" if enc.subtitulo else "")
        lineas = envolver(titulo, NEGRITA, 8.5, 165)
        _lineas_texto(ops, lineas[:1], 20, 11.0, NEGRITA, 8.5)
        if enc.cabecera.lineas_izquierda:
            _lineas_texto(ops, envolver(enc.cabecera.lineas_izquierda[0], NORMAL, 7.5, 165)[:1], 20, 15.0,
                          NORMAL, 7.5, gris=0.35)
        ops.append(op_linea(X_IZQ, 20.5, X_DER, 20.5, 0.6, 0.55))
        return ops, 24.0

    def _tam_logo(self, nombre, alto_max, ancho_max):
        if not self.carpeta:
            return None
        ruta = self.carpeta / nombre
        if not ruta.exists():
            return None
        from PIL import Image

        with Image.open(ruta) as im:
            w, h = im.size
        esc = min(alto_max / h, ancho_max / w)
        return w * esc, h * esc

    # ------------------------------------------------------------ bloques
    def _encabezado_pregunta(self, e: Elemento, ops, ancho=ANCHO) -> float:
        texto = e.etiqueta
        lineas = envolver(texto, NEGRITA, self.t, ancho)
        return _lineas_texto(ops, lineas, X_IZQ, 0.0, NEGRITA, self.t)

    def bloques(self, e: Elemento) -> list[Bloque]:
        if e.tipo == "seccion":
            return [self._b_seccion(e)]
        if e.tipo == "texto":
            return [self._b_texto(e)]
        if e.tipo in ("unica", "multiple"):
            return [self._b_opciones(e)]
        if e.tipo == "escala":
            return self._b_escala(e)
        if e.tipo == "numero":
            return [self._b_numero(e)]
        if e.tipo == "abierta":
            return [self._b_abierta(e)]
        raise ValueError(f"Tipo de elemento desconocido: {e.tipo}")

    def _b_seccion(self, e):
        ops = []
        tam = self.t + 1.5
        y = 2.0
        y += _lineas_texto(ops, envolver(e.etiqueta, NEGRITA, tam, ANCHO), X_IZQ, y, NEGRITA, tam)
        y += 0.8
        ops.append(op_linea(X_IZQ, y, X_DER, y, 0.4, 0.6))
        return Bloque(alto=y + 1.5, ops=ops, con_siguiente=True)

    def _b_texto(self, e):
        ops = []
        alto = _lineas_texto(ops, envolver(e.etiqueta, NEGRITA, self.t, ANCHO), X_IZQ, 0.0, NEGRITA, self.t)
        return Bloque(alto=alto, ops=ops, con_siguiente=True)

    def _disposicion(self, e: Elemento) -> tuple[str, float]:
        """Decide si las opciones van en fila (horizontal) o en columna, y el paso entre casillas."""
        n = len(e.opciones)
        if e.disposicion == "vertical" or e.con_texto or n > 6:
            return "vertical", 0.0
        paso = min((ANCHO - SANGRIA) / n, 45.0)
        ancho_etq = self._ancho_etiqueta_horizontal(paso)
        lineas = [envolver(o, NORMAL, self.t, ancho_etq) for o in e.opciones]
        cabe = all(ancho_texto(l, NORMAL, self.t) <= ancho_etq for ls in lineas for l in ls)
        lineas_max = max(len(ls) for ls in lineas)
        limite = 3 if e.disposicion == "horizontal" else 2
        if cabe and lineas_max <= limite:
            return "horizontal", paso
        return "vertical", 0.0

    @staticmethod
    def _ancho_etiqueta_horizontal(paso: float) -> float:
        # casilla + 2 mm hasta el texto + al menos 5 mm libres antes de la casilla siguiente
        return paso - CASILLA_MM - 2.0 - 5.0

    def _b_opciones(self, e: Elemento) -> Bloque:
        ops: list[dict] = []
        y = self._encabezado_pregunta(e, ops)
        if e.tipo == "multiple" and "varias" not in e.texto.lower() and "más de una" not in e.texto.lower():
            y += _lineas_texto(ops, ["(Puede marcar varias opciones)"], X_IZQ, y, CURSIVA, self.t - 1.5, gris=0.3)
        y += 1.8
        disp, paso = self._disposicion(e)
        x_cas = X_IZQ + SANGRIA  # borde izquierdo de la primera casilla
        lh = alto_linea(self.t)
        zonas = []
        if disp == "horizontal":
            ancho_etq = self._ancho_etiqueta_horizontal(paso)
            lineas = [envolver(o, NORMAL, self.t, ancho_etq) for o in e.opciones]
            alto_fila = max(7.0, max(len(l) for l in lineas) * lh + 2.0)
            cy = y + CASILLA_MM / 2 + 0.5
            for i, ls in enumerate(lineas):
                x = x_cas + i * paso
                _lineas_texto(ops, ls, x + CASILLA_MM + 2.0, cy - lh / 2 - 0.1, NORMAL, self.t)
            campo = {"clave": e.id, "pregunta": e.id, "tipo": e.tipo, "fila": None, "direccion": "horizontal",
                     "cx": x_cas + CASILLA_MM / 2, "cy": cy, "paso": paso, "n": len(e.opciones)}
            y += alto_fila
        else:
            x_etq = x_cas + CASILLA_MM + 2.5
            ancho_etq = X_DER - x_etq
            lineas = []
            for i, o in enumerate(e.opciones):
                if i in e.con_texto:
                    ls = envolver(o, NORMAL, self.t, min(ancho_etq, 70.0))
                else:
                    ls = envolver(o, NORMAL, self.t, ancho_etq)
                lineas.append(ls)
            paso = max(7.5, max(len(ls) for ls in lineas) * lh + 2.6)
            if e.con_texto:
                paso = max(paso, 9.0)
            cy0 = y + CASILLA_MM / 2 + 0.5
            for i, ls in enumerate(lineas):
                cy = cy0 + i * paso
                y_txt = cy - lh / 2 - 0.1 if len(ls) == 1 else cy - CASILLA_MM / 2
                _lineas_texto(ops, ls, x_etq, y_txt, NORMAL, self.t)
                if i in e.con_texto:
                    x_linea = x_etq + max(ancho_texto(l, NORMAL, self.t) for l in ls) + 2.0
                    y_linea = y_txt + _subida(self.t) + (len(ls) - 1) * lh + 0.8
                    ops.append(op_linea(x_linea, y_linea, X_DER, y_linea, 0.5, 0.45))
                    zonas.append({"pregunta": e.id, "tipo": "especifique", "opcion": i,
                                  "rect": [x_linea - 1, cy - paso / 2 - 1.5, X_DER + 1, y_linea + 2.0]})
            campo = {"clave": e.id, "pregunta": e.id, "tipo": e.tipo, "fila": None, "direccion": "vertical",
                     "cx": x_cas + CASILLA_MM / 2, "cy": cy0, "paso": paso, "n": len(e.opciones)}
            y = cy0 + (len(e.opciones) - 1) * paso + CASILLA_MM / 2 + 1.5
        return Bloque(alto=y, ops=ops, campos=[campo], zonas=zonas)

    # ---- escala (tabla de valoración)
    def _geom_escala(self, e: Elemento, etiquetas_col: list[str]):
        tam_cab = self.t - 2.5
        ncols = len(etiquetas_col)
        # Columnas lo más anchas posible (más fácil marcar con pulso inestable),
        # dejando al menos 60 mm para el texto de las filas.
        paso = max(8.0, min(14.0, (ANCHO - 60.0) / ncols))
        for etq in etiquetas_col:
            for palabra in etq.split():
                paso = max(paso, ancho_texto(palabra, NORMAL, tam_cab) + 2.0)
        paso = min(paso, 22.0)
        ancho_rejilla = paso * ncols
        sin_etiquetas = all(not f.strip() for f in e.filas)
        if sin_etiquetas:
            x_rej = X_IZQ + SANGRIA - (paso - CASILLA_MM) / 2
        else:
            x_rej = X_DER - ancho_rejilla
        cab = [envolver(etq, NORMAL, tam_cab, paso - 0.6) for etq in etiquetas_col]
        alto_cab = max(len(c) for c in cab) * alto_linea(tam_cab) + 1.2
        return paso, x_rej, cab, alto_cab, tam_cab, sin_etiquetas

    def _b_escala(self, e: Elemento) -> list[Bloque]:
        etiquetas_col = list(e.valores) + list(e.extras)
        paso, x_rej, cab, alto_cab, tam_cab, sin_etq = self._geom_escala(e, etiquetas_col)
        ancho_etq = x_rej - X_IZQ - 4.0
        tam_fila = self.t - 0.5
        lh = alto_linea(tam_fila)
        filas = []
        for r, etq in enumerate(e.filas):
            ls = envolver(etq, NORMAL, tam_fila, ancho_etq) if etq.strip() else []
            filas.append((r, ls, max(8.0, len(ls) * lh + 2.6)))

        def construir(filas_parte, primera: bool) -> Bloque:
            ops: list[dict] = []
            if primera:
                y = self._encabezado_pregunta(e, ops)
            else:
                y = _lineas_texto(ops, [f"{e.etiqueta[:90]} (continuación)"], X_IZQ, 0.0, CURSIVA, self.t - 1.5,
                                  gris=0.3)
            y += 1.5
            # Cabecera de columnas
            for c, ls in enumerate(cab):
                xc = x_rej + c * paso
                y_txt = y + alto_cab - 1.2 - len(ls) * alto_linea(tam_cab)
                _lineas_texto(ops, ls, xc, y_txt, NEGRITA if c < len(e.valores) else NORMAL, tam_cab, "centro",
                              ancho_caja=paso)
            y_ini_tabla = y
            y += alto_cab
            campos = []
            for k, (r, ls, alto_fila) in enumerate(filas_parte):
                if k % 2 == 0:
                    x_fondo = x_rej - 1.0 if sin_etq else X_IZQ
                    ops.append(op_rect(x_fondo, y, x_rej + paso * len(etiquetas_col) + 1.0 - x_fondo, alto_fila,
                                       relleno=0.93))
                cy = y + alto_fila / 2
                if ls:
                    _lineas_texto(ops, ls, X_IZQ + 1.5, cy - len(ls) * lh / 2 - 0.1, NORMAL, tam_fila)
                campos.append({"clave": f"{e.id}_f{r + 1}", "pregunta": e.id, "tipo": "escala", "fila": r,
                               "direccion": "horizontal", "cx": x_rej + paso / 2, "cy": cy, "paso": paso,
                               "n": len(etiquetas_col)})
                y += alto_fila
            if e.extras:
                xs = x_rej + paso * len(e.valores)
                ops.append(op_linea(xs, y_ini_tabla, xs, y, 0.6, 0.45))
            return Bloque(alto=y + 1.0, ops=ops, campos=campos)

        completo = construir(filas, True)
        alto_max = Y_LIMITE - 24.0 - 2.0
        if completo.alto <= alto_max:
            return [completo]
        # Tabla más alta que una página: se parte por filas.
        partes, actual, primera = [], [], True
        for f in filas:
            prueba = construir(actual + [f], primera)
            if actual and prueba.alto > alto_max:
                partes.append(construir(actual, primera))
                actual, primera = [f], False
            else:
                actual.append(f)
        if actual:
            partes.append(construir(actual, primera))
        return partes

    def _b_numero(self, e: Elemento) -> Bloque:
        ops: list[dict] = []
        y = self._encabezado_pregunta(e, ops)
        y += 1.5
        tam = self.t - 1.0
        # Casillas para escribir el número
        txt = "Escriba el número:"
        ops.append(op_texto(X_IZQ + SANGRIA, y + 5.0, txt, NORMAL, tam))
        x = X_IZQ + SANGRIA + ancho_texto(txt, NORMAL, tam) + 3.0
        for k in range(e.cifras):
            ops.append(op_rect(x + k * 8.0, y, 7.0, 8.0, relleno=1.0, borde=0.0, grosor=0.8))
        y += 10.0
        ops.append(op_texto(X_IZQ + SANGRIA, y + 3.8, "y marque cada cifra:", NORMAL, tam))
        y += 5.5
        paso = 8.0
        x_rej = X_IZQ + SANGRIA + 24.0
        tam_cab = self.t - 2.5
        for d in range(10):
            ops.append(op_texto(x_rej + d * paso + paso / 2, y + _subida(tam_cab), str(d), NEGRITA, tam_cab,
                                "centro"))
        y += alto_linea(tam_cab) + 1.0
        campos = []
        for k in range(e.cifras):
            alto_fila = 8.0
            if k % 2 == 0:
                ops.append(op_rect(X_IZQ + SANGRIA - 1, y, x_rej + 10 * paso - X_IZQ - SANGRIA + 2, alto_fila,
                                   relleno=0.93))
            cy = y + alto_fila / 2
            ops.append(op_texto(X_IZQ + SANGRIA, cy + 1.2, f"{k + 1}ª cifra", NORMAL, tam))
            campos.append({"clave": f"{e.id}_c{k + 1}", "pregunta": e.id, "tipo": "numero", "fila": k,
                           "direccion": "horizontal", "cx": x_rej + paso / 2, "cy": cy, "paso": paso, "n": 10})
            y += alto_fila
        return Bloque(alto=y + 1.0, ops=ops, campos=campos)

    def _b_abierta(self, e: Elemento) -> Bloque:
        ops: list[dict] = []
        y = self._encabezado_pregunta(e, ops)
        y += 1.5
        alto_caja = e.lineas * 8.0 + 2.0
        x0 = X_IZQ + 2.0
        ops.append(op_rect(x0, y, X_DER - x0, alto_caja, relleno=1.0, borde=0.45, grosor=0.6, radio=1.0))
        for k in range(1, e.lineas + 1):
            yl = y + k * 8.0
            ops.append(op_linea(x0 + 3, yl, X_DER - 3, yl, 0.3, 0.78))
        zona = {"pregunta": e.id, "tipo": "texto_libre", "opcion": None, "rect": [x0, y, X_DER, y + alto_caja]}
        return Bloque(alto=y + alto_caja + 1.0, ops=ops, zonas=[zona])

    def _b_despedida(self) -> Bloque:
        ops: list[dict] = []
        y = 2.0
        y += _lineas_texto(ops, envolver(self.enc.despedida, NEGRITA, self.t, ANCHO), X_IZQ, y, NEGRITA, self.t,
                           "centro", ancho_caja=ANCHO)
        return Bloque(alto=y, ops=ops)

    # ------------------------------------------------------------ paginación
    def maquetar(self) -> Maqueta:
        lista: list[tuple[str | None, Bloque]] = []
        for e in self.enc.elementos:
            for b in self.bloques(e):
                lista.append((e.id if e.es_pregunta else None, b))
        despedida = self._b_despedida() if self.enc.despedida.strip() else None

        paginas: list[PaginaMaqueta] = []

        def nueva_pagina() -> tuple[PaginaMaqueta, float]:
            pag = PaginaMaqueta(indice=len(paginas))
            ops, y0 = self._cabecera_primera() if not paginas else self._cabecera_siguientes()
            pag.ops.extend(ops)
            paginas.append(pag)
            return pag, y0

        pag, y = nueva_pagina()
        y_tope = y  # dónde empieza el contenido en la página actual
        i = 0
        while i < len(lista):
            # Un título de sección (o un texto) se coloca junto con el bloque que le sigue.
            grupo = [lista[i]]
            j = i
            while grupo[-1][1].con_siguiente and j + 1 < len(lista):
                j += 1
                grupo.append(lista[j])
            alto_grupo = sum(b.alto for _, b in grupo) + ESPACIO_ENTRE_BLOQUES * (len(grupo) - 1)
            if y + alto_grupo > Y_LIMITE and y > y_tope:
                pag, y = nueva_pagina()
                y_tope = y
            for pid, b in grupo:
                if y + b.alto > Y_LIMITE and y > y_tope:
                    pag, y = nueva_pagina()
                    y_tope = y
                self._colocar(pag, pid, b, y)
                y += b.alto + ESPACIO_ENTRE_BLOQUES
            i = j + 1
        # La despedida solo se pone si cabe: no merece una hoja más que imprimir y escanear.
        if despedida and y + despedida.alto <= Y_LIMITE:
            self._colocar(pag, None, despedida, y)

        if len(paginas) > MAX_PAGINAS:
            raise ValueError(f"La encuesta ocupa {len(paginas)} páginas; el máximo es {MAX_PAGINAS}.")
        maqueta = Maqueta(encuesta=self.enc.to_dict(), paginas=paginas)
        maqueta.huella = calcular_huella(maqueta)
        return maqueta

    def _colocar(self, pag: PaginaMaqueta, pregunta_id: str | None, b: Bloque, y0: float) -> None:
        for op in b.ops:
            op = dict(op)
            for k in ("y", "y0", "y1"):
                if k in op:
                    op[k] = round(op[k] + y0, 3)
            pag.ops.append(op)
        for z in b.zonas:
            x0, ya, x1, yb = z["rect"]
            pag.zonas.append({**z, "rect": [x0, ya + y0, x1, yb + y0]})
        for c in b.campos:
            campo = _campo_absoluto(c, y0)
            pag.campos.append(campo)
            for (bx, by) in campo["casillas"]:
                # Se dibuja la casilla exactamente donde OMRChecker va a medir.
                x_mm = (bx - _MARGEN_MEDIDA_PX) / PX_MM
                y_mm = (by - _MARGEN_MEDIDA_PX) / PX_MM
                pag.ops.append({"op": "casilla", "x": x_mm, "y": y_mm, "w": CASILLA_MM, "h": CASILLA_MM})
        if pregunta_id and (b.campos or b.zonas):
            pag.zonas.append({"pregunta": pregunta_id, "tipo": "pregunta", "opcion": None,
                              "rect": [X_IZQ - 2, y0 - 1.5, X_DER + 2, y0 + b.alto + 0.5]})


def _campo_absoluto(c: dict, y0: float) -> dict:
    """Pasa un campo relativo (mm) a coordenadas de la imagen normalizada (px), como las usa OMRChecker."""
    cx, cy = c["cx"], c["cy"] + y0
    origen = [round((cx - CASILLA_MM / 2) * PX_MM + _MARGEN_MEDIDA_PX),
              round((cy - CASILLA_MM / 2) * PX_MM + _MARGEN_MEDIDA_PX)]
    paso_px = round(c["paso"] * PX_MM, 4)
    casillas = []
    for k in range(c["n"]):
        if c["direccion"] == "horizontal":
            casillas.append([round(origen[0] + k * paso_px), origen[1]])
        else:
            casillas.append([origen[0], round(origen[1] + k * paso_px)])
    return {
        "clave": c["clave"], "pregunta": c["pregunta"], "tipo": c["tipo"], "fila": c["fila"],
        "direccion": c["direccion"], "origen": origen, "paso_px": round(paso_px, 4),
        "valores": list(LETRAS[: c["n"]]), "casillas": casillas,
    }


def calcular_huella(maqueta: Maqueta) -> str:
    datos = json.dumps(
        {"e": maqueta.encuesta, "p": [(p.ops, p.campos) for p in maqueta.paginas]},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha1(datos.encode("utf-8")).hexdigest()[:8]


def maquetar(encuesta: Encuesta, carpeta_recursos: Path | None = None) -> Maqueta:
    return Maquetador(encuesta, carpeta_recursos).maquetar()
