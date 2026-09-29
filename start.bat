@echo off
setlocal enabledelayedexpansion
rem ====================================================================
rem  Personal Notes - one-click start script
rem  Flow: env check -> dependency check -> port probe -> launch ->
rem        health polling -> open browser
rem  This script never kills processes and never frees ports.
rem ====================================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

set "PY=python"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"

rem Candidate ports: project default first, then alternatives for
rem machines where port 5000 is reserved or occupied by another service.
set "CANDIDATES=5000 5057 5067 5087"
set "FIRST=5000"

echo [1/5] Checking Python ...
where python >nul 2>nul
if errorlevel 1 goto :fail_python

rem Use the project virtualenv when it exists so that plain "python"
rem resolves to the interpreter that has the dependencies installed.
if exist "%ROOT%\.venv\Scripts\python.exe" set "PATH=%ROOT%\.venv\Scripts;%PATH%"

echo [2/5] Checking dependencies ...
"%PY%" -c "import flask, flask_sqlalchemy, flask_login, requests" >nul 2>nul
if errorlevel 1 goto :fail_deps

echo [3/5] Probing ports ...
rem 3a) reuse a service that is already answering
for %%P in (%CANDIDATES%) do (
  call :is_healthy %%P
  if not errorlevel 1 (
    set "PORT=%%P"
    goto :already_running
  )
)

rem 3b) pick the first free port
for %%P in (%CANDIDATES%) do (
  netstat -ano | findstr /C:"LISTENING" | findstr /C:":%%P " >nul 2>nul
  if errorlevel 1 (
    set "PORT=%%P"
    goto :launch
  )
)
goto :fail_ports

:launch
echo [4/5] Starting the service on port %PORT% ...
ver >nul
start "Personal Notes - Flask log" /D "%ROOT%" "%ComSpec%" /k "set APP_PORT=%PORT% && %PY% app.py"
if errorlevel 1 goto :fail_launch

echo [5/5] Waiting for http://127.0.0.1:%PORT%/api/health ...
for /l %%I in (1,1,60) do (
  call :is_healthy %PORT%
  if not errorlevel 1 goto :ready
  timeout /t 2 /nobreak >nul
)
goto :fail_not_ready

:ready
echo.
echo Service is ready: http://127.0.0.1:%PORT%/
echo A log window named "Personal Notes - Flask log" is now open.
echo Close that window to stop the service.
ver >nul
start "" "http://127.0.0.1:%PORT%/"
echo.
echo Press any key to close this window.
pause >nul
exit /b 0

:already_running
echo A service is already answering on port %PORT%, no new instance was started.
ver >nul
start "" "http://127.0.0.1:%PORT%/"
echo Opened http://127.0.0.1:%PORT%/ in your browser.
echo Press any key to close this window.
pause >nul
exit /b 0

rem ---------------------------------------------------------------
rem  Health probe for one port. Exit code 0 means the app answers.
rem ---------------------------------------------------------------
:is_healthy
"%PY%" -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:%~1/api/health', timeout=2); sys.exit(0 if b'OK' in r.read() else 1)" >nul 2>nul
exit /b %errorlevel%

rem ---------------------------------------------------------------
rem  Failure paths
rem ---------------------------------------------------------------
:fail_python
echo Python was not found on PATH. Install Python 3.12 first, then run this script again.
goto :fail

:fail_deps
echo Dependencies are missing for the interpreter "%PY%".
echo Install them with:
echo   python -m pip install -r requirements.txt -i %PIP_MIRROR%
goto :fail

:fail_ports
echo All candidate ports are in use and none answers /api/health.
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /C:"LISTENING" ^| findstr /C:":%FIRST% "') do echo   port %FIRST% is held by PID %%A
echo.
echo Check any port:  netstat -ano ^| findstr LISTENING
echo Stop a process:  taskkill /PID ^<pid^> /F
echo Or pick a free port:  set APP_PORT=5099 ^&^& start.bat
goto :fail

:fail_launch
echo Could not launch the service process.
goto :fail

:fail_not_ready
echo The service did not become ready within 120 seconds.
echo Check the log window "Personal Notes - Flask log" for details.
echo Port %PORT%, health endpoint http://127.0.0.1:%PORT%/api/health
goto :fail

:fail
echo.
echo Startup failed. Read the message above, then press any key to close.
pause >nul
exit /b 1
