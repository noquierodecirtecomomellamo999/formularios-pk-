"""Página 1: diseño de la encuesta (editor de preguntas, cabecera y vista previa)."""

import copy
import re
import tempfile
from pathlib import Path

import streamlit as st

import comun
from comun import iniciar, lineas
from encuestas_omr.formulario_pdf import generar_pdf
from encuestas_omr.importar import desde_texto, importar_archivo
from encuestas_omr.maquetacion import maquetar
from encuestas_omr.modelo import ESCALAS_PREDEFINIDAS, TIPOS, Elemento, Encuesta, asignar_ids, nuevo_elemento, validar

ICONOS = {"seccion": "🔷", "texto": "📄", "unica": "🔘", "multiple": "☑️", "escala": "📶", "numero": "🔢",
          "abierta": "✏️"}
DISPOSICION = {"auto": "Automática (en fila si caben)", "vertical": "Una debajo de otra", "horizontal": "En una fila"}
PERSONALIZADA = "Personalizada…"


def _k(eid: str, e: Elemento, campo: str) -> str:
    return f"ed:{eid}:{e.id}:{campo}"


# --------------------------------------------------------------------------- acciones (callbacks)
def _mover(eid, elem_id, delta):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    i = next(i for i, x in enumerate(enc.elementos) if x.id == elem_id)
    j = i + delta
    if 0 <= j < len(enc.elementos):
        enc.elementos[i], enc.elementos[j] = enc.elementos[j], enc.elementos[i]
        alm.guardar(enc)


def _borrar(eid, elem_id):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    enc.elementos = [x for x in enc.elementos if x.id != elem_id]
    alm.guardar(enc)


def _anadir(eid, clave_tipo, despues_de=None):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    tipo = st.session_state[clave_tipo]
    nuevo = nuevo_elemento(tipo)
    if despues_de is None:
        enc.elementos.append(nuevo)
    else:
        i = next(i for i, x in enumerate(enc.elementos) if x.id == despues_de)
        enc.elementos.insert(i + 1, nuevo)
    asignar_ids(enc)
    alm.guardar(enc)
    st.session_state["ed_abierto"] = nuevo.id


def _numerar(eid, modo):
    """Numera todas las preguntas: «1., 2., 3.…» o «1.1., 1.2.…» por secciones (respeta a), b), c)…)."""
    alm = comun.almacen()
    enc = alm.cargar(eid)
    seccion = n = k = 0
    for e in enc.elementos:
        if e.tipo == "seccion":
            seccion, n = seccion + 1, 0
            continue
        if not (e.es_pregunta or e.tipo == "texto") or re.fullmatch(r"[a-zA-Z]\)", e.numero or ""):
            continue
        n, k = n + 1, k + 1
        e.numero = f"{seccion}.{n}." if (modo == "secciones" and seccion) else f"{k}."
    alm.guardar(enc)
    for e in enc.elementos:  # refresca los campos «Número» del editor
        st.session_state.pop(f"ed:{eid}:{e.id}:numero", None)


def _quitar_logo(eid, nombre):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    enc.cabecera.logos = [x for x in enc.cabecera.logos if x != nombre]
    alm.guardar(enc)


# --------------------------------------------------------------------------- diálogos
@st.dialog("Nueva encuesta")
def _dialogo_nueva(eid_actual):
    alm = comun.almacen()
    titulo = st.text_input("Título", placeholder="Cuestionario de satisfacción")
    subtitulo = st.text_input("Subtítulo (programa, año…)", placeholder="Programa Centro de Día · Año 2027")
    copiar = st.checkbox("Usar la misma cabecera, logos y pie que la encuesta actual", value=bool(eid_actual))
    if st.button("Crear", type="primary", disabled=not titulo.strip()):
        nueva = alm.crear(titulo.strip(), subtitulo.strip())
        if copiar and eid_actual:
            base = alm.cargar(eid_actual)
            nueva.cabecera = copy.deepcopy(base.cabecera)
            nueva.pie, nueva.instrucciones, nueva.despedida = base.pie, base.instrucciones, base.despedida
            alm.guardar(nueva)
            for logo in base.cabecera.logos:
                origen = alm.recursos(eid_actual) / logo
                if origen.exists():
                    (alm.recursos(nueva.id) / logo).write_bytes(origen.read_bytes())
        comun.seleccionar(nueva.id)
        st.rerun()


