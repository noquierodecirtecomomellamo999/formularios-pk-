"""Integración con OMRChecker (https://github.com/Udayraj123/OMRChecker, licencia MIT).

El código de OMRChecker se incluye sin modificar en ``third_party/OMRChecker``.
Aquí se:

1. prepara el entorno para poder importarlo como librería (sin ventanas, sin
   configurar el *logging* global del programa),
2. genera su ``template.json`` a partir de la maquetación de cada página,
3. llama a ``ImageInstanceOps.read_omr_response`` sobre la página ya enderezada.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import types
from pathlib import Path

from .maquetacion import MEDIDA_PX, PAGINA_PX

CARPETA_OMRCHECKER = Path(__file__).resolve().parent.parent / "third_party" / "OMRChecker"

# Ajustes de umbral de OMRChecker. Se parte de sus valores por defecto y se
# rebaja el salto mínimo porque aquí las casillas se marcan con una X (menos tinta
# que un círculo relleno) y a veces con lápiz.
AJUSTES = {
    "threshold_params": {"MIN_JUMP": 18, "MIN_GAP": 22, "CONFIDENT_SURPLUS": 4},
    "outputs": {"show_image_level": 0, "save_image_level": 0, "save_detections": False},
}

_cerrojo = threading.Lock()
_modulos = None


def _importar():
    """Importa OMRChecker una sola vez, sin efectos secundarios molestos."""
    global _modulos
    if _modulos is not None:
        return _modulos
    with _cerrojo:
        if _modulos is not None:
            return _modulos
        os.environ.setdefault("MPLBACKEND", "Agg")
        import matplotlib

        matplotlib.use("Agg")
        # OMRChecker consulta el tamaño de la pantalla al importarse (para mostrar
        # ventanas de depuración que aquí no se usan). En un servidor sin pantalla
        # eso falla, así que se le da un monitor ficticio.
        falso = types.ModuleType("screeninfo")
        falso.get_monitors = lambda: [types.SimpleNamespace(x=0, y=0, width=1920, height=1080)]
        sys.modules["screeninfo"] = falso
        # Evita que OMRChecker configure el logging raíz de toda la aplicación.
        raiz = logging.getLogger()
        handler_temporal = None
        if not raiz.handlers:
            handler_temporal = logging.NullHandler()
            raiz.addHandler(handler_temporal)
        ruta = str(CARPETA_OMRCHECKER)
        if ruta not in sys.path:
            sys.path.insert(0, ruta)
        try:
            from dotmap import DotMap
            from src.defaults import CONFIG_DEFAULTS
            from src.template import Template
        finally:
            if handler_temporal is not None:
                raiz.removeHandler(handler_temporal)
        logging.getLogger("src.logger").setLevel(logging.WARNING)
        _modulos = types.SimpleNamespace(Template=Template, CONFIG_DEFAULTS=CONFIG_DEFAULTS, DotMap=DotMap)
        return _modulos


def configuracion():
    m = _importar()
    conf = m.CONFIG_DEFAULTS.toDict()
    for seccion, valores in AJUSTES.items():
        conf.setdefault(seccion, {}).update(valores)
    return m.DotMap(conf, _dynamic=False)


def plantilla_json(campos: list[dict]) -> dict:
    """``template.json`` de OMRChecker para una página: un bloque por campo."""
    bloques = {}
    for c in campos:
        bloques[c["clave"]] = {
            "origin": [int(c["origen"][0]), int(c["origen"][1])],
            "bubbleValues": c["valores"],
            "direction": c["direccion"],
            "bubblesGap": c["paso_px"],
            "labelsGap": 0,
            "fieldLabels": [c["clave"]],
        }
    return {
        "pageDimensions": list(PAGINA_PX),
        "bubbleDimensions": [MEDIDA_PX, MEDIDA_PX],
        "preProcessors": [],
        "emptyValue": "",
        "fieldBlocks": bloques,
    }


class PlantillaPagina:
    """Plantilla de OMRChecker cargada para una página concreta de una maqueta."""

    def __init__(self, campos: list[dict], carpeta_cache: Path, nombre: str):
        m = _importar()
        self.campos = campos
        self.vacia = not campos
        if self.vacia:
            return
        carpeta_cache.mkdir(parents=True, exist_ok=True)
        ruta = carpeta_cache / f"{nombre}.template.json"
        ruta.write_text(json.dumps(plantilla_json(campos), indent=1), encoding="utf-8")
        self.template = m.Template(ruta, configuracion())
        # Posición original de cada casilla, para poder aplicar desplazamientos locales.
        self._bloques = {b.name: b for b in self.template.field_blocks}
        self._originales = {
            b.name: [[(p.x, p.y) for p in fila] for fila in b.traverse_bubbles] for b in self.template.field_blocks
        }

    def leer(self, pagina_gris, desplazamientos: dict[str, tuple[int, int]] | None = None) -> dict[str, str]:
        """Devuelve ``{clave_campo: letras marcadas}`` (p. ej. ``"B"``, ``"AC"`` o ``""``)."""
        if self.vacia:
            return {}
        desplazamientos = desplazamientos or {}
        for nombre, bloque in self._bloques.items():
            dx, dy = desplazamientos.get(nombre, (0, 0))
            for fila, orig in zip(bloque.traverse_bubbles, self._originales[nombre]):
                for burbuja, (x, y) in zip(fila, orig):
                    burbuja.x, burbuja.y = x + int(dx), y + int(dy)
        with _cerrojo:  # OMRChecker guarda estado en atributos de clase
            respuesta, _, _, _ = self.template.image_instance_ops.read_omr_response(
                self.template, image=pagina_gris, name="pagina", save_dir=None
            )
        return {k: str(v) for k, v in respuesta.items()}
