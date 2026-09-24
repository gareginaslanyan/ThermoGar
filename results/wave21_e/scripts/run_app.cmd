@echo off
rem 21-E (copy of 21-B): app for design audit. Own port, own state root, full toolbar menu by CLI key only.
setlocal
set THERMOGAR_STATE_ROOT=%TEMP%\tg21e_state
set PYTHONHASHSEED=0
set PYTHONUTF8=1
cd /d "%~dp0..\..\.."
"D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe" -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8635 --server.address 127.0.0.1 --client.toolbarMode auto