@st.dialog("Duplicar encuesta")
def _dialogo_duplicar(eid):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    st.caption("Se copian las preguntas, la cabecera y los logos (no los escaneos ni los resultados). "
               "Útil para repetir la encuesta otro año o en otro programa.")
    titulo = st.text_input("Título", value=enc.titulo)
    subtitulo = st.text_input("Subtítulo", value=enc.subtitulo)
    if st.button("Duplicar", type="primary"):
        nueva = alm.duplicar(eid, titulo, subtitulo)
        comun.seleccionar(nueva.id)
        st.rerun()


@st.dialog("Importar preguntas", width="large")
def _dialogo_importar(eid):
    alm = comun.almacen()
    st.caption("Sube el cuestionario en Word (.docx) o pega el texto. El programa reconoce las preguntas, las "
               "opciones y las tablas de valoración; después puedes corregir lo que haga falta en el editor.")
    archivo = st.file_uploader("Documento de Word o texto", type=["docx", "txt"])
    texto = st.text_area("…o pega aquí el texto", height=180,
                         placeholder="# 1. Atención\n1.1. ¿Cómo valora el trato?\n- Muy bien\n- Bien\n- Regular\n- Mal\n"
                                     "1.2. Valore de 0 a 10:\nTransporte: 0 1 2 3 4 5 6 7 8 9 10")
    enc_imp = None
    try:
        if archivo is not None:
            enc_imp = importar_archivo(archivo.name, archivo.getvalue())
        elif texto.strip():
            enc_imp = desde_texto(texto)
    except Exception as e:  # documento con un formato inesperado
        st.error(f"No se ha podido interpretar el documento: {e}")
    if enc_imp is None:
        return
    st.success(f"Se han reconocido {len(enc_imp.preguntas)} preguntas.")
    with st.container(height=260):
        for e in enc_imp.elementos:
            detalle = ""
            if e.tipo in ("unica", "multiple"):
                detalle = " · ".join(e.opciones)
            elif e.tipo == "escala":
                detalle = f"{e.valores[0]}–{e.valores[-1]} · " + " / ".join(f or "(una fila)" for f in e.filas)
            st.markdown(f"{ICONOS.get(e.tipo, '')} **{e.numero} {e.texto}**  \n<small>{TIPOS[e.tipo]} · {detalle}</small>",
                        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Crear una encuesta nueva con esto", type="primary"):
        base = alm.cargar(eid) if eid else None
        nueva = alm.crear(enc_imp.titulo, enc_imp.subtitulo)
        nueva.elementos, nueva.introduccion = enc_imp.elementos, enc_imp.introduccion or nueva.introduccion
        if enc_imp.despedida:
            nueva.despedida = enc_imp.despedida
        if base:
            nueva.cabecera, nueva.pie = copy.deepcopy(base.cabecera), base.pie
            for logo in base.cabecera.logos:
                origen = alm.recursos(eid) / logo
                if origen.exists():
                    (alm.recursos(nueva.id) / logo).write_bytes(origen.read_bytes())
        alm.guardar(nueva)
        comun.seleccionar(nueva.id)
        st.rerun()
    if eid and c2.button("Añadirlas al final de la encuesta actual"):
        enc = alm.cargar(eid)
        usados = {e.id for e in enc.elementos}
        for e in enc_imp.elementos:
            if e.id in usados:
                e.id = ""
            enc.elementos.append(e)
        asignar_ids(enc)
        alm.guardar(enc)
        st.rerun()


@st.dialog("Borrar encuesta")
def _dialogo_borrar(eid):
    alm = comun.almacen()
    enc = alm.cargar(eid)
    st.warning(f"Se va a borrar «{enc.titulo} {enc.subtitulo}» con sus escaneos y resultados. "
               "Se mueve a la carpeta `papelera` dentro de los datos, por si hubiera que recuperarla.")
    if st.checkbox("Sí, quiero borrarla") and st.button("Borrar", type="primary"):
        alm.borrar(eid)
        st.session_state.pop("encuesta_id", None)
        st.session_state.pop("sel_encuesta", None)
        st.rerun()


# --------------------------------------------------------------------------- editor de un elemento
def _editor_elemento(eid: str, e: Elemento, i: int, total: int) -> Elemento:
    n = copy.deepcopy(e)
    resumen = f"{e.numero} {e.texto}".strip() or TIPOS[e.tipo]
    if len(resumen) > 90:
        resumen = resumen[:89] + "…"
    with st.expander(f"{ICONOS[e.tipo]} {resumen}", expanded=st.session_state.get("ed_abierto") == e.id):
        c_tipo, c_botones = st.columns([3, 2])
        c_tipo.caption(f"Elemento {i + 1} de {total} · {TIPOS[e.tipo]}")
        b1, b2, b3 = c_botones.columns(3)
        b1.button("⬆️", key=_k(eid, e, "subir"), help="Subir", on_click=_mover, args=(eid, e.id, -1),
                  disabled=i == 0, width="stretch")
        b2.button("⬇️", key=_k(eid, e, "bajar"), help="Bajar", on_click=_mover, args=(eid, e.id, 1),
                  disabled=i == total - 1, width="stretch")
        b3.button("🗑️", key=_k(eid, e, "borrar"), help="Borrar", on_click=_borrar, args=(eid, e.id),
                  width="stretch")

        if e.tipo == "seccion":
            n.texto = st.text_input("Título de la sección", key=iniciar(_k(eid, e, "texto"), e.texto))
            return n
        c_num, c_txt = st.columns([1, 6])
        n.numero = c_num.text_input("Número", key=iniciar(_k(eid, e, "numero"), e.numero), placeholder="1.1.")
        etiqueta = "Texto" if e.tipo == "texto" else "Pregunta"
        n.texto = c_txt.text_area(etiqueta, key=iniciar(_k(eid, e, "texto"), e.texto), height=68)
        if e.tipo in ("unica", "multiple"):
            c1, c2 = st.columns([3, 2])
            opciones_txt = c1.text_area("Opciones (una por línea)", key=iniciar(_k(eid, e, "opciones"),
                                                                                  "\n".join(e.opciones)), height=140)
            n.opciones = lineas(opciones_txt)
            n.tipo = c2.radio("Se puede marcar", ["unica", "multiple"], key=iniciar(_k(eid, e, "tipo"), e.tipo),
                              format_func=lambda t: "Una sola opción" if t == "unica" else "Varias opciones")
            n.disposicion = c2.selectbox("Colocación de las opciones", list(DISPOSICION),
                                         key=iniciar(_k(eid, e, "disp"), e.disposicion),
                                         format_func=DISPOSICION.get)
            indices = list(range(len(n.opciones)))
            clave = iniciar(_k(eid, e, "con_texto"), list(e.con_texto))
            st.session_state[clave] = [k for k in st.session_state[clave] if k in indices]
            n.con_texto = c2.multiselect("Con línea para escribir («especifique»)", indices, key=clave,
                                         format_func=lambda k: n.opciones[k])
            n.favorables = [k for k in e.favorables if k < len(n.opciones)]
        elif e.tipo == "escala":
            c1, c2 = st.columns([3, 2])
            filas_txt = c1.text_area("Aspectos a valorar (uno por línea; vacío = una sola fila)",
                                     key=iniciar(_k(eid, e, "filas"), "\n".join(f for f in e.filas if f)), height=140)
            n.filas = lineas(filas_txt) or [""]
            presets = list(ESCALAS_PREDEFINIDAS) + [PERSONALIZADA]
            actual = next((k for k, v in ESCALAS_PREDEFINIDAS.items() if v == e.valores), PERSONALIZADA)
            elegido = c2.selectbox("Escala", presets, key=iniciar(_k(eid, e, "escala"), actual))
            if elegido == PERSONALIZADA:
                txt = c2.text_input("Valores separados por comas", key=iniciar(_k(eid, e, "valores"),
                                                                                ", ".join(e.valores)))
                n.valores = [v.strip() for v in txt.split(",") if v.strip()]
            else:
                n.valores = list(ESCALAS_PREDEFINIDAS[elegido])
            extras = c2.text_input("Columnas extra (separadas por comas)", key=iniciar(_k(eid, e, "extras"),
                                                                                      ", ".join(e.extras)),
                                   placeholder="No usa", help="Respuestas que no puntúan, como «No usa» o «NS/NC».")
            n.extras = [v.strip() for v in extras.split(",") if v.strip()]
        elif e.tipo == "numero":
            n.cifras = st.number_input("Número de cifras", 1, 6, key=iniciar(_k(eid, e, "cifras"), e.cifras))
        elif e.tipo == "abierta":
            n.lineas = st.number_input("Líneas para escribir", 1, 20, key=iniciar(_k(eid, e, "lineas"), e.lineas))
    return n


# --------------------------------------------------------------------------- página
def pagina():
    alm = comun.almacen()
    eid = st.session_state.get("encuesta_id")
    st.title("📝 Diseñar encuesta")
    c = st.columns(5)
    if c[0].button("➕ Nueva", width="stretch"):
        _dialogo_nueva(eid)
    if c[1].button("📥 Importar de Word", width="stretch"):
        _dialogo_importar(eid)
    if not eid or not alm.existe(eid):
        st.info("No hay ninguna encuesta. Crea una nueva o impórtala de un documento de Word.")
        return
    if c[2].button("📄 Duplicar", width="stretch"):
        _dialogo_duplicar(eid)
    if c[4].button("🗑️ Borrar", width="stretch"):
        _dialogo_borrar(eid)

    enc = alm.cargar(eid)
    if alm.impresiones(eid) or alm.lotes(eid):
        st.info("Esta encuesta ya se ha impreso. Puedes seguir cambiándola: las hojas ya impresas se leerán con "
                "su versión original. Si el cambio es grande (otro año, otro programa), mejor **Duplicar**.", icon="ℹ️")

    tab_preg, tab_datos, tab_previa = st.tabs(["Preguntas", "Título, cabecera y logos", "Vista previa"])

    with tab_preg:
        errores = validar(enc)
        if errores:
            st.warning("Hay que corregir:\n\n" + "\n".join(f"- {x}" for x in errores))
        nuevos_elementos = [_editor_elemento(eid, e, i, len(enc.elementos)) for i, e in enumerate(enc.elementos)]
        st.divider()
        a1, a2, a3 = st.columns([2, 1, 2])
        tipos_nuevos = ["unica", "multiple", "escala", "abierta", "numero", "seccion", "texto"]
        a1.selectbox("Añadir", tipos_nuevos, key="ed_tipo_nuevo", format_func=lambda t: f"{ICONOS[t]} {TIPOS[t]}",
                     label_visibility="collapsed")
        a2.button("➕ Añadir", on_click=_anadir, args=(eid, "ed_tipo_nuevo"), width="stretch")
        with a3.popover("🔢 Numerar automáticamente", width="stretch"):
            st.caption("Pone el número a todas las preguntas (respeta los subapartados a), b), c)…).")
            st.button("1., 2., 3.…", on_click=_numerar, args=(eid, "seguido"), width="stretch")
            st.button("1.1., 1.2.… por secciones", on_click=_numerar, args=(eid, "secciones"),
                      width="stretch")

    with tab_datos:
        k = f"dg:{eid}:"
        c1, c2 = st.columns(2)
        titulo = c1.text_input("Título", key=iniciar(k + "titulo", enc.titulo))
        subtitulo = c2.text_input("Subtítulo (programa, año…)", key=iniciar(k + "subtitulo", enc.subtitulo))
        intro = st.text_area("Introducción", key=iniciar(k + "intro", enc.introduccion), height=90)
        instr = st.text_area("Instrucciones para rellenar", key=iniciar(k + "instr", enc.instrucciones), height=90)
        c1, c2, c3 = st.columns([3, 1, 1])
        despedida = c1.text_input("Frase final", key=iniciar(k + "despedida", enc.despedida))
        fecha = c2.checkbox("Casilla «Fecha»", key=iniciar(k + "fecha", enc.mostrar_fecha))
        tam = c3.number_input("Tamaño de letra", 9.5, 13.0, step=0.5, key=iniciar(k + "tam", float(enc.tamano_letra)))
        st.subheader("Cabecera y pie")
        c1, c2 = st.columns(2)
        cab = c1.text_area("Datos de la organización (una línea cada uno; la primera va en negrita)",
                           key=iniciar(k + "cab", "\n".join(enc.cabecera.lineas_izquierda)), height=120)
        pie = c2.text_input("Pie de página (web, teléfono…)", key=iniciar(k + "pie", enc.pie))
        with c2:
            st.caption("Logos")
            recursos = alm.recursos(eid)
            for nombre in enc.cabecera.logos:
                l1, l2 = st.columns([3, 1])
                if (recursos / nombre).exists():
                    l1.image(str(recursos / nombre), width=140)
                else:
                    l1.write(f"{nombre} (no encontrado)")
                l2.button("Quitar", key=f"{k}quitar:{nombre}", on_click=_quitar_logo, args=(eid, nombre))
            n_sub = st.session_state.get("logo_n", 0)
            subido = st.file_uploader("Añadir logo", type=["png", "jpg", "jpeg"], key=f"logo_up_{n_sub}")
            if subido is not None:
                nombre = alm.guardar_logo(eid, subido.name, subido.getvalue())
                enc_l = alm.cargar(eid)
                if nombre not in enc_l.cabecera.logos:
                    enc_l.cabecera.logos.append(nombre)
                    alm.guardar(enc_l)
                st.session_state["logo_n"] = n_sub + 1
                st.rerun()

    # Composición y guardado automático
    nueva = copy.deepcopy(enc)
    nueva.elementos = nuevos_elementos
    nueva.titulo, nueva.subtitulo, nueva.introduccion, nueva.instrucciones = titulo, subtitulo, intro, instr
    nueva.despedida, nueva.mostrar_fecha, nueva.tamano_letra, nueva.pie = despedida, fecha, float(tam), pie
    nueva.cabecera.lineas_izquierda = lineas(cab)
    if nueva.to_dict() != enc.to_dict():
        alm.guardar(nueva)
        st.toast("Cambios guardados", icon="💾")
        enc = nueva

    with tab_previa:
        _vista_previa(alm, eid, enc)


def _vista_previa(alm, eid, enc: Encuesta):
    errores = validar(enc)
    if errores:
        st.warning("Corrige primero los avisos de la pestaña «Preguntas».")
        return
    if not st.toggle("Mostrar vista previa", key="ed_previa"):
        st.caption("Actívalo para ver cómo quedará la hoja (se actualiza con cada cambio).")
        return
    try:
        m = maquetar(enc, alm.recursos(eid))
    except ValueError as e:
        st.error(str(e))
        return
    with tempfile.TemporaryDirectory() as tmp:
        ruta = generar_pdf(m, Path(tmp) / "previa.pdf", alm.recursos(eid), hojas=[1])
        imagenes = comun.vista_previa_pdf(ruta, dpi=80)
        datos_pdf = ruta.read_bytes()
    st.caption(f"{len(m.paginas)} página(s) por cuestionario · versión {m.huella}")
    st.download_button("Descargar esta vista previa (PDF)", datos_pdf, file_name=f"{eid}_muestra.pdf",
                       mime="application/pdf")
    cols = st.columns(min(3, len(imagenes)))
    for k, img in enumerate(imagenes):
        cols[k % len(cols)].image(img, caption=f"Página {k + 1}", width="stretch")
