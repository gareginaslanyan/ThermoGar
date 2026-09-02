@echo off
setlocal
cd /d "%~dp0"
set "THERMOGAR_PYTHON=%~dp0.venv-windows\Scripts\python.exe"
if not exist "%THERMOGAR_PYTHON%" (
    echo ThermoGar: Python environment not found.
    echo Expected: %THERMOGAR_PYTHON%
    exit /b 1
)
"%THERMOGAR_PYTHON%" -m streamlit run "%~dp0app\ThermoGar_app.py"
endlocal
