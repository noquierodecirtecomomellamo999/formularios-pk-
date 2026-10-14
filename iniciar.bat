@echo off
chcp 65001 >nul
title Encuestas CIRENC
cd /d "%~dp0"
set "ENTORNO=%LOCALAPPDATA%\Encuestas CIRENC\entorno"

rem Se instala la primera vez, o de nuevo si esta versión necesita otras librerías
fc /b requirements.txt "%ENTORNO%\listo.txt" >nul 2>nul
if errorlevel 1 call instalar.bat
if not exist "%ENTORNO%\listo.txt" exit /b 1

echo.
echo  Abriendo Encuestas CIRENC en el navegador...
echo  Mientras uses el programa, deja esta ventana abierta. Para cerrarlo, usa el botón
echo  «Cerrar el programa» del menú de la izquierda o cierra esta ventana.
echo.
"%ENTORNO%\Scripts\python.exe" lanzador.py
