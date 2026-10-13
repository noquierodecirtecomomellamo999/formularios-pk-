@echo off
chcp 65001 >nul
title Encuestas CIRENC
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call instalar.bat
if not exist ".venv\Scripts\python.exe" exit /b 1

echo.
echo  Abriendo Encuestas CIRENC en el navegador...
echo  Mientras uses el programa, deja esta ventana abierta. Para cerrarlo, usa el botón
echo  «Cerrar el programa» del menú de la izquierda o cierra esta ventana.
echo.
".venv\Scripts\python.exe" lanzador.py
