"""Página 5: resultados, gráficos, informe PDF y Excel."""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import comun
from encuestas_omr import graficos
from encuestas_omr.analisis import conclusiones_automaticas, num, pct, resumir
from encuestas_omr.exportar import exportar_excel
from encuestas_omr.informe_pdf import generar_informe, textos_por_defecto
from encuestas_omr.modelo import GRAFICOS
from encuestas_omr.resultados import consolidar

OPCIONES_GRAFICO = {
    "unica": ["auto", "quesito", "barras", "barras_h", "ninguno"],
    "multiple": ["auto", "barras_h", "barras", "ninguno"],
    "escala": ["auto", "barras_h", "barras", "quesito", "ninguno"],
    "numero": ["auto", "barras", "ninguno"],
}
NOMBRES_GRAFICO = {**GRAFICOS, "auto": "Automático"}


# --------------------------------------------------------------------------- guardado (callbacks)
def _guardar_en_encuesta(eid, pid, campo, clave_widget):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    e = enc.pregunta(pid)
    valor = st.session_state.get(clave_widget)
    if campo == "favorables":
        valor = sorted(valor or [])
    setattr(e, campo, valor)
    alm.guardar(enc)


def _guardar_texto_informe(eid, campo, clave_widget):
    alm = comun.almacen()
    t = alm.textos_informe(eid)
    t[campo] = st.session_state.get(clave_widget)
    alm.guardar_textos_informe(eid, t)


def _guardar_frase(eid, pid, clave_widget, automatica):
    alm = comun.almacen()
    t = alm.textos_informe(eid)
    frases = t.setdefault("frases", {})
    valor = (st.session_state.get(clave_widget) or "").strip()
    if valor and valor != automatica:
        frases[pid] = valor
    else:
        frases.pop(pid, None)
    alm.guardar_textos_informe(eid, t)


def _restaurar_frase(eid, pid, clave_widget):
    alm = comun.almacen()
    t = alm.textos_informe(eid)
    t.setdefault("frases", {}).pop(pid, None)
    alm.guardar_textos_informe(eid, t)
    st.session_state.pop(clave_widget, None)


def _regenerar_conclusiones(eid, clave_widget):
    alm = comun.almacen()
    t = alm.textos_informe(eid)
    t.pop("conclusiones", None)
    alm.guardar_textos_informe(eid, t)
    st.session_state.pop(clave_widget, None)


# --------------------------------------------------------------------------- piezas
def _png_grafico(r, tipo):
    clave = repr((tipo, r.elemento.to_dict(), [(f.etiqueta, f.n) for f in r.tabla],
                  [(f.etiqueta, f.media, f.pct_umbral, [(d.etiqueta, d.n) for d in f.distribucion]) for f in r.filas],
                  r.numeros))

    def generar():
        with tempfile.TemporaryDirectory() as tmp:
            ruta = graficos.grafico(r, Path(tmp) / "g.png", tipo)
            return ruta.read_bytes() if ruta else None

    return comun.cache_png(clave, generar)


def _tabla(r) -> pd.DataFrame | None:
    e = r.elemento
    if e.tipo in ("unica", "multiple"):
        filas = [{"Respuesta": f.etiqueta, "Personas": f.n, "Porcentaje": pct(f.pct)} for f in r.tabla]
        if r.n_blanco:
            filas.append({"Respuesta": "(sin respuesta)", "Personas": r.n_blanco, "Porcentaje": ""})
        return pd.DataFrame(filas)
    if e.tipo == "escala":
        u = r.umbral
        filas = []
        for f in r.filas:
            fila = {"Aspecto": f.etiqueta or "Puntuación", "Media": num(f.media), "Mediana": num(f.mediana),
                    f"% ≥ {num(u)}": pct(f.pct_umbral), "Respuestas": f.n}
            if e.extras:
                fila[" / ".join(e.extras)] = f.n_extras
            filas.append(fila)
        return pd.DataFrame(filas)
    if e.tipo == "numero" and r.numeros:
        s = pd.Series(r.numeros)
        return pd.DataFrame([{"Respuestas": len(s), "Media": num(s.mean(), 1), "Mediana": num(s.median(), 1),
                              "Mínimo": int(s.min()), "Máximo": int(s.max())}])
    return None


