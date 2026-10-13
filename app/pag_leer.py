"""Página 3: subir y leer los escaneos."""

import random

import numpy as np
import streamlit as st

import comun
from encuestas_omr import simulador
from encuestas_omr.formulario_pdf import generar_pdf
from encuestas_omr.proceso import procesar_lote


def _procesar(alm, eid, lote):
    aviso = st.info("Leyendo las hojas… **no cambies de página hasta que termine.** (Si se interrumpe, el lote "
                    "queda guardado y se puede leer después con «Leer ahora».)", icon="⏳")
    barra = st.progress(0.0, text="Leyendo…")

    def progreso(i, n, desc):
        barra.progress(min(1.0, i / max(n, 1)), text=f"Leyendo página {i} de {n} · {desc}")

    resultados = procesar_lote(alm, eid, lote, progreso)
    barra.empty()
    aviso.empty()
    errores = sum(1 for r in resultados if r.error)
    st.session_state["leer_resumen"] = (len(resultados), errores)


def _crear_prueba(alm, eid, n):
    """Cuestionarios rellenados al azar y 'escaneados', para probar el programa sin imprimir."""
    import tempfile
    from pathlib import Path

    m = alm.maqueta_actual(eid)
    inicio = 90001 + 1000 * len(alm.lotes(eid))  # números altos para no chocar con los reales
    with tempfile.TemporaryDirectory() as tmp:
        pdf = generar_pdf(m, Path(tmp) / "f.pdf", alm.recursos(eid), hojas=list(range(inicio, inicio + n)))
        paginas = simulador.rasterizar_pdf(pdf, 150)
        rng_py, rng = random.Random(), np.random.default_rng()
        escaneadas = []
        P = len(m.paginas)
        textos = [f"{z['pregunta']}:{z.get('opcion')}" for pg in m.paginas for z in pg.zonas if z["tipo"] == "texto_libre"]
        for k in range(n):
            resp = simulador.respuestas_aleatorias(m, rng_py)
            estilo = simulador.ESTILOS[rng_py.choice(["boligrafo", "boligrafo_fino", "lapiz", "tick", "circulo"])]
            hojas = simulador.rellenar(paginas[k * P:(k + 1) * P], m, resp, 150, estilo, rng,
                                       textos=set(textos) if rng_py.random() < 0.3 else set())
            escaneadas += [simulador.escanear(h, rng, angulo=rng_py.uniform(-1.5, 1.5)) for h in hojas]
        ruta = simulador.guardar_pdf(escaneadas, Path(tmp) / "prueba_simulada.pdf", 150)
        return alm.crear_lote(eid, [(ruta.name, ruta.read_bytes())])


def pagina():
    st.title("📥 Leer escaneos")
    activa = comun.encuesta_activa()
    if not activa:
        return
    alm, eid, enc = activa
    st.caption(f"{enc.titulo} · {enc.subtitulo}" if enc.subtitulo else enc.titulo)
    st.markdown(
        "Escanea las hojas rellenadas en un **PDF de varias páginas** (200 o 300 ppp, gris o blanco y negro) y "
        "súbelo aquí. También valen fotos o imágenes escaneadas (JPG, PNG, TIFF). Puedes subir varios archivos."
    )
    n_sub = st.session_state.get("leer_n", 0)
    archivos = st.file_uploader("Archivos escaneados", type=["pdf", "jpg", "jpeg", "png", "tif", "tiff"],
                                accept_multiple_files=True, key=f"leer_up_{n_sub}")
    if archivos and st.button(f"Leer {len(archivos)} archivo(s)", type="primary"):
        lote = alm.crear_lote(eid, [(a.name, a.getvalue()) for a in archivos])
        _procesar(alm, eid, lote)
        st.session_state["leer_n"] = n_sub + 1
        st.rerun()

    resumen = st.session_state.pop("leer_resumen", None)
    if resumen:
        total, errores = resumen
        if errores:
            st.warning(f"Se han leído {total} páginas; {errores} no se han podido leer (mira abajo el motivo).")
        else:
            st.success(f"Se han leído las {total} páginas correctamente.")
        st.page_link(comun.PAGINAS["revisar"], label="Ir a revisar las dudas", icon="🔍")

    with st.expander("🧪 Probar sin imprimir (datos inventados)"):
        st.caption("Crea cuestionarios rellenados al azar y 'escaneados' por ordenador para ver cómo funciona todo "
                   "el proceso. Después borra ese lote para que no cuente en los resultados.")
        n = st.number_input("Cuestionarios de prueba", 3, 40, 10)
        if st.button("Crear y leer escaneo de prueba"):
            with st.spinner("Creando hojas de prueba…"):
                lote = _crear_prueba(alm, eid, int(n))
            _procesar(alm, eid, lote)
            st.rerun()

    lotes = alm.lotes(eid)
    if not lotes:
        return
    st.subheader("Escaneos subidos")
    for meta in reversed(lotes):
        lote = meta["id"]
        prueba = any("prueba_simulada" in a for a in meta["archivos"])
        titulo = (f"Lote {lote} · {meta['fecha'].replace('T', ' ')} · {meta['paginas']} páginas"
                  + (f" · ⚠️ {meta['errores']} sin leer" if meta["errores"] else "")
                  + (" · 🧪 PRUEBA" if prueba else ""))
        with st.expander(titulo):
            st.caption("Archivos: " + ", ".join(meta["archivos"]))
            if not meta.get("procesado"):
                if st.button("Leer ahora", key=f"proc_{lote}"):
                    _procesar(alm, eid, lote)
                    st.rerun()
            lectura = alm.lectura(eid, lote)
            fallos = [r for r in lectura if r.error]
            avisos = [r for r in lectura if r.aviso and not r.error]
            for r in fallos:
                c1, c2 = st.columns([1, 4])
                ruta = alm.ruta_lote(eid, lote) / r.imagen
                if r.imagen and ruta.exists():
                    c1.image(str(ruta), width=120)
                c2.error(f"**{r.origen}**: {r.error}")
            for r in avisos:
                st.caption(f"ℹ️ {r.origen}: {r.aviso}")
            confirmar = st.checkbox("Quiero borrar este lote", key=f"conf_{lote}")
            if st.button("🗑️ Borrar lote", key=f"borrar_{lote}", disabled=not confirmar):
                alm.borrar_lote(eid, lote)
                st.rerun()
