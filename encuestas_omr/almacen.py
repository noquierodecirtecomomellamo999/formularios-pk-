"""Almacenamiento en disco de encuestas, versiones impresas, escaneos y revisiones.

Todo se guarda en archivos dentro de la carpeta de datos (por defecto ``datos/``
junto al programa), para que se pueda copiar o hacer copia de seguridad sin más:

    datos/encuestas/<id>/
        encuesta.json              definición de la encuesta
        recursos/                  logos
        maquetas/<huella>.json     cada versión impresa (para leer sus hojas siempre bien)
        impresiones.json           registro de PDF generados y números de cuestionario usados
        lotes/<lote>/              cada tanda de escaneos subida
            originales/            archivos tal cual se subieron
            paginas/0001.jpg ...   páginas enderezadas
            lote.json              datos del lote
            lectura.json           resultado de la lectura de cada página
        revisiones.json            correcciones manuales y transcripciones
        informe.json               textos editados del informe
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .lector import ResultadoPagina
from .maquetacion import Maqueta, maquetar
from .modelo import Encuesta, asignar_ids, slug

RAIZ_PROGRAMA = Path(__file__).resolve().parent.parent
CARPETA_EJEMPLOS = RAIZ_PROGRAMA / "ejemplos"


def carpeta_datos_por_defecto() -> Path:
    return Path(os.environ.get("ENCUESTAS_OMR_DATOS", RAIZ_PROGRAMA / "datos"))


def _leer_json(ruta: Path, por_defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return por_defecto


def _escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporal, ruta)  # escritura atómica: no deja archivos a medias


class Almacen:
    def __init__(self, raiz: Path | None = None):
        self.raiz = Path(raiz) if raiz else carpeta_datos_por_defecto()
        self.dir_encuestas = self.raiz / "encuestas"
        self.dir_encuestas.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ encuestas
    def ruta(self, id_: str) -> Path:
        return self.dir_encuestas / id_

    def recursos(self, id_: str) -> Path:
        r = self.ruta(id_) / "recursos"
        r.mkdir(parents=True, exist_ok=True)
        return r

    def ids(self) -> list[str]:
        return sorted(p.name for p in self.dir_encuestas.iterdir() if (p / "encuesta.json").exists())

    def listar(self) -> list[dict]:
        res = []
        for id_ in self.ids():
            d = _leer_json(self.ruta(id_) / "encuesta.json", {})
            res.append({"id": id_, "titulo": d.get("titulo", id_), "subtitulo": d.get("subtitulo", "")})
        return res

    def existe(self, id_: str) -> bool:
        return (self.ruta(id_) / "encuesta.json").exists()

    def cargar(self, id_: str) -> Encuesta:
        return Encuesta.cargar(self.ruta(id_) / "encuesta.json")

    def guardar(self, enc: Encuesta) -> None:
        asignar_ids(enc)
        enc.guardar(self.ruta(enc.id) / "encuesta.json")

    def id_libre(self, base: str) -> str:
        base = slug(base)
        candidato, n = base, 2
        while self.ruta(candidato).exists():
            candidato, n = f"{base}-{n}", n + 1
        return candidato

    def crear(self, titulo: str, subtitulo: str = "") -> Encuesta:
        enc = Encuesta(id=self.id_libre(f"{titulo} {subtitulo}"), titulo=titulo, subtitulo=subtitulo)
        self.guardar(enc)
        return enc

    def duplicar(self, id_: str, titulo: str | None = None, subtitulo: str | None = None) -> Encuesta:
        """Copia la definición y los logos (no los escaneos ni resultados)."""
        enc = self.cargar(id_)
        if titulo is not None:
            enc.titulo = titulo
        if subtitulo is not None:
            enc.subtitulo = subtitulo
        enc.id = self.id_libre(f"{enc.titulo} {enc.subtitulo}")
        self.guardar(enc)
        origen = self.ruta(id_) / "recursos"
        if origen.exists():
            shutil.copytree(origen, self.recursos(enc.id), dirs_exist_ok=True)
        return enc

    def borrar(self, id_: str) -> Path:
        """Mueve la encuesta (con todos sus datos) a la papelera, no la elimina."""
        destino = self.raiz / "papelera" / f"{id_}_{datetime.now():%Y%m%d-%H%M%S}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.ruta(id_)), destino)
        return destino

    def importar(self, datos: dict, carpeta_logos: Path | None = None) -> Encuesta:
        enc = Encuesta.from_dict(datos)
        if self.existe(enc.id):
            enc.id = self.id_libre(enc.id)
        self.guardar(enc)
        if carpeta_logos:
            for nombre in enc.cabecera.logos:
                if (carpeta_logos / nombre).exists():
                    shutil.copy2(carpeta_logos / nombre, self.recursos(enc.id) / nombre)
        return enc

    def instalar_ejemplos(self, solo_si_vacio: bool = True) -> list[str]:
        if solo_si_vacio and self.ids():
            return []
        nuevos = []
        for ruta in sorted(CARPETA_EJEMPLOS.glob("*.json")):
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if self.existe(datos["id"]):
                continue
            nuevos.append(self.importar(datos, CARPETA_EJEMPLOS / "logos").id)
        return nuevos

    def guardar_logo(self, id_: str, nombre: str, contenido: bytes) -> str:
        nombre = slug(Path(nombre).stem) + Path(nombre).suffix.lower()
        (self.recursos(id_) / nombre).write_bytes(contenido)
        return nombre

    # ------------------------------------------------------------------ maquetas (versiones impresas)
    def maqueta_actual(self, id_: str) -> Maqueta:
        """Maqueta de la versión actual; se guarda para poder leer siempre sus hojas."""
        m = maquetar(self.cargar(id_), self.recursos(id_))
        ruta = self.ruta(id_) / "maquetas" / f"{m.huella}.json"
        if not ruta.exists():
            m.guardar(ruta)
        return m

    def maqueta(self, id_: str, huella: str) -> Maqueta | None:
        ruta = self.ruta(id_) / "maquetas" / f"{huella}.json"
        return Maqueta.cargar(ruta) if ruta.exists() else None

    def huellas(self, id_: str) -> list[str]:
        carpeta = self.ruta(id_) / "maquetas"
        if not carpeta.exists():
            return []
        return [p.stem for p in sorted(carpeta.glob("*.json"), key=lambda p: p.stat().st_mtime)]

    def buscar_maqueta(self, huella: str) -> tuple[str, Maqueta] | None:
        """Busca una versión impresa en todas las encuestas."""
        for id_ in self.ids():
            m = self.maqueta(id_, huella)
            if m is not None:
                return id_, m
        return None

    # ------------------------------------------------------------------ impresiones
    def impresiones(self, id_: str) -> list[dict]:
        return _leer_json(self.ruta(id_) / "impresiones.json", [])

    def siguiente_hoja(self, id_: str) -> int:
        usadas = [i["hasta"] for i in self.impresiones(id_) if i.get("hasta")]
        return max(usadas, default=0) + 1

    def registrar_impresion(self, id_: str, huella: str, desde: int, hasta: int, archivo: str) -> None:
        lista = self.impresiones(id_)
        lista.append({"fecha": datetime.now().isoformat(timespec="seconds"), "huella": huella,
                      "desde": desde, "hasta": hasta, "archivo": archivo})
        _escribir_json(self.ruta(id_) / "impresiones.json", lista)

    # ------------------------------------------------------------------ lotes de escaneos
    def dir_lotes(self, id_: str) -> Path:
        return self.ruta(id_) / "lotes"

    def ruta_lote(self, id_: str, lote: str) -> Path:
        return self.dir_lotes(id_) / lote

    def lotes(self, id_: str) -> list[dict]:
        carpeta = self.dir_lotes(id_)
        if not carpeta.exists():
            return []
        res = []
        for p in sorted(carpeta.iterdir()):
            meta = _leer_json(p / "lote.json", None)
            if meta:
                res.append(meta)
        return res

    def crear_lote(self, id_: str, archivos: list[tuple[str, bytes]]) -> str:
        existentes = [m["id"] for m in self.lotes(id_)]
        n = 1 + max((int(x[1:]) for x in existentes if x[1:].isdigit()), default=0)
        lote = f"L{n:03d}"
        base = self.ruta_lote(id_, lote)
        (base / "originales").mkdir(parents=True, exist_ok=True)
        nombres = []
        for nombre, contenido in archivos:
            nombre_seguro = Path(nombre).name
            (base / "originales" / nombre_seguro).write_bytes(contenido)
            nombres.append(nombre_seguro)
        _escribir_json(base / "lote.json", {"id": lote, "fecha": datetime.now().isoformat(timespec="seconds"),
                                            "archivos": nombres, "paginas": 0, "errores": 0, "procesado": False})
        return lote

    def guardar_lectura(self, id_: str, lote: str, paginas: list[ResultadoPagina]) -> None:
        base = self.ruta_lote(id_, lote)
        _escribir_json(base / "lectura.json", [p.to_dict() for p in paginas])
        meta = _leer_json(base / "lote.json", {})
        meta.update(paginas=len(paginas), errores=sum(1 for p in paginas if p.error), procesado=True)
        _escribir_json(base / "lote.json", meta)

    def lectura(self, id_: str, lote: str) -> list[ResultadoPagina]:
        return [ResultadoPagina.from_dict(d) for d in _leer_json(self.ruta_lote(id_, lote) / "lectura.json", [])]

    def borrar_lote(self, id_: str, lote: str) -> None:
        shutil.rmtree(self.ruta_lote(id_, lote), ignore_errors=True)

    # ------------------------------------------------------------------ revisiones e informe
    def revisiones(self, id_: str) -> dict:
        r = _leer_json(self.ruta(id_) / "revisiones.json", {})
        r.setdefault("campos", {})
        r.setdefault("textos", {})
        r.setdefault("descartados", [])
        return r

    def guardar_revisiones(self, id_: str, revisiones: dict) -> None:
        _escribir_json(self.ruta(id_) / "revisiones.json", revisiones)

    def textos_informe(self, id_: str) -> dict:
        return _leer_json(self.ruta(id_) / "informe.json", {})

    def guardar_textos_informe(self, id_: str, textos: dict) -> None:
        _escribir_json(self.ruta(id_) / "informe.json", textos)
