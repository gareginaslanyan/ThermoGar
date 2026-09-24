@echo off
rem 21-D (copy of 21-B): app for frames 04, 15, 16, 17, 36. Own port, own state root, full toolbar menu by CLI key only.
setlocal
set THERMOGAR_STATE_ROOT=%TEMP%\tg21d_state
set PYTHONHASHSEED=0
set PYTHONUTF8=1
cd /d "%~dp0..\..\.."
"D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe" -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8641 --server.address 127.0.0.1 --client.toolbarMode auto
