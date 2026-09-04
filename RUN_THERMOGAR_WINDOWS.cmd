@echo off
setlocal
cd /d "%~dp0"
set "THERMOGAR_PYTHON=%~dp0.venv-windows\Scripts\python.exe"
rem Закреплённая хеш-затравка: pycalphad обходит множества строк, и от
rem затравки зависит порядок суммирования. Без неё числа расходятся в
rem последних битах между запусками и между воркерами пула.
set "PYTHONHASHSEED=0"
if not exist "%THERMOGAR_PYTHON%" (
    echo ThermoGar: Python environment not found.
    echo Expected: %THERMOGAR_PYTHON%
    exit /b 1
)
"%THERMOGAR_PYTHON%" -m streamlit run "%~dp0app\ThermoGar_app.py"
endlocal
