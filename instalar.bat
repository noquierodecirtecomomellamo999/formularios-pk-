@echo off
chcp 65001 >nul
title Instalar Encuestas CIRENC
cd /d "%~dp0"
rem El entorno de Python se crea en una carpeta de ruta corta, no dentro de esta carpeta: así no se
rem choca con el límite de 260 caracteres de Windows aunque el programa esté en una ruta muy larga.
set "ENTORNO=%LOCALAPPDATA%\Encuestas CIRENC\entorno"
echo.
echo  === Instalación de Encuestas CIRENC ===
echo.

rem Buscar un Python 3.10 o posterior: primero el lanzador «py» y después «python»
rem (la prueba también descarta el acceso directo «python» de la Microsoft Store, que no es un Python real)
set "PY=py -3"
call :probar_python
if not errorlevel 1 goto python_ok
set "PY=python"
call :probar_python
if not errorlevel 1 goto python_ok
goto sin_python

:python_ok
rem Se reutiliza el entorno si ya existe y funciona (si se desinstaló su Python, se rehace)
if not exist "%ENTORNO%\Scripts\python.exe" goto crear_entorno
"%ENTORNO%\Scripts\python.exe" -c "pass" >nul 2>nul
if not errorlevel 1 goto instalar_paquetes
:crear_entorno
echo  Creando el entorno del programa...
%PY% -m venv --clear "%ENTORNO%"
if errorlevel 1 goto error

:instalar_paquetes
if exist "%ENTORNO%\listo.txt" del "%ENTORNO%\listo.txt"
echo  Instalando los componentes. La primera vez tarda unos minutos...
"%ENTORNO%\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip >nul
"%ENTORNO%\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error
rem Marca de instalación terminada: copia de las librerías instaladas (si cambian, iniciar.bat reinstala)
copy /y requirements.txt "%ENTORNO%\listo.txt" >nul

echo.
echo  Instalación terminada.
echo  Para abrir el programa, haz doble clic en "iniciar.bat".
echo.
pause
exit /b 0

:probar_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
exit /b %errorlevel%

:sin_python
echo  No se encuentra Python 3.10 o posterior en este ordenador.
echo  1. Descarga la última versión de https://www.python.org/downloads/
echo  2. Al instalarlo, marca la casilla "Add python.exe to PATH".
echo  3. Vuelve a hacer doble clic en este archivo.
echo.
echo  Más fácil: usa el instalador, que ya lo lleva todo dentro (Python incluido):
echo  https://github.com/noquierodecirtecomomellamo999/formularios-pk-/releases/latest/download/Instalar-Encuestas-CIRENC.exe
echo.
pause
exit /b 1

:error
echo.
echo  Ha habido un error durante la instalación.
echo  - Comprueba que hay conexión a internet y vuelve a intentarlo.
echo  - Lo más sencillo es usar el instalador, que ya lo lleva todo dentro:
echo    https://github.com/noquierodecirtecomomellamo999/formularios-pk-/releases/latest/download/Instalar-Encuestas-CIRENC.exe
echo  Si se repite, copia los mensajes de arriba para pedir ayuda.
echo.
pause
exit /b 1
