"""Página 4: revisar respuestas dudosas, transcribir textos y gestionar cuestionarios."""

import pandas as pd
import streamlit as st

import comun
from encuestas_omr.lector import TINTA_VACIA
from encuestas_omr.recortes import recorte_pregunta, recorte_texto
from encuestas_omr.resultados import clave_revision, clave_texto, consolidar

POR_PAGINA = 8
SIN_RESPUESTA = -1


def _opciones(e, campo) -> list[str]:
    if e.tipo in ("unica", "multiple"):
        return list(e.opciones)
    if e.tipo == "escala":
        return list(e.valores) + list(e.extras)
    return [str(d) for d in range(10)]


def _guardar_campo(eid, cid, clave, clave_widget, multiple):
    alm = comun.almacen()
    rev = alm.revisiones(eid)
    valor = st.session_state.get(clave_widget)
    if multiple:
        sel = sorted(valor or [])
    else:
        sel = [] if valor in (None, SIN_RESPUESTA) else [valor]
    rev["campos"][clave_revision(cid, clave)] = sel
    alm.guardar_revisiones(eid, rev)


def _aceptar_todas(eid, items):
    alm = comun.almacen()
    rev = alm.revisiones(eid)
    for it in items:
        k = clave_revision(it.cuestionario, it.clave)
        if k not in rev["campos"]:
            rev["campos"][k] = list(it.campo.seleccion) if len(it.campo.seleccion) <= 1 or it.campo.tipo == "multiple" \
                else []
    alm.guardar_revisiones(eid, rev)


def _deshacer(eid, cid, clave):
    alm = comun.almacen()
    rev = alm.revisiones(eid)
    rev["campos"].pop(clave_revision(cid, clave), None)
    alm.guardar_revisiones(eid, rev)


def _guardar_texto(eid, cid, pregunta, opcion, clave_widget):
    alm = comun.almacen()
    rev = alm.revisiones(eid)
    texto = (st.session_state.get(clave_widget) or "").strip()
    k = clave_texto(cid, pregunta, opcion)
    if texto:
        rev["textos"][k] = texto
    else:
        rev["textos"].pop(k, None)
    alm.guardar_revisiones(eid, rev)


def _guardar_descartados(eid, clave_widget):
    alm = comun.almacen()
    rev = alm.revisiones(eid)
    rev["descartados"] = list(st.session_state.get(clave_widget) or [])
    alm.guardar_revisiones(eid, rev)


def _sugerencia(campo):
    """Para marcas débiles sin respuesta clara: la casilla con más tinta (solo como propuesta)."""
    if campo.seleccion or not campo.tinta or max(campo.tinta) < TINTA_VACIA:
        return None
    return max(range(len(campo.tinta)), key=lambda k: campo.tinta[k])


def _campo_maqueta(alm, eid, item):
    m = alm.maqueta(eid, item.ref.resultado.huella)
    if not m:
        return None
    for c in m.paginas[item.ref.resultado.indice].campos:
        if c["clave"] == item.clave:
            return c
    return None


