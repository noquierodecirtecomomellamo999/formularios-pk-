# OMRChecker (copia incluida)

Este directorio contiene el código fuente (`src/`) del proyecto de código abierto
**OMRChecker** de Udayraj Deshmukh y colaboradores, distribuido bajo licencia MIT
(ver `LICENSE`).

- Repositorio original: https://github.com/Udayraj123/OMRChecker
- Versión copiada: commit `5cf44a5a9c7a49e2e541c6e19aefd09a41a4d494` (4 sep 2026)

El código se incluye **sin modificaciones** (solo se ha omitido su carpeta `src/tests`). El programa lo usa como motor de
lectura de casillas a través de `encuestas_omr/motor_omrchecker.py`, que:

1. Genera automáticamente un `template.json` de OMRChecker por cada página del
   formulario (a partir de la maquetación, sin calibrar nada a mano).
2. Llama a `Template` y a `ImageInstanceOps.read_omr_response` sobre la página ya
   enderezada.

Para actualizarlo basta con sustituir la carpeta `src/` por la de una versión
más reciente del repositorio original.
