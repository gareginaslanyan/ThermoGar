@echo off
rem 21-Z, step 3: the same app of 76aeb42 (git archive in %TEMP%\tg21z_base), own state root.
setlocal
set THERMOGAR_STATE_ROOT=%TEMP%\tg21z_base_state
set PYTHONHASHSEED=0
set PYTHONUTF8=1
cd /d "%TEMP%\tg21z_base"
"D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe" -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8637 --server.address 127.0.0.1 --client.toolbarMode auto
