@echo off
setlocal
set "PROJECT=%~1"
if "%PROJECT%"=="" set "PROJECT=%USERPROFILE%\Desktop\ThermoGar"
set "PYTHON=%PROJECT%\.venv-windows\Scripts\python.exe"
"%PYTHON%" "%PROJECT%\tools\thermogar_properties_test.py" --project-root "%PROJECT%" || exit /b 1
"%PYTHON%" "%PROJECT%\tools\thermogar_self_test.py" --project-root "%PROJECT%" || exit /b 1
endlocal
