"""Página 2: generar el PDF para imprimir."""

from datetime import datetime

import streamlit as st

import comun
from encuestas_omr.formulario_pdf import generar_pdf
from encuestas_omr.modelo import validar


def pagina():
    st.title("🖨️ Imprimir")
    activa = comun.encuesta_activa()
    if not activa:
        return
    alm, eid, enc = activa
    st.caption(f"{enc.titulo} · {enc.subtitulo}" if enc.subtitulo else enc.titulo)
    errores = validar(enc)
    if errores:
        st.error("La encuesta tiene errores; corrígelos en «Diseñar encuesta»:\n\n" +
                 "\n".join(f"- {x}" for x in errores))
        return
    try:
        m = alm.maqueta_actual(eid)
    except ValueError as e:
        st.error(str(e))
        return
    st.info(f"Cada cuestionario ocupa **{len(m.paginas)} página(s)**. Referencia de esta versión: `{m.huella}`.")

    modo = st.radio(
        "¿Cómo lo vas a imprimir?",
        ["numeradas", "maestra"],
        format_func=lambda x: {
            "numeradas": "Copias numeradas (recomendado): cada cuestionario lleva su número en todas sus hojas",
            "maestra": "Una sola copia sin numerar, para fotocopiarla",
        }[x],
    )
    if modo == "numeradas":
        desde = alm.siguiente_hoja(eid)
        n = st.number_input("Número de cuestionarios", 1, 2000, 30, step=5)
        st.caption(f"Se numerarán del **{desde}** al **{desde + n - 1}**. Con copias numeradas da igual el orden "
                   "en que se escaneen las hojas y se detecta si falta alguna página. El número no identifica a "
                   "la persona: la encuesta sigue siendo anónima.")
        hojas = list(range(desde, desde + int(n)))
    else:
        desde, hojas = 0, [0]
        st.caption("Al escanear, cada cuestionario debe ir con sus páginas seguidas y en orden "
                   "(página 1, página 2…), y luego el siguiente.")

    if st.button("Generar PDF para imprimir", type="primary"):
        nombre = f"{eid}_{datetime.now():%Y%m%d-%H%M}_{'n' + str(desde) if desde else 'maestra'}.pdf"
        destino = alm.ruta(eid) / "impresiones" / nombre
        with st.spinner("Generando el PDF…"):
            generar_pdf(m, destino, alm.recursos(eid), hojas=hojas)
        alm.registrar_impresion(eid, m.huella, desde, hojas[-1] if desde else 0, nombre)
        st.session_state["ultimo_pdf"] = str(destino)
        st.rerun()

    ultimo = st.session_state.get("ultimo_pdf")
    if ultimo:
        from pathlib import Path

        ruta = Path(ultimo)
        if ruta.exists() and ruta.parent.parent.name == eid:
            st.success(f"PDF generado: {ruta.name}")
            st.download_button("⬇️ Descargar PDF", ruta.read_bytes(), file_name=ruta.name, mime="application/pdf",
                               type="primary")

    st.markdown(
        "**Al imprimir:** tamaño real (100 %, sin «ajustar a la página»), papel blanco A4. Puede ser a doble cara. "
        "No grapes sobre los cuadrados negros de las esquinas."
    )

    impresiones = alm.impresiones(eid)
    if impresiones:
        st.subheader("Impresiones anteriores")
        for i, imp in enumerate(reversed(impresiones)):
            ruta = alm.ruta(eid) / "impresiones" / imp["archivo"]
            c1, c2 = st.columns([4, 1])
            rango = f"nº {imp['desde']}–{imp['hasta']}" if imp.get("desde") else "sin numerar"
            c1.write(f"{imp['fecha'].replace('T', ' ')} · {rango} · versión `{imp['huella']}`")
            if ruta.exists():
                c2.download_button("Descargar", ruta.read_bytes(), file_name=ruta.name, mime="application/pdf",
                                   key=f"imp_{i}", width="stretch")