def _bloque_pregunta(alm, eid, r, frases_editadas):
    e = r.elemento
    with st.container(border=True):
        st.markdown(f"**{e.numero} {e.texto}**")
        if e.tipo == "abierta":
            st.write(r.frase)
            if r.textos:
                st.markdown("\n".join(f"- {t}" for t in r.textos))
            if r.n_escritos > len(r.textos):
                st.caption(f"{r.n_escritos - len(r.textos)} comentario(s) sin transcribir; se pueden transcribir en "
                           "«Revisar dudas» o saldrán como imagen en el anexo del informe.")
            return
        c_graf, c_ctrl = st.columns([3, 2])
        with c_ctrl:
            kg = f"gr:{eid}:{e.id}"
            comun.iniciar(kg, e.grafico if e.grafico in OPCIONES_GRAFICO[e.tipo] else "auto")
            st.selectbox("Tipo de gráfico", OPCIONES_GRAFICO[e.tipo], key=kg, format_func=NOMBRES_GRAFICO.get,
                         on_change=_guardar_en_encuesta, args=(eid, e.id, "grafico", kg))
            if e.tipo == "unica":
                kf = f"fav:{eid}:{e.id}"
                comun.iniciar(kf, [k for k in e.favorables if k < len(e.opciones)])
                st.multiselect("Respuestas favorables (para la frase de resumen)", list(range(len(e.opciones))),
                               key=kf, format_func=lambda k: e.opciones[k],
                               on_change=_guardar_en_encuesta, args=(eid, e.id, "favorables", kf))
            if e.tipo == "escala":
                ku = f"umb:{eid}:{e.id}"
                comun.iniciar(ku, float(r.umbral) if r.umbral is not None else 0.0)
                st.number_input("Contar el % que puntúa igual o más que", key=ku, step=1.0,
                                on_change=_guardar_en_encuesta, args=(eid, e.id, "umbral", ku))
            tabla = _tabla(r)
            if tabla is not None:
                st.dataframe(tabla, hide_index=True, width="stretch")
        with c_graf:
            imagen = _png_grafico(r, st.session_state.get(f"gr:{eid}:{e.id}", "auto"))
            if imagen:
                st.image(imagen, width="stretch")
            elif r.n_validas == 0:
                st.caption("Sin respuestas.")
        kfr = f"fr:{eid}:{e.id}"
        editada = e.id in frases_editadas
        if editada:
            comun.iniciar(kfr, frases_editadas[e.id])
        else:
            st.session_state[kfr] = r.frase  # sigue a los datos mientras no se edite a mano
        st.text_area("Resultado (puedes editar la frase)", key=kfr, height=68, on_change=_guardar_frase,
                     args=(eid, e.id, kfr, r.frase))
        notas = []
        if r.n_blanco:
            notas.append(f"{r.n_blanco} sin respuesta")
        if r.n_dudosas:
            notas.append(f"⚠️ {r.n_dudosas} dudosa(s) sin revisar")
        if r.especifique:
            notas.append("escrito: " + "; ".join(r.especifique))
        if notas:
            st.caption(" · ".join(notas))
        if editada:
            c1, c2 = st.columns([3, 1])
            c1.caption("✏️ Frase editada a mano (no se actualiza sola si cambian los datos).")
            c2.button("Restaurar automática", key=f"rest:{kfr}", on_click=_restaurar_frase, args=(eid, e.id, kfr))


