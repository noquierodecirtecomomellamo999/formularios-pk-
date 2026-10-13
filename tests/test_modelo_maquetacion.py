import copy

import pytest

from conftest import EJEMPLOS, NOMBRES_EJEMPLOS, cargar_ejemplo
from encuestas_omr.maquetacion import (CASILLA_MM, MEDIDA_PX, PAGINA_PX, PX_MM, Y_LIMITE, maquetar)
from encuestas_omr.modelo import Elemento, Encuesta, asignar_ids, nuevo_elemento, validar
from encuestas_omr.motor_omrchecker import PlantillaPagina, plantilla_json


def test_ejemplos_validos_y_json_ida_y_vuelta():
    assert len(NOMBRES_EJEMPLOS) == 4
    for nombre in NOMBRES_EJEMPLOS:
        enc = cargar_ejemplo(nombre)
        assert validar(enc) == []
        assert Encuesta.from_dict(enc.to_dict()).to_dict() == enc.to_dict()


def test_asignar_ids_unicos():
    enc = Encuesta(id="x", titulo="T", elementos=[nuevo_elemento(t) for t in
                                                  ("seccion", "unica", "unica", "texto", "escala", "abierta")])
    asignar_ids(enc)
    ids = [e.id for e in enc.elementos]
    assert len(set(ids)) == len(ids)
    assert all("." not in i for i in ids)  # OMRChecker no admite puntos en las etiquetas


def test_validar_detecta_errores():
    enc = Encuesta(id="x", titulo="", elementos=[Elemento("unica", id="p1", texto="?", opciones=["Sola"])])
    errores = validar(enc)
    assert any("título" in e for e in errores)
    assert any("2 opciones" in e for e in errores)


@pytest.mark.parametrize("nombre", NOMBRES_EJEMPLOS)
def test_maquetacion_dentro_de_la_pagina(nombre):
    m = maquetar(cargar_ejemplo(nombre), EJEMPLOS / "logos")
    assert 1 <= len(m.paginas) <= 3
    preguntas = {e.id for e in cargar_ejemplo(nombre).preguntas}
    vistas = set()
    for pag in m.paginas:
        cajas = []
        for c in pag.campos:
            vistas.add(c["pregunta"])
            for x, y in c["casillas"]:
                assert 0 < x and x + MEDIDA_PX < PAGINA_PX[0]
                assert 0 < y and y + MEDIDA_PX < Y_LIMITE * PX_MM
                cajas.append((x, y))
        # Ninguna casilla se solapa con otra
        lado = CASILLA_MM * PX_MM
        for i, (x1, y1) in enumerate(cajas):
            for x2, y2 in cajas[i + 1:]:
                assert abs(x1 - x2) >= lado or abs(y1 - y2) >= lado
        for z in pag.zonas:
            vistas.add(z["pregunta"])
            assert z["rect"][3] <= Y_LIMITE + 1
    assert preguntas <= vistas


@pytest.mark.parametrize("nombre", NOMBRES_EJEMPLOS)
def test_plantilla_omrchecker_valida(nombre, tmp_path):
    m = maquetar(cargar_ejemplo(nombre), EJEMPLOS / "logos")
    for pag in m.paginas:
        datos = plantilla_json(pag.campos)
        assert set(datos["fieldBlocks"]) == {c["clave"] for c in pag.campos}
        plantilla = PlantillaPagina(pag.campos, tmp_path, f"p{pag.indice}")  # OMRChecker valida el esquema
        # Las casillas que calcula OMRChecker son exactamente las que se imprimen
        for bloque in plantilla.template.field_blocks:
            campo = next(c for c in pag.campos if c["clave"] == bloque.name)
            assert [[b.x, b.y] for b in bloque.traverse_bubbles[0]] == campo["casillas"]


def test_huella_solo_depende_de_lo_impreso():
    enc = cargar_ejemplo("cirenc-centro-de-dia-2026")
    h0 = maquetar(enc, EJEMPLOS / "logos").huella
    otra = copy.deepcopy(enc)
    otra.preguntas[0].grafico = "barras"
    otra.preguntas[0].favorables = [0]
    assert maquetar(otra, EJEMPLOS / "logos").huella == h0
    otra.preguntas[0].texto += " (cambiado)"
    assert maquetar(otra, EJEMPLOS / "logos").huella != h0


def test_escala_muy_larga_se_parte_en_paginas():
    filas = [f"Aspecto número {i}" for i in range(45)]
    enc = Encuesta(id="larga", titulo="Larga", elementos=[
        Elemento("escala", id="p1", texto="Valore:", valores=[str(i) for i in range(11)], filas=filas)])
    m = maquetar(enc)
    claves = [c["clave"] for p in m.paginas for c in p.campos]
    assert len(m.paginas) >= 2
    assert sorted(claves) == sorted(f"p1_f{i + 1}" for i in range(45))
