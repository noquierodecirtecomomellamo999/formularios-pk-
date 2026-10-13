"""Construye la versión de Windows lista para usar (con Python incluido).

Se ejecuta en Windows (lo hace GitHub Actions automáticamente, ver
.github/workflows/instalador.yml):

    python instalador/construir.py

Resultado en ``dist/``:
    Encuestas CIRENC/                  carpeta con el programa, Python y todas las librerías
    Encuestas-CIRENC-portable.zip      la misma carpeta comprimida (no necesita instalación)

Después, Inno Setup convierte la carpeta en ``Instalar-Encuestas-CIRENC.exe``
(ver instalador/encuestas_cirenc.iss).
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ / "dist"
NOMBRE = "Encuestas CIRENC"
DESTINO = DIST / NOMBRE
CARPETAS = ["app", "encuestas_omr", "third_party", "ejemplos", "recursos", ".streamlit"]
ARCHIVOS = ["lanzador.py", "README.md", "requirements.txt"]
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".pytest_cache")


def version() -> str:
    from encuestas_omr import __version__  # noqa: E402

    return __version__


def descargar_python(destino: Path) -> str:
    """Descarga el «Python embebido» oficial de la misma versión menor que el Python que construye.

    (Las últimas versiones de mantenimiento solo publican código fuente, así que se busca la
    versión de parche más reciente que tenga paquete embebido.)
    """
    v = sys.version_info
    for parche in range(v.micro, -1, -1):
        numero = f"{v.major}.{v.minor}.{parche}"
        url = f"https://www.python.org/ftp/python/{numero}/python-{numero}-embed-amd64.zip"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                datos = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            z.extractall(destino)
        print(f"Python embebido {numero} descargado")
        # Activar site-packages y la carpeta del programa
        pth = destino / f"python{v.major}{v.minor}._pth"
        pth.write_text(f"python{v.major}{v.minor}.zip\n.\nLib\\site-packages\n..\nimport site\n", encoding="utf-8")
        return numero
    raise SystemExit(f"No se encuentra Python embebido para {v.major}.{v.minor}")


def instalar_librerias(destino: Path) -> None:
    site = destino / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                           "--no-warn-script-location", "--target", str(site), "-r", str(RAIZ / "requirements.txt")])
    # Ejecutables de consola que no hacen falta (el programa se abre con el lanzador)
    shutil.rmtree(site / "bin", ignore_errors=True)


def copiar_programa(destino: Path) -> None:
    for carpeta in CARPETAS:
        shutil.copytree(RAIZ / carpeta, destino / carpeta, ignore=IGNORAR, dirs_exist_ok=True)
    for archivo in ARCHIVOS:
        shutil.copy2(RAIZ / archivo, destino / archivo)
    # Abridor para la versión portable (la instalada usa los iconos del escritorio y del menú Inicio)
    (destino / f"Abrir {NOMBRE}.bat").write_bytes(
        ('@echo off\r\ncd /d "%~dp0"\r\nstart "" "python\\pythonw.exe" lanzador.py\r\n').encode("utf-8"))
    (destino / "version.txt").write_text(version() + "\n", encoding="utf-8")


def generar_guia(destino: Path) -> None:
    """La guía se genera con el Python ya empaquetado (que tiene ReportLab)."""
    python = destino / "python" / "python.exe"
    if not python.exists():  # construcción de prueba fuera de Windows
        python = Path(sys.executable)
    subprocess.check_call([str(python), str(RAIZ / "instalador" / "guia_rapida.py"),
                           str(destino / "Guía rápida.pdf")])


def comprimir(destino: Path) -> Path:
    zip_path = DIST / "Encuestas-CIRENC-portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=DIST, base_dir=NOMBRE)
    return zip_path


def main() -> None:
    sin_python = "--sin-python" in sys.argv  # solo para probar la copia fuera de Windows
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)
    if not sin_python:
        if sys.platform != "win32":
            raise SystemExit("La versión con Python incluido se construye en Windows (o usa --sin-python).")
        descargar_python(DESTINO / "python")
        instalar_librerias(DESTINO / "python")
    copiar_programa(DESTINO)
    generar_guia(DESTINO)
    # Copia de la guía con nombre sin tildes (GitHub las quita de los nombres de las descargas)
    shutil.copy2(DESTINO / "Guía rápida.pdf", DIST / "Guia-rapida-Encuestas-CIRENC.pdf")
    zip_path = comprimir(DESTINO)
    tam = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file()) / 1e6
    print(f"Listo: {DESTINO} ({tam:.0f} MB) y {zip_path.name} ({zip_path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    main()
