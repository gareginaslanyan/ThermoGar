@echo off
rem 21-M: port 8640, state tg21m_state, no bytecode in app (thermogar_paths_test::test_005). 21-I (copy of 21-Z, 21-E, 21-B): app for design audit. Own port, own state root, full toolbar menu by CLI key only.
setlocal
set THERMOGAR_STATE_ROOT=%TEMP%\tg21m_state
set PYTHONHASHSEED=0
set PYTHONUTF8=1
set MPLBACKEND=Agg
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0..\..\.."
"D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe" -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8640 --server.address 127.0.0.1 --client.toolbarMode auto
