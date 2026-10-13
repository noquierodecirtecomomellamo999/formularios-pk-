"""Lectura de hojas rellenadas y escaneadas por ordenador (simulador)."""

import numpy as np
import pytest

from conftest import EJEMPLOS, hojas_rellenas
from encuestas_omr.lector import Lector, decidir
from encuestas_omr.marcadores import interpretar_qr, texto_qr


def _leer_todo(maqueta, imagenes, tmp_path):
    lector = Lector(lambda h: maqueta if h == maqueta.huella else None, maqueta, tmp_path / "cache")
    return [lector.leer_pagina(img, f"p{i}")[0] for i, img in enumerate(imagenes)]


def _comparar(resultados, verdad):
    """Devuelve (correctas, dudosas, errores_silenciosos)."""
    bien = dudosas = mal = 0
    for r in resultados:
        assert not r.error, r.error
        esperadas = verdad[r.hoja]
        for c in r.campos:
            esperado = sorted(esperadas.get(c.clave, []))
            if c.estado == "dudoso":
                dudosas += 1
            elif c.seleccion == esperado:
                bien += 1
            else:
                mal += 1
    return bien, dudosas, mal


@pytest.mark.parametrize("estilo", ["boligrafo", "boligrafo_fino", "lapiz", "tick", "lapiz_claro", "x_pequena"])
def test_lectura_sin_errores_ni_dudas(estilo, maqueta_ejemplo, tmp_path):
    m = maqueta_ejemplo("cirenc-centro-de-dia-2026")
    imagenes, verdad = hojas_rellenas(m, EJEMPLOS / "logos", tmp_path, n=2, estilo=estilo, semilla=7)
    bien, dudosas, mal = _comparar(_leer_todo(m, imagenes, tmp_path), verdad)
    assert mal == 0
    assert dudosas == 0
    assert bien == 2 * sum(len(p.campos) for p in m.paginas)


@pytest.mark.parametrize("dpi", [150, 300])
def test_otras_resoluciones_y_hoja_del_reves(dpi, maqueta_ejemplo, tmp_path):
    m = maqueta_ejemplo("cirenc-familiares-2026")
    imagenes, verdad = hojas_rellenas(m, EJEMPLOS / "logos", tmp_path, n=1, dpi=dpi, estilo="boligrafo", semilla=3,
                                      girar_180=True)
    resultados = _leer_todo(m, imagenes, tmp_path)
    assert all(r.qr for r in resultados)
    bien, dudosas, mal = _comparar(resultados, verdad)
    assert mal == 0 and dudosas <= 1


def test_marcas_dudosas_van_a_revision_nunca_a_error(maqueta_ejemplo, tmp_path):
    """Círculos alrededor de la casilla o temblores fuertes: pueden quedar dudosos, pero nunca mal leídos."""
    m = maqueta_ejemplo("cirenc-tratamiento-ambulatorio-2026")
    for estilo in ("circulo", "temblor"):
        imagenes, verdad = hojas_rellenas(m, EJEMPLOS / "logos", tmp_path, n=1, estilo=estilo, semilla=11)
        _, _, mal = _comparar(_leer_todo(m, imagenes, tmp_path), verdad)
        assert mal == 0


def test_pagina_en_blanco_y_hoja_ajena(maqueta_ejemplo, tmp_path):
    m = maqueta_ejemplo("cirenc-familiares-2026")
    imagenes, _ = hojas_rellenas(m, EJEMPLOS / "logos", tmp_path, n=1, prob_blanco=1.0)
    for r in _leer_todo(m, imagenes, tmp_path):
        assert not r.error
        assert all(c.seleccion == [] and c.estado == "ok" for c in r.campos)
    otra = (np.random.default_rng(0).integers(200, 255, (2339, 1654))).astype(np.uint8)
    r = _leer_todo(m, [otra], tmp_path)[0]
    assert r.error


def test_textos_escritos_a_mano(maqueta_ejemplo, tmp_path):
    m = maqueta_ejemplo("cirenc-centro-de-dia-2026")
    for con_texto in (False, True):
        for estilo in ("boligrafo", "lapiz"):
            imagenes, _ = hojas_rellenas(m, EJEMPLOS / "logos", tmp_path, n=1, estilo=estilo, textos=con_texto,
                                         semilla=5, dpi=150)
            textos = [t for r in _leer_todo(m, imagenes, tmp_path) for t in r.textos if t.tipo == "texto_libre"]
            assert textos and all(t.escrito == con_texto for t in textos)


def test_qr_ida_y_vuelta():
    assert interpretar_qr(texto_qr("a1b2c3d4", 1, 15)) == ("a1b2c3d4", 1, 15)
    assert interpretar_qr("http://otra-cosa") is None


@pytest.mark.parametrize("tipo,omr,tinta,esperado,estado", [
    ("unica", "B", [0, .4, 0, 0], [1], "ok"),
    ("unica", "", [0, 0, 0, 0], [], "ok"),
    ("unica", "AB", [.4, .45, 0, 0], [0, 1], "dudoso"),  # doble marca
    ("unica", "D", [0, .4, 0, 1.0], [1], "ok"),  # corrección: casilla rellena = anulada
    ("unica", "C", [0, 0, 1.0, 0], [2], "ok"),  # marca rellenando la casilla
    ("unica", "B", [0, .07, 0, 0], [], "dudoso"),  # marca débil
    ("multiple", "AC", [.4, 0, .3, 0], [0, 2], "ok"),
    ("multiple", "A", [.4, 0, .3, 0], [0, 2], "dudoso"),  # los dos métodos no coinciden
])
def test_decidir(tipo, omr, tinta, esperado, estado):
    seleccion, est, _, _ = decidir(tipo, omr, tinta)
    assert seleccion == esperado
    assert est == estado