def _tab_dudas(alm, eid, enc, cons):
    revisiones = alm.revisiones(eid)
    ver_todas = st.toggle("Mostrar también las ya revisadas", key="rev_todas")
    items = [d for d in cons.dudas if d.cuestionario not in cons.descartados]
    if not ver_todas:
        items = [d for d in items if clave_revision(d.cuestionario, d.clave) not in revisiones["campos"]]
    if not items:
        st.success("No hay respuestas dudosas pendientes. 🎉")
        return
    paginas = (len(items) - 1) // POR_PAGINA + 1
    c1, c2 = st.columns([1, 3])
    pag = c1.number_input(f"Página (de {paginas})", 1, paginas, 1, key="rev_pag") if paginas > 1 else 1
    visibles = items[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]
    c2.button("✔ Aceptar la lectura automática en todas las de esta página", on_click=_aceptar_todas,
              args=(eid, visibles), help="Las dobles marcas quedan como «sin respuesta».")
    for it in visibles:
        e = enc.pregunta(it.pregunta)
        campo = it.campo
        opciones = _opciones(e, campo)
        multiple = campo.tipo == "multiple"
        k_rev = clave_revision(it.cuestionario, it.clave)
        revisado = k_rev in revisiones["campos"]
        actual = revisiones["campos"].get(k_rev, campo.seleccion)
        with st.container(border=True):
            cabecera = f"**Cuestionario {it.cuestionario}** · {e.numero} {e.texto[:90]}"
            if campo.tipo == "escala" and e.filas[campo.fila]:
                cabecera += f" · fila «{e.filas[campo.fila]}»"
            if campo.tipo == "numero":
                cabecera += f" · {campo.fila + 1}ª cifra"
            st.markdown(cabecera)
            ci, cc = st.columns([3, 2])
            cm = _campo_maqueta(alm, eid, it)
            img = recorte_pregunta(alm, eid, it.ref, it.pregunta, [(cm, campo)] if cm else None)
            if img is not None:
                ci.image(comun.png(img), width="stretch")
            ci.caption(f"Recuadro verde = lo que ha leído el programa. Motivo de la duda: {campo.motivo or '—'} · "
                       f"{it.ref.resultado.origen}")
            kw = f"rev:{eid}:{k_rev}"
            if multiple:
                comun.iniciar(kw, list(actual))
                cc.multiselect("Opciones marcadas", list(range(len(opciones))), key=kw,
                               format_func=lambda k: opciones[k], placeholder="Elige…")
            else:
                comun.iniciar(kw, actual[0] if len(actual) == 1 else (SIN_RESPUESTA if revisado else
                                                                       _sugerencia(campo)))
                cc.radio("Respuesta correcta", [SIN_RESPUESTA] + list(range(len(opciones))), key=kw,
                         format_func=lambda k: "— Sin respuesta / no se puede saber —" if k == SIN_RESPUESTA
                         else opciones[k], horizontal=len(opciones) > 6)
            b1, b2 = cc.columns(2)
            b1.button("💾 Guardar" if not revisado else "💾 Cambiar", key=f"g:{kw}", type="primary",
                      on_click=_guardar_campo, args=(eid, it.cuestionario, it.clave, kw, multiple), width="stretch")
            if revisado:
                b2.button("↩️ Deshacer", key=f"d:{kw}", on_click=_deshacer, args=(eid, it.cuestionario, it.clave),
                          width="stretch")
                cc.caption("✅ Revisada")


