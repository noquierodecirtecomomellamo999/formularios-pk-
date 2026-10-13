"""Utilidades compartidas por las páginas de la aplicación."""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from encuestas_omr.almacen import Almacen  # noqa: E402
from encuestas_omr.modelo import Encuesta  # noqa: E402


@st.cache_resource
def almacen() -> Almacen:
    a = Almacen()
    a.instalar_ejemplos()
    return a


def nombre_encuesta(d: dict) -> str:
    return f"{d['titulo']} · {d['subtitulo']}" if d.get("subtitulo") else d["titulo"]


def seleccionar(id_: str) -> None:
    """Cambia la encuesta activa (para usar antes de st.rerun o en un callback)."""
    st.session_state["encuesta_id"] = id_
    st.session_state["sel_encuesta"] = id_


def selector_encuesta() -> str | None:
    alm = almacen()
    lista = alm.listar()
    if not lista:
        return None
    ids = [x["id"] for x in lista]
    nombres = {x["id"]: nombre_encuesta(x) for x in lista}
    if st.session_state.get("sel_encuesta") not in ids:
        st.session_state["sel_encuesta"] = st.session_state.get("encuesta_id") if \
            st.session_state.get("encuesta_id") in ids else ids[0]
    elegido = st.sidebar.selectbox("Encuesta de trabajo", ids, format_func=lambda i: nombres[i], key="sel_encuesta")
    st.session_state["encuesta_id"] = elegido
    return elegido


def encuesta_activa() -> tuple[Almacen, str, Encuesta] | None:
    alm = almacen()
    eid = st.session_state.get("encuesta_id")
    if not eid or not alm.existe(eid):
        st.info("Primero crea o elige una encuesta en el menú de la izquierda.")
        return None
    return alm, eid, alm.cargar(eid)


def iniciar(clave: str, valor) -> str:
    """Da valor inicial a un widget solo la primera vez (patrón recomendado por Streamlit)."""
    if clave not in st.session_state:
        st.session_state[clave] = valor
    return clave


def lineas(texto: str) -> list[str]:
    return [l.strip() for l in (texto or "").splitlines() if l.strip()]


def png(imagen) -> bytes:
    """numpy (gris o RGB) -> bytes PNG para st.image / descargas."""
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(imagen).save(buf, format="PNG")
    return buf.getvalue()


def vista_previa_pdf(ruta: Path, dpi: int = 70) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(ruta))
    try:
        res = []
        for i in range(len(pdf)):
            img = pdf[i].render(scale=dpi / 72).to_pil()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            res.append(buf.getvalue())
        return res
    finally:
        pdf.close()


def cache_png(clave: str, generar) -> bytes | None:
    """Guarda en la sesión imágenes ya generadas (gráficos), para no rehacerlas en cada clic."""
    cache = st.session_state.setdefault("_cache_png", {})
    h = hashlib.md5(clave.encode("utf-8")).hexdigest()
    if h not in cache:
        if len(cache) > 300:
            cache.clear()
        cache[h] = generar()
    return cache[h]
