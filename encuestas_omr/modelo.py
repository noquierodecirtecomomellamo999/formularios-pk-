"""Modelo de datos de una encuesta y lectura/escritura en JSON.

Una encuesta es una lista ordenada de *elementos*. Cada elemento tiene un ``tipo``:

- ``seccion``  : título de apartado (p. ej. "1. Bienvenida y ambiente del Centro").
- ``texto``    : texto informativo o subapartado, sin casillas.
- ``unica``    : pregunta de respuesta única (una casilla por opción).
- ``multiple`` : pregunta en la que se pueden marcar varias opciones.
- ``escala``   : tabla de valoración: varias filas (servicios, aspectos...) con la
                 misma escala (1-5, 0-10...) y columnas extra opcionales ("No usa").
- ``numero``   : número escrito con casillas por cifra (edad, años en el centro...).
- ``abierta``  : respuesta libre escrita a mano (se guarda el recorte de imagen).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

TIPOS = {
    "seccion": "Título de sección",
    "texto": "Texto / subapartado",
    "unica": "Respuesta única",
    "multiple": "Respuesta múltiple",
    "escala": "Escala / tabla de valoración",
    "numero": "Número (por cifras)",
    "abierta": "Respuesta abierta (texto libre)",
}
TIPOS_PREGUNTA = ("unica", "multiple", "escala", "numero", "abierta")

DISPOSICIONES = ("auto", "vertical", "horizontal")
GRAFICOS = {
    "auto": "Automático",
    "quesito": "Quesito (tarta)",
    "barras": "Barras verticales",
    "barras_h": "Barras horizontales",
    "ninguno": "Sin gráfico",
}

INSTRUCCIONES_POR_DEFECTO = (
    "Marque con una X la casilla de la respuesta elegida, dentro del cuadro. "
    "Puede usar bolígrafo o lápiz oscuro. Si se equivoca, rellene por completo "
    "la casilla equivocada y marque con una X la correcta."
)

# Las escalas más habituales, para ofrecerlas en el editor.
ESCALAS_PREDEFINIDAS = {
    "0 a 10": [str(i) for i in range(11)],
    "1 a 5": [str(i) for i in range(1, 6)],
    "1 a 10": [str(i) for i in range(1, 11)],
    "Nada / Poco / Bastante / Mucho": ["Nada", "Poco", "Bastante", "Mucho"],
}


@dataclass
class Elemento:
    tipo: str
    id: str = ""
    texto: str = ""
    numero: str = ""
    # unica / multiple
    opciones: list[str] = field(default_factory=list)
    con_texto: list[int] = field(default_factory=list)  # opciones con línea "especifique"
    disposicion: str = "auto"
    favorables: list[int] = field(default_factory=list)  # para las frases de resultado
    # escala
    valores: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    filas: list[str] = field(default_factory=list)
    umbral: float | None = None
    # numero
    cifras: int = 2
    # abierta
    lineas: int = 3
    # análisis
    grafico: str = "auto"

    @property
    def es_pregunta(self) -> bool:
        return self.tipo in TIPOS_PREGUNTA

    @property
    def etiqueta(self) -> str:
        """Número + texto, tal como aparece en el formulario."""
        return f"{self.numero} {self.texto}".strip() if self.numero else self.texto

    def puntuaciones(self) -> list[float]:
        """Valor numérico de cada columna puntuable de una escala.

        Si las etiquetas son números ("0".."10") se usa ese número; si son palabras
        ("Nada", "Poco"...) se usa la posición 1, 2, 3...
        """
        nums = []
        for v in self.valores:
            try:
                nums.append(float(v.replace(",", ".")))
            except ValueError:
                return [float(i + 1) for i in range(len(self.valores))]
        return nums

    def to_dict(self) -> dict:
        d = {"tipo": self.tipo, "id": self.id}
        if self.numero:
            d["numero"] = self.numero
        d["texto"] = self.texto
        if self.tipo in ("unica", "multiple"):
            d["opciones"] = list(self.opciones)
            if self.con_texto:
                d["con_texto"] = list(self.con_texto)
            if self.disposicion != "auto":
                d["disposicion"] = self.disposicion
            if self.favorables:
                d["favorables"] = list(self.favorables)
        elif self.tipo == "escala":
            d["valores"] = list(self.valores)
            if self.extras:
                d["extras"] = list(self.extras)
            d["filas"] = list(self.filas)
            if self.umbral is not None:
                d["umbral"] = self.umbral
        elif self.tipo == "numero":
            d["cifras"] = self.cifras
        elif self.tipo == "abierta":
            d["lineas"] = self.lineas
        if self.es_pregunta and self.grafico != "auto":
            d["grafico"] = self.grafico
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Elemento:
        conocidos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in conocidos})


@dataclass
class Cabecera:
    lineas_izquierda: list[str] = field(default_factory=list)
    lineas_derecha: list[str] = field(default_factory=list)
    logos: list[str] = field(default_factory=list)  # nombres de archivo dentro de la carpeta de la encuesta


@dataclass
class Encuesta:
    id: str
    titulo: str
    subtitulo: str = ""
    introduccion: str = ""
    instrucciones: str = INSTRUCCIONES_POR_DEFECTO
    mostrar_fecha: bool = True
    cabecera: Cabecera = field(default_factory=Cabecera)
    pie: str = ""
    despedida: str = "Muchas gracias por su colaboración"
    tamano_letra: float = 11.0
    elementos: list[Elemento] = field(default_factory=list)

    # ------------------------------------------------------------------ consultas
    @property
    def preguntas(self) -> list[Elemento]:
        return [e for e in self.elementos if e.es_pregunta]

    def pregunta(self, id_: str) -> Elemento:
        for e in self.elementos:
            if e.id == id_:
                return e
        raise KeyError(id_)

    # ------------------------------------------------------------------ JSON
    def to_dict(self) -> dict:
        return {
            "formato": "encuesta-omr/1",
            "id": self.id,
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "introduccion": self.introduccion,
            "instrucciones": self.instrucciones,
            "mostrar_fecha": self.mostrar_fecha,
            "cabecera": asdict(self.cabecera),
            "pie": self.pie,
            "despedida": self.despedida,
            "tamano_letra": self.tamano_letra,
            "elementos": [e.to_dict() for e in self.elementos],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Encuesta:
        enc = cls(
            id=d["id"],
            titulo=d.get("titulo", ""),
            subtitulo=d.get("subtitulo", ""),
            introduccion=d.get("introduccion", ""),
            instrucciones=d.get("instrucciones", INSTRUCCIONES_POR_DEFECTO),
            mostrar_fecha=d.get("mostrar_fecha", True),
            cabecera=Cabecera(**d.get("cabecera", {})),
            pie=d.get("pie", ""),
            despedida=d.get("despedida", "Muchas gracias por su colaboración"),
            tamano_letra=float(d.get("tamano_letra", 11.0)),
            elementos=[Elemento.from_dict(e) for e in d.get("elementos", [])],
        )
        asignar_ids(enc)
        return enc

    def guardar(self, ruta: Path) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def cargar(cls, ruta: Path) -> Encuesta:
        return cls.from_dict(json.loads(Path(ruta).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------- utilidades

def slug(texto: str, max_len: int = 60) -> str:
    """Convierte un texto en un identificador seguro para carpetas: 'Centro de día 2026' -> 'centro-de-dia-2026'."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:max_len].strip("-") or "encuesta"


