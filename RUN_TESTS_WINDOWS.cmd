@echo off
setlocal
set "PROJECT=%~1"
if "%PROJECT%"=="" set "PROJECT=%USERPROFILE%\Desktop\ThermoGar"
set "PYTHON=%PROJECT%\.venv-windows\Scripts\python.exe"
rem Та же затравка, что и у приложения: тесты сравнивают числа
rem параллельного и последовательного режимов побайтово.
set "PYTHONHASHSEED=0"
"%PYTHON%" "%PROJECT%\tools\thermogar_properties_test.py" --project-root "%PROJECT%" || exit /b 1
"%PYTHON%" "%PROJECT%\tools\thermogar_self_test.py" --project-root "%PROJECT%" || exit /b 1
endlocal
