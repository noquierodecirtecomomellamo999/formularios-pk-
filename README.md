# Encuestas OMR

Programa para **diseñar cuestionarios en papel, leerlos automáticamente después de escanearlos y obtener
los resultados con tablas, gráficos e informe en PDF**.

1. Escribes las preguntas en el programa, o las importas de un documento de Word.
2. El programa crea un PDF para imprimir. Cada hoja lleva casillas, unas marcas en las esquinas y un código QR.
3. Escaneas las hojas rellenadas y subes el PDF del escáner.
4. El programa lee las casillas. Lo que no está claro, como una doble marca o una marca muy débil, te lo enseña para que decidas con un clic.
5. Obtienes los gráficos de barras o de quesito, las tablas, el **informe PDF** y un **Excel** con todas las respuestas.

Funciona en tu ordenador, sin internet una vez instalado, y es gratuito. Para leer las casillas usa
**[OMRChecker](https://github.com/Udayraj123/OMRChecker)**, un lector de marcas ópticas (OMR) de código
abierto con licencia MIT.

---

## Instalación en Windows (lo normal)

1. Descarga el instalador:
   **[Instalar-Encuestas-CIRENC.exe](https://github.com/noquierodecirtecomomellamo999/formularios-pk-/releases/latest/download/Instalar-Encuestas-CIRENC.exe)**
2. Haz doble clic en él.
   - Si aparece «Windows protegió su PC», pulsa **Más información → Ejecutar de todas formas**. Sale porque el programa no está firmado por una empresa de software.
   - Deja marcado **«Crear un icono en el escritorio»** y pulsa **Instalar**.
3. Ábrelo con el icono **Encuestas CIRENC** del escritorio. Se abre en el navegador.

Cosas que conviene saber:
- **No hace falta instalar nada más**: el instalador lleva todo lo necesario, Python incluido.
- No necesita internet ni permisos de administrador.
- Los datos se guardan en **Documentos › Encuestas CIRENC**.
- Para cerrarlo, usa el botón **«Cerrar el programa»** del menú de la izquierda.

**Guía rápida.** Tienes una guía rápida para imprimir:
- en el menú Inicio, como «Guía rápida de Encuestas CIRENC»;
- o descargándola aquí: [Guia-rapida-Encuestas-CIRENC.pdf](https://github.com/noquierodecirtecomomellamo999/formularios-pk-/releases/latest/download/Guia-rapida-Encuestas-CIRENC.pdf).

**Versión portable (sin instalar).** También hay una versión que no se instala:
[Encuestas-CIRENC-portable.zip](https://github.com/noquierodecirtecomomellamo999/formularios-pk-/releases/latest/download/Encuestas-CIRENC-portable.zip).
Se descomprime y se abre con «Abrir Encuestas CIRENC.bat».

> El instalador se construye y se prueba solo, en un Windows de GitHub (instalar, abrir, leer hojas, desinstalar), cada vez que se cambia el programa. Ver [`.github/workflows/instalador.yml`](.github/workflows/instalador.yml).

### Instalar desde el código (para quien vaya a modificar el programa)

1. **Instala Python** 3.10 o posterior desde <https://www.python.org/downloads/>, marcando **«Add python.exe to PATH»**.
2. Descarga el código: en GitHub, *Code → Download ZIP*, y descomprímelo.
3. Haz doble clic en **`instalar.bat`**. La primera vez tarda unos minutos.
4. Ábrelo con **`iniciar.bat`**.

> En Linux o macOS: `./iniciar.sh`.

La primera vez aparecen cargadas como ejemplo las cuatro encuestas de CIRENC de 2026:
- Centro de Día
- Medio Rural
- Tratamiento Ambulatorio
- Familiares

## Cómo se usa

En el menú de la izquierda eliges la **encuesta de trabajo** y vas por los pasos:

### 1. Diseñar encuesta

**Tipos de pregunta**

| Tipo | Para qué sirve |
|---|---|
| Respuesta única | Muy bien / Bien / Regular / Mal, Sí / No… Se puede añadir una línea de «especifique». |
| Respuesta múltiple | «Puede marcar varias opciones». |
| Escala / tabla de valoración | Varios servicios valorados de 0 a 10, de 1 a 5…, con columnas extra como «No usa». |
| Número | Edad, años en el centro… Se marca por cifras. |
| Respuesta abierta | Comentarios y sugerencias. Se guarda la imagen y se puede transcribir. |
| Secciones y textos | Títulos de apartado e instrucciones, como «7. Refiriéndonos a…» antes de a), b), c). |

**Botones de la parte de arriba**
- **Importar de Word**: sube el `.docx` del cuestionario y el programa reconoce las preguntas, las opciones y las tablas 0–10. Después solo hay que revisarlo.
- **Duplicar**: para repetir la encuesta otro año o en otro programa sin volver a escribirla.

**Otras pestañas**
- En «Título, cabecera y logos» se ponen los datos de la organización y los logos.
- En «Vista previa» se ve cómo quedará la hoja.

Los cambios se guardan solos.

### 2. Imprimir
- **Copias numeradas** (recomendado). Cada cuestionario lleva su número en todas sus páginas. Así da igual el orden en que se escaneen y se detecta si falta alguna página. El número no identifica a la persona: la encuesta sigue siendo **anónima**.
- **Hoja sin numerar** para fotocopiar. En ese caso hay que escanear cada cuestionario con sus páginas seguidas y en orden.

Imprime a **tamaño real (100 %)**, en papel blanco A4. Se puede imprimir a doble cara.

### 3. Leer escaneos

**Cómo escanear**
- Escanea a **200 o 300 ppp**, en gris o blanco y negro, en un **PDF de varias páginas**.
- También valen imágenes JPG, PNG o TIFF.
- Si la hoja entra algo torcida o del revés, no pasa nada.

**Probar sin imprimir.** En «Probar sin imprimir» puedes generar cuestionarios rellenados al azar para ver todo el proceso. Después borra ese lote de prueba.

### 4. Revisar dudas

**Dudas.** El programa enseña un recorte de cada pregunta dudosa con lo que ha leído marcado en verde. Eliges la respuesta correcta y pulsas «Guardar». Las dudas típicas son:
- dos casillas marcadas;
- una marca muy débil;
- un círculo alrededor de la casilla en lugar de una X.

**Comentarios escritos a mano.** Se pueden transcribir. Los que no se transcriban salen como imagen en un anexo del informe.

**Hojas que no deben contar.** Puedes descartar hojas de prueba o rellenadas por error.

### 5. Resultados e informe

Para cada pregunta se muestra:
- el gráfico: automático, quesito, barras verticales u horizontales;
- la tabla «Respuesta · Personas · Porcentaje»;
- la frase de **Resultado**, que puedes editar. Por ejemplo: «El 88 % elige «Muy positivo» o «Bastante positivo». Un 8 % «Regular» y un 4 % «Negativo».»

En las escalas salen la media, la mediana y el % que puntúa 8 o más; el umbral se puede cambiar.

**Respuestas favorables.** Marca qué respuestas son «favorables» para que la frase de resumen las sume.

**En la pestaña «Informe y exportación»**
- Edita el título, la introducción, las conclusiones (salen propuestas automáticamente) y el texto final (lugar, fecha, firma).
- Genera el **informe PDF** y el **Excel**.

## Consejos para que la lectura sea fiable

**Al repartir los cuestionarios**
- Pide que marquen con una **X dentro de la casilla**, con bolígrafo o lápiz oscuro.
- Para anular una respuesta, que **rellenen entera** la casilla equivocada y marquen la buena con una X. El programa lo entiende.
- No grapes ni escribas sobre los **cuadrados negros de las esquinas** ni sobre el **código QR**.

**Si cambias la encuesta después de imprimirla**, las hojas ya impresas se siguen leyendo bien, porque cada versión impresa queda guardada. Para cambios grandes es mejor **duplicar** la encuesta.

## Dónde se guardan los datos

En Windows, todo se guarda en **Documentos › Encuestas CIRENC**:
- las encuestas;
- las versiones impresas;
- los escaneos;
- las revisiones;
- los informes.

En el programa, el botón «Abrir la carpeta de datos» la abre.

- **Copia de seguridad**: basta con copiar esa carpeta.
- **Actualizar o desinstalar el programa no la borra.**
- Las encuestas borradas van a la subcarpeta `papelera`.

Se puede usar otra carpeta con la variable de entorno `ENCUESTAS_OMR_DATOS`.

## Cómo funciona la lectura

1. **Enderezado.** Las 4 marcas de las esquinas (marcadores ArUco) dicen qué página es y cómo está colocada. Con eso se endereza la imagen, aunque esté girada, desplazada o escaneada a otra resolución.
2. **Identificación.** El **código QR** indica la versión impresa de la encuesta y el número de cuestionario.
3. **Ajuste fino.** Se afina la posición de cada grupo de casillas buscando su borde impreso.
4. **Lectura.** **OMRChecker** decide qué casillas están marcadas, a partir de una plantilla que el programa genera solo desde el diseño. No hay que calibrar nada a mano.
5. **Comprobación.** Como segunda comprobación se mide la tinta dentro de cada casilla. Así también se distingue una X de una casilla rellena (anulada).
6. **Decisión.** Si los dos métodos coinciden, la respuesta se da por buena. Si no, o si hay dobles marcas o marcas débiles, va a **revisión**.

**Pruebas con hojas simuladas.** Se ha probado con cuestionarios rellenados y escaneados por ordenador:
- marcas de bolígrafo, lápiz, lápiz muy claro, ticks y X pequeñas;
- hojas torcidas o del revés;
- escaneos a 150, 200 y 300 ppp.

En todas esas pruebas **no hubo ninguna respuesta mal leída sin avisar**. Las marcas raras, como un círculo alrededor de la casilla o un temblor muy fuerte, se mandan a revisión.

> Conviene hacer una prueba real con la impresora y el escáner que vayáis a usar, con unas pocas hojas, antes de la primera encuesta grande.

## Para desarrolladores

```
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt      (Windows)
.venv/bin/pip install -r requirements-dev.txt          (Linux/macOS)
python -m pytest                                       # pruebas automáticas
python -m streamlit run app/inicio.py                  # la aplicación
```

| Carpeta / archivo | Contenido |
|---|---|
| `encuestas_omr/` | Modelo, maquetación, PDF, lector OMR, análisis, gráficos, informe |
| `app/` | Interfaz (Streamlit) |
| `ejemplos/` | Encuestas de ejemplo y logo |
| `lanzador.py` | Abre el programa (lo usan el icono del escritorio y `iniciar.bat`) |
| `instalador/` | Construcción del instalador de Windows, prueba del paquete y guía rápida |
| `tests/` | Pruebas (con un simulador que rellena y «escanea» hojas) |
| `third_party/OMRChecker/` | Copia sin modificar de OMRChecker (licencia MIT) |

**Código de terceros**
- OMRChecker (MIT): © Udayraj Deshmukh y colaboradores.
- Las fuentes DejaVu vienen incluidas con matplotlib.

**Publicar una versión nueva del instalador**
1. Cambia el número en `encuestas_omr/__init__.py`.
2. En GitHub: *Actions → Instalador de Windows → Run workflow*.

El instalador se construye, se prueba y se publica en *Releases*. Los enlaces de descarga de arriba apuntan siempre a la última versión.