_ID_VALIDO = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def asignar_ids(enc: Encuesta) -> None:
    """Da un id único y válido a cada elemento que no lo tenga (p1, p2..., s1..., t1...)."""
    usados = {e.id for e in enc.elementos if e.id and _ID_VALIDO.match(e.id)}
    prefijos = {"seccion": "s", "texto": "t"}
    contadores: dict[str, int] = {}
    for e in enc.elementos:
        if e.id and _ID_VALIDO.match(e.id):
            continue
        pre = prefijos.get(e.tipo, "p")
        n = contadores.get(pre, 0)
        while True:
            n += 1
            candidato = f"{pre}{n}"
            if candidato not in usados:
                break
        contadores[pre] = n
        e.id = candidato
        usados.add(candidato)


def validar(enc: Encuesta) -> list[str]:
    """Devuelve una lista de problemas (vacía si la encuesta es correcta)."""
    errores: list[str] = []
    if not enc.titulo.strip():
        errores.append("La encuesta no tiene título.")
    if not enc.preguntas:
        errores.append("La encuesta todavía no tiene preguntas.")
    vistos: set[str] = set()
    for i, e in enumerate(enc.elementos, start=1):
        nombre = f"Elemento {i} ({e.etiqueta[:40] or TIPOS.get(e.tipo, e.tipo)})"
        if e.tipo not in TIPOS:
            errores.append(f"{nombre}: tipo desconocido '{e.tipo}'.")
            continue
        if not _ID_VALIDO.match(e.id or ""):
            errores.append(f"{nombre}: identificador no válido '{e.id}'.")
        if e.id in vistos:
            errores.append(f"{nombre}: identificador repetido '{e.id}'.")
        vistos.add(e.id)
        if e.tipo in ("seccion", "texto") and not e.texto.strip():
            errores.append(f"{nombre}: está vacío.")
        if e.tipo in ("unica", "multiple"):
            if len([o for o in e.opciones if o.strip()]) < 2:
                errores.append(f"{nombre}: necesita al menos 2 opciones.")
            if len(e.opciones) > 26:
                errores.append(f"{nombre}: como máximo 26 opciones.")
            if any(not (0 <= k < len(e.opciones)) for k in e.con_texto + e.favorables):
                errores.append(f"{nombre}: hay referencias a opciones que no existen.")
        if e.tipo == "escala":
            if len(e.valores) < 2:
                errores.append(f"{nombre}: la escala necesita al menos 2 valores.")
            if len(e.valores) + len(e.extras) > 14:
                errores.append(f"{nombre}: como máximo 14 columnas (valores + extras).")
            if not e.filas:
                errores.append(f"{nombre}: la tabla necesita al menos una fila.")
        if e.tipo == "numero" and not (1 <= e.cifras <= 6):
            errores.append(f"{nombre}: el número de cifras debe estar entre 1 y 6.")
        if e.tipo == "abierta" and not (1 <= e.lineas <= 20):
            errores.append(f"{nombre}: el número de líneas debe estar entre 1 y 20.")
    return errores


def nuevo_elemento(tipo: str) -> Elemento:
    """Elemento con valores de partida razonables para el editor."""
    if tipo == "unica":
        return Elemento(tipo, texto="Nueva pregunta", opciones=["Sí", "No"])
    if tipo == "multiple":
        return Elemento(tipo, texto="Nueva pregunta (puede marcar varias opciones)",
                        opciones=["Opción 1", "Opción 2", "Opción 3"])
    if tipo == "escala":
        return Elemento(tipo, texto="Valore de 0 a 10 los siguientes servicios:",
                        valores=ESCALAS_PREDEFINIDAS["0 a 10"], filas=["Servicio 1", "Servicio 2"])
    if tipo == "numero":
        return Elemento(tipo, texto="Edad", cifras=2)
    if tipo == "abierta":
        return Elemento(tipo, texto="Sugerencias y mejoras", lineas=4)
    if tipo == "seccion":
        return Elemento(tipo, texto="Nueva sección")
    return Elemento(tipo, texto="Texto")
