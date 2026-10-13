"""Abre Encuestas CIRENC: arranca el programa (si no estaba ya abierto) y lo muestra en el navegador.

Es lo que ejecuta el icono del escritorio. Se puede lanzar con ``pythonw.exe`` (sin
ventana negra): los mensajes internos se guardan en un archivo de registro.

Opciones:
    --sin-navegador   no abre el navegador (para pruebas automáticas)
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
APP = RAIZ / "app" / "inicio.py"
PUERTOS = range(8501, 8521)


def _preparar_registro() -> None:
    """Con pythonw no hay consola: se redirige la salida a un archivo para poder diagnosticar problemas."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Encuestas CIRENC"
    base.mkdir(parents=True, exist_ok=True)
    registro = base / "registro.txt"
    if registro.exists() and registro.stat().st_size > 2_000_000:
        registro.replace(base / "registro_anterior.txt")
    salida = open(registro, "a", encoding="utf-8", buffering=1)
    salida.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    sys.stdout = sys.stderr = salida


def _responde(puerto: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/_stcore/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def _ocupado(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def _abrir_navegador_cuando_este_listo(puerto: int) -> None:
    for _ in range(240):
        if _responde(puerto):
            webbrowser.open(f"http://127.0.0.1:{puerto}")
            return
        time.sleep(0.5)


def main() -> int:
    abrir = "--sin-navegador" not in sys.argv
    _preparar_registro()
    # Si ya está abierto, solo se muestra en el navegador
    for puerto in PUERTOS:
        if _ocupado(puerto) and _responde(puerto):
            if abrir:
                webbrowser.open(f"http://127.0.0.1:{puerto}")
            return 0
    puerto = next(p for p in PUERTOS if not _ocupado(p))
    if abrir:
        threading.Thread(target=_abrir_navegador_cuando_este_listo, args=(puerto,), daemon=True).start()
    os.chdir(RAIZ)
    sys.argv = [
        "streamlit", "run", str(APP),
        "--server.port", str(puerto),
        "--server.address", "127.0.0.1",  # solo este ordenador: sin avisos del cortafuegos
        "--server.headless", "true",
        "--server.fileWatcherType", "none",
        "--server.runOnSave", "false",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    from streamlit.web import cli

    return cli.main()


if __name__ == "__main__":
    sys.exit(main())