def _tab_textos(alm, eid, enc, cons):
    items = [t for t in cons.textos if t.cuestionario not in cons.descartados]
    if not items:
        st.info("No se ha detectado texto escrito a mano en las respuestas abiertas.")
        return
    revisiones = alm.revisiones(eid)
    hechos = sum(1 for t in items if clave_texto(t.cuestionario, t.pregunta, t.opcion) in revisiones["textos"])
    st.caption(f"{hechos} de {len(items)} transcritos. Transcribirlos es opcional: los que no se transcriban "
               "aparecen como imagen en un anexo del informe.")
    solo_pendientes = st.toggle("Mostrar solo los pendientes de transcribir", value=True, key="tx_pend")
    if solo_pendientes:
        items = [t for t in items if clave_texto(t.cuestionario, t.pregunta, t.opcion) not in revisiones["textos"]]
    paginas = max(1, (len(items) - 1) // POR_PAGINA + 1)
    pag = st.number_input(f"Página (de {paginas})", 1, paginas, 1, key="tx_pag") if paginas > 1 else 1
    for it in items[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]:
        e = enc.pregunta(it.pregunta)
        with st.container(border=True):
            titulo = f"**Cuestionario {it.cuestionario}** · {e.numero} {e.texto[:90]}"
            if it.opcion is not None:
                titulo += f" · «{e.opciones[it.opcion]}»"
            st.markdown(titulo)
            img = recorte_texto(alm, eid, it.ref, it.pregunta, it.tipo_texto, it.opcion)
            if img is not None:
                st.image(comun.png(img), width="stretch")
            k = clave_texto(it.cuestionario, it.pregunta, it.opcion)
            kw = f"tx:{eid}:{k}"
            comun.iniciar(kw, revisiones["textos"].get(k, ""))
            st.text_input("Transcripción", key=kw, on_change=_guardar_texto,
                          args=(eid, it.cuestionario, it.pregunta, it.opcion, kw),
                          placeholder="Escribe lo que pone y pulsa Intro")


def _tab_errores(alm, eid, cons):
    if not cons.errores:
        st.success("Todas las páginas escaneadas se han leído.")
        return
    st.caption("Estas páginas no se han podido leer. Lo habitual es volver a escanearlas (rectas, completas y sin "
               "tapar las esquinas) y subirlas otra vez.")
    for r in cons.errores:
        c1, c2 = st.columns([1, 4])
        ruta = alm.ruta_lote(eid, r.lote) / r.resultado.imagen
        if r.resultado.imagen and ruta.exists():
            c1.image(str(ruta), width=140)
        c2.error(f"**Lote {r.lote} · {r.resultado.origen}**  \n{r.resultado.error}")


def _tab_cuestionarios(alm, eid, enc, cons):
    if not cons.cuestionarios:
        st.info("Todavía no hay cuestionarios leídos.")
        return
    pendientes = {}
    for d in cons.dudas_pendientes:
        pendientes[d.cuestionario] = pendientes.get(d.cuestionario, 0) + 1
    filas = [{"Cuestionario": c.id, "Nº impreso": c.hoja or "", "Páginas leídas": len(c.paginas),
              "Faltan páginas": ", ".join(str(i + 1) for i in c.faltan), "Dudas pendientes": pendientes.get(c.id, 0),
              "Lote": next(iter(c.paginas.values())).lote}
             for c in cons.cuestionarios]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    ids = [c.id for c in cons.cuestionarios]
    kw = f"desc:{eid}"
    comun.iniciar(kw, [x for x in cons.descartados if x in ids])
    st.multiselect("Cuestionarios que NO deben contar en los resultados (hojas de prueba, rellenadas por error…)",
                   ids, key=kw, on_change=_guardar_descartados, args=(eid, kw), placeholder="Elige…")
    elegido = st.selectbox("Ver las hojas de un cuestionario", [""] + ids, format_func=lambda x: x or "—")
    if elegido:
        c = next(x for x in cons.cuestionarios if x.id == elegido)
        cols = st.columns(max(1, len(c.paginas)))
        for col, (indice, ref) in zip(cols, sorted(c.paginas.items())):
            ruta = alm.ruta_lote(eid, ref.lote) / ref.resultado.imagen
            if ruta.exists():
                col.image(str(ruta), caption=f"Página {indice + 1} · {ref.resultado.origen}", width="stretch")


def pagina():
    st.title("🔍 Revisar dudas")
    activa = comun.encuesta_activa()
    if not activa:
        return
    alm, eid, enc = activa
    st.caption(f"{enc.titulo} · {enc.subtitulo}" if enc.subtitulo else enc.titulo)
    if not alm.lotes(eid):
        st.info("Todavía no se ha subido ningún escaneo de esta encuesta.")
        st.page_link(comun.PAGINAS["leer"], label="Ir a «Leer escaneos»", icon="📥")
        return
    cons = consolidar(alm, eid, enc)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cuestionarios", len(cons.validos))
    c2.metric("Dudas pendientes", len(cons.dudas_pendientes))
    c3.metric("Textos escritos", len([t for t in cons.textos if t.cuestionario not in cons.descartados]))
    c4.metric("Páginas sin leer", len(cons.errores))
    for aviso in cons.avisos:
        st.warning(aviso)
    t1, t2, t3, t4 = st.tabs([f"Dudas ({len(cons.dudas_pendientes)})", "Textos escritos a mano",
                              f"Páginas sin leer ({len(cons.errores)})", "Cuestionarios"])
    with t1:
        _tab_dudas(alm, eid, enc, cons)
    with t2:
        _tab_textos(alm, eid, enc, cons)
    with t3:
        _tab_errores(alm, eid, cons)
    with t4:
        _tab_cuestionarios(alm, eid, enc, cons)