def _informe(alm, eid, enc, cons, resumenes):
    defecto = textos_por_defecto(enc, cons, resumenes)
    guardado = alm.textos_informe(eid)
    k = f"inf:{eid}:"
    # Los textos que no se han editado a mano siguen a los datos (número de personas, conclusiones…)
    for campo, sufijo in (("titulo", "titulo"), ("introduccion", "intro"), ("conclusiones", "concl")):
        if not guardado.get(campo):
            st.session_state[k + sufijo] = defecto[campo]
    st.text_input("Título del informe", key=comun.iniciar(k + "titulo", guardado.get("titulo") or defecto["titulo"]),
                  on_change=_guardar_texto_informe, args=(eid, "titulo", k + "titulo"))
    st.text_area("Introducción", key=comun.iniciar(k + "intro", guardado.get("introduccion") or defecto["introduccion"]),
                 height=100, on_change=_guardar_texto_informe, args=(eid, "introduccion", k + "intro"))
    c1, c2 = st.columns([4, 1])
    c1.text_area("Conclusiones (las líneas que empiezan por «- » salen como lista)",
                 key=comun.iniciar(k + "concl", guardado.get("conclusiones") or defecto["conclusiones"]), height=220,
                 on_change=_guardar_texto_informe, args=(eid, "conclusiones", k + "concl"))
    c2.button("🔄 Rehacer automáticas", on_click=_regenerar_conclusiones, args=(eid, k + "concl"),
              help="Vuelve a escribir las conclusiones a partir de los datos actuales.")
    st.text_area("Texto final (lugar, fecha, firma…)", key=comun.iniciar(k + "cierre", guardado.get("cierre", "")),
                 height=80, placeholder="En La Roda, a 21 de septiembre de 2026\n\nNombre y cargo",
                 on_change=_guardar_texto_informe, args=(eid, "cierre", k + "cierre"))
    st.checkbox("Incluir en un anexo los comentarios escritos a mano que no se han transcrito",
                key=comun.iniciar(k + "rec", guardado.get("incluir_recortes", True)),
                on_change=_guardar_texto_informe, args=(eid, "incluir_recortes", k + "rec"))

    c1, c2 = st.columns(2)
    marca = datetime.now().strftime("%Y%m%d-%H%M")
    if c1.button("📄 Generar informe PDF", type="primary", width="stretch"):
        with st.spinner("Generando el informe…"):
            destino = alm.ruta(eid) / "informes" / f"informe_{eid}_{marca}.pdf"
            generar_informe(alm, eid, destino)
        st.session_state["informe_pdf"] = str(destino)
    if c2.button("📊 Exportar a Excel", width="stretch"):
        with st.spinner("Preparando el Excel…"):
            destino = alm.ruta(eid) / "informes" / f"resultados_{eid}_{marca}.xlsx"
            exportar_excel(alm, eid, destino)
        st.session_state["informe_xlsx"] = str(destino)
    for clave, mime, columna in (("informe_pdf", "application/pdf", c1),
                                 ("informe_xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  c2)):
        ruta = Path(st.session_state.get(clave, ""))
        if ruta.is_file() and ruta.parent.parent.name == eid:
            columna.download_button(f"⬇️ Descargar {ruta.name}", ruta.read_bytes(), file_name=ruta.name, mime=mime,
                                    width="stretch")


def pagina():
    st.title("📊 Resultados e informe")
    activa = comun.encuesta_activa()
    if not activa:
        return
    alm, eid, enc = activa
    st.caption(f"{enc.titulo} · {enc.subtitulo}" if enc.subtitulo else enc.titulo)
    cons = consolidar(alm, eid, enc)
    if not cons.validos:
        st.info("Todavía no hay cuestionarios leídos para esta encuesta.")
        st.page_link(comun.PAGINAS["leer"], label="Ir a «Leer escaneos»", icon="📥")
        return
    resumenes = resumir(enc, cons)
    c1, c2, c3 = st.columns(3)
    c1.metric("Cuestionarios analizados", len(cons.validos))
    c2.metric("Dudas sin revisar", len(cons.dudas_pendientes))
    c3.metric("Páginas sin leer", len(cons.errores))
    if cons.dudas_pendientes:
        st.warning(f"Hay {len(cons.dudas_pendientes)} respuesta(s) dudosa(s) sin revisar. Los resultados usan de "
                   "momento la lectura automática.")
        st.page_link(comun.PAGINAS["revisar"], label="Revisar las dudas", icon="🔍")
    if any(any("prueba_simulada" in a for a in m["archivos"]) for m in alm.lotes(eid)):
        st.warning("🧪 Los resultados incluyen un lote de **prueba con datos inventados**. Bórralo en «Leer "
                   "escaneos» antes de hacer el informe definitivo.")

    tab_preg, tab_inf = st.tabs(["Preguntas", "Informe y exportación"])
    with tab_preg:
        frases = alm.textos_informe(eid).get("frases", {})
        por_id = {r.elemento.id: r for r in resumenes}
        for e in enc.elementos:
            if e.tipo == "seccion":
                st.subheader(e.texto)
            elif e.tipo == "texto":
                st.markdown(f"**{e.numero} {e.texto}**")
            else:
                _bloque_pregunta(alm, eid, por_id[e.id], frases)
    with tab_inf:
        _informe(alm, eid, enc, cons, resumenes)
