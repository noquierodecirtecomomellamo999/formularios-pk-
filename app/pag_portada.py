import streamlit as st

import comun
from encuestas_omr.resultados import consolidar


def pagina():
    st.title("📋 Encuestas en papel con lectura automática")
    st.write(
        "Diseña el cuestionario, imprímelo, escanea las hojas rellenadas y obtén automáticamente "
        "las tablas, los gráficos y el informe de resultados."
    )
    pasos = [
        ("disenar", "📝", "Diseñar la encuesta", "Escribe las preguntas o impórtalas de un Word."),
        ("imprimir", "🖨️", "Imprimir", "Genera el PDF con las casillas, las marcas de las esquinas y el código QR."),
        ("leer", "📥", "Leer los escaneos", "Sube el PDF del escáner: el programa lee las casillas solo."),
        ("revisar", "🔍", "Revisar dudas", "Comprueba las pocas respuestas dudosas y transcribe los comentarios."),
        ("resultados", "📊", "Resultados e informe", "Gráficos, tablas, informe PDF y Excel."),
    ]
    cols = st.columns(len(pasos))
    for col, (ruta, icono, titulo, texto) in zip(cols, pasos):
        with col:
            with st.container(border=True):
                st.page_link(comun.PAGINAS[ruta], label=f"**{titulo}**", icon=icono)
                st.caption(texto)

    activa = comun.encuesta_activa()
    if not activa:
        return
    alm, eid, enc = activa
    st.subheader(f"Encuesta de trabajo: {enc.titulo}")
    if enc.subtitulo:
        st.caption(enc.subtitulo)
    impresiones = alm.impresiones(eid)
    lotes = alm.lotes(eid)
    cons = consolidar(alm, eid, enc) if lotes else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preguntas", len(enc.preguntas))
    c2.metric("Cuestionarios impresos", sum(i["hasta"] - i["desde"] + 1 for i in impresiones if i.get("desde")))
    c3.metric("Cuestionarios leídos", len(cons.validos) if cons else 0)
    c4.metric("Dudas por revisar", len(cons.dudas_pendientes) if cons else 0)

    with st.expander("Consejos para que la lectura sea fiable"):
        st.markdown(
            "- Imprime a **tamaño real (100 %)** en folios blancos A4. Se puede imprimir a doble cara.\n"
            "- No grapes ni escribas sobre los **cuadrados negros de las esquinas** ni sobre el **código QR**.\n"
            "- Pide que marquen con una **X dentro de la casilla**, con bolígrafo o lápiz oscuro. Para anular "
            "una respuesta, que **rellenen entera** la casilla equivocada.\n"
            "- Escanea a **200 o 300 ppp**, en gris o blanco y negro, en un **PDF de varias páginas**. "
            "Si las copias están numeradas, el orden de las hojas da igual.\n"
            "- Si cambias las preguntas después de imprimir, las hojas ya impresas se siguen leyendo bien "
            "(cada versión impresa queda guardada), pero para cambios grandes es mejor **duplicar** la encuesta."
        )
