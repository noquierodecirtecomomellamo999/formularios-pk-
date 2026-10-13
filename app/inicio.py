"""Aplicación de encuestas en papel con lectura automática (OMR).

Arranque:  streamlit run app/inicio.py   (o doble clic en iniciar.bat en Windows)
"""

import sys
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

st.set_page_config(page_title="Encuestas OMR", page_icon="📋", layout="wide")

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
    st.caption(f"Datos guardados en: `{comun.almacen().raiz}`")
nav.run()
