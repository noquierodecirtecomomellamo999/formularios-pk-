@echo off
chcp 65001 >nul
title Instalar Encuestas OMR
cd /d "%~dp0"
echo.
echo  === Instalación de Encuestas OMR ===
echo.

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto comprobar_version
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY goto sin_python

:comprobar_version
rem (también descarta el acceso directo "python" de la Microsoft Store, que no es un Python real)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto python_viejo

if exist ".venv\Scripts\python.exe" goto instalar_paquetes
echo  Creando el entorno del programa...
%PY% -m venv .venv
if errorlevel 1 goto error

:instalar_paquetes
echo  Instalando los componentes. La primera vez tarda unos minutos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error

echo.
echo  Instalación terminada.
echo  Para abrir el programa, haz doble clic en "iniciar.bat".
echo.
pause
exit /b 0

:sin_python
echo  No se ha encontrado Python en este ordenador.
echo  1. Descárgalo de https://www.python.org/downloads/
echo  2. Al instalarlo, marca la casilla "Add python.exe to PATH".
echo  3. Vuelve a hacer doble clic en este archivo.
echo.
pause
exit /b 1

:python_viejo
echo  No se encuentra un Python 3.10 o posterior que funcione en este ordenador.
echo  1. Descarga la última versión de https://www.python.org/downloads/
echo  2. Al instalarlo, marca la casilla "Add python.exe to PATH".
echo  3. Vuelve a hacer doble clic en este archivo.
echo.
pause
exit /b 1

:error
echo.
echo  Ha habido un error durante la instalación. Revisa que haya conexión a internet
echo  y vuelve a intentarlo. Si se repite, copia los mensajes de arriba para pedir ayuda.
echo.
pause
exit /b 1
