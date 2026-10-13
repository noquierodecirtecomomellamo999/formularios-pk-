import random
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from encuestas_omr import simulador as sim  # noqa: E402
from encuestas_omr.almacen import Almacen  # noqa: E402
from encuestas_omr.formulario_pdf import generar_pdf  # noqa: E402
from encuestas_omr.maquetacion import maquetar  # noqa: E402
from encuestas_omr.modelo import Encuesta  # noqa: E402

EJEMPLOS = RAIZ / "ejemplos"
NOMBRES_EJEMPLOS = sorted(p.stem for p in EJEMPLOS.glob("*.json"))


def cargar_ejemplo(nombre: str) -> Encuesta:
    return Encuesta.cargar(EJEMPLOS / f"{nombre}.json")


@pytest.fixture
def almacen(tmp_path) -> Almacen:
    alm = Almacen(tmp_path / "datos")
    alm.instalar_ejemplos()
    return alm


def hojas_rellenas(maqueta, recursos, tmp_path, n=1, dpi=200, estilo="boligrafo", semilla=0, textos=False,
                   primera_hoja=1, angulo=1.0, girar_180=False, prob_blanco=0.05):
    """Genera ``n`` cuestionarios rellenados al azar y escaneados. Devuelve (imágenes, respuestas por hoja)."""
    pdf = generar_pdf(maqueta, tmp_path / f"f_{semilla}.pdf", recursos,
                      hojas=list(range(primera_hoja, primera_hoja + n)))
    paginas = sim.rasterizar_pdf(pdf, dpi)
    rng_py, rng = random.Random(semilla), np.random.default_rng(semilla)
    zonas = {f"{z['pregunta']}:{z.get('opcion')}" for pg in maqueta.paginas for z in pg.zonas
             if z["tipo"] == "texto_libre"}
    P = len(maqueta.paginas)
    imagenes, verdad = [], {}
    for k in range(n):
        resp = sim.respuestas_aleatorias(maqueta, rng_py, prob_blanco=prob_blanco)
        verdad[primera_hoja + k] = resp
        hojas = sim.rellenar(paginas[k * P:(k + 1) * P], maqueta, resp, dpi, sim.ESTILOS[estilo], rng,
                             textos=zonas if textos else set())
        imagenes += [sim.escanear(h, rng, angulo=rng_py.uniform(-angulo, angulo), girar_180=girar_180)
                     for h in hojas]
    return imagenes, verdad


@pytest.fixture
def maqueta_ejemplo():
    def _crear(nombre):
        return maquetar(cargar_ejemplo(nombre), EJEMPLOS / "logos")
    return _crear
