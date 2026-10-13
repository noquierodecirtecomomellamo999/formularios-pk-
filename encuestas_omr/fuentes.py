"""Registro de fuentes para ReportLab.

Se usa DejaVu Sans, que viene incluida con matplotlib (ya es dependencia del
programa), para tener todos los caracteres del castellano (y símbolos como ≥ o ·)
sin depender de las fuentes instaladas en Windows.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

NORMAL = "DejaVuSans"
NEGRITA = "DejaVuSans-Bold"
CURSIVA = "DejaVuSans-Oblique"

_registradas = False


def registrar() -> None:
    global _registradas
    if _registradas:
        return
    import matplotlib

    carpeta = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for nombre in (NORMAL, NEGRITA, CURSIVA):
        pdfmetrics.registerFont(TTFont(nombre, str(carpeta / f"{nombre}.ttf")))
    pdfmetrics.registerFontFamily(NORMAL, normal=NORMAL, bold=NEGRITA, italic=CURSIVA, boldItalic=NEGRITA)
    _registradas = True


def ancho(texto: str, fuente: str, tamano: float) -> float:
    """Ancho del texto en puntos."""
    registrar()
    return pdfmetrics.stringWidth(texto, fuente, tamano)
