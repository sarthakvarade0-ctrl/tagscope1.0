@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo TagScope could not start. Install Python 3.10 or newer from https://www.python.org/downloads/windows/
  echo During installation, enable the option to add Python to PATH.
  pause
)
endlocal
