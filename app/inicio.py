"""Aplicación de encuestas en papel con lectura automática (OMR).

Arranque:  doble clic en el icono «Encuestas CIRENC» (o iniciar.bat), o bien
           python lanzador.py   /   streamlit run app/inicio.py
"""

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

import comun  # noqa: E402
import pag_disenar  # noqa: E402
import pag_imprimir  # noqa: E402
import pag_leer  # noqa: E402
import pag_portada  # noqa: E402
import pag_resultados  # noqa: E402
import pag_revisar  # noqa: E402

ICONO = comun.RAIZ / "recursos" / "icono.png"
LOGO = comun.RAIZ / "ejemplos" / "logos" / "logo_cirenc.png"
st.set_page_config(page_title="Encuestas CIRENC", page_icon=str(ICONO) if ICONO.exists() else "📋", layout="wide")
if LOGO.exists():
    st.logo(str(LOGO), size="large")


def _cerrar_programa():
    # Se deja un momento para que el navegador reciba la página de despedida.
    threading.Timer(1.5, lambda: os._exit(0)).start()


if st.session_state.get("_cerrar"):
    st.title("Programa cerrado")
    st.write("Todo lo que has hecho está guardado. Ya puedes cerrar esta pestaña del navegador.")
    st.write("Para volver a abrirlo, usa el icono **Encuestas CIRENC** del escritorio.")
    _cerrar_programa()
    st.stop()

paginas = [
    st.Page(pag_portada.pagina, title="Inicio", icon="🏠", url_path="inicio", default=True),
    st.Page(pag_disenar.pagina, title="1. Diseñar encuesta", icon="📝", url_path="disenar"),
    st.Page(pag_imprimir.pagina, title="2. Imprimir", icon="🖨️", url_path="imprimir"),
    st.Page(pag_leer.pagina, title="3. Leer escaneos", icon="📥", url_path="leer"),
    st.Page(pag_revisar.pagina, title="4. Revisar dudas", icon="🔍", url_path="revisar"),
    st.Page(pag_resultados.pagina, title="5. Resultados e informe", icon="📊", url_path="resultados"),
]
nav = st.navigation(paginas)
comun.PAGINAS = {p.url_path: p for p in paginas}

with st.sidebar:
    comun.selector_encuesta()
    st.divider()
    raiz_datos = comun.almacen().raiz
    st.caption(f"Tus datos se guardan en:  \n`{raiz_datos}`")
    if os.name == "nt":
        st.button("📂 Abrir la carpeta de datos", on_click=lambda: os.startfile(raiz_datos), width="stretch",
                  help="Para hacer copias de seguridad basta con copiar esta carpeta.")
    with st.popover("⏻ Cerrar el programa", width="stretch"):
        st.caption("Todo lo que has hecho ya está guardado.")
        st.button("Cerrar ahora", type="primary", width="stretch",
                  on_click=lambda: st.session_state.update(_cerrar=True))
nav.run()
