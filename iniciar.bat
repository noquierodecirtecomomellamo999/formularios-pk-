@echo off
chcp 65001 >nul
title Encuestas OMR
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call instalar.bat
if not exist ".venv\Scripts\python.exe" exit /b 1

rem Evita la pregunta de bienvenida de Streamlit (correo electrónico) la primera vez
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    mkdir "%USERPROFILE%\.streamlit" 2>nul
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo.
echo  Abriendo Encuestas OMR en el navegador...
echo  Mientras uses el programa, deja esta ventana abierta. Para cerrarlo, cierra esta ventana.
echo.
".venv\Scripts\python.exe" -m streamlit run app\inicio.py --server.headless false --browser.gatherUsageStats false
pause
