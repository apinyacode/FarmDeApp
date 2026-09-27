@echo off
REM One-command setup + start for the Angel Arms Foundation website (Windows).
REM
REM   start.bat          development: auto-reloads when you edit files (http://127.0.0.1:5000)
REM   start.bat prod     production: runs with waitress, reachable from other machines
REM
REM First run creates .venv, installs packages, and writes instance\.env with a
REM random SECRET_KEY and ADMIN_PASSWORD. Later runs reuse all of that.

setlocal
cd /d "%~dp0"
set MODE=%1
if "%MODE%"=="" set MODE=dev
if "%PORT%"=="" set PORT=5000

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>nul
if errorlevel 1 (
  echo Python 3.9 or newer is required. Get it from https://www.python.org/downloads/
  echo During install, tick "Add python.exe to PATH".
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo ==^> Creating virtual environment (.venv^)
  %PY% -m venv .venv || exit /b 1
)
set VPY=.venv\Scripts\python.exe

if not exist .venv\.installed (
  echo ==^> Installing packages
  %VPY% -m pip install --quiet --upgrade pip
  %VPY% -m pip install --quiet -r requirements.txt || exit /b 1
  type nul > .venv\.installed
)

if not exist instance mkdir instance
if not exist instance\.env (
  echo ==^> Creating instance\.env with a secret key and admin password
  %VPY% -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32)); print('ADMIN_PASSWORD=' + secrets.token_urlsafe(12))" > instance\.env
)

echo ==^> Running tests
%VPY% -m pytest -q || exit /b 1

echo.
echo   Admin page: /admin/volunteers  (any username; password is in instance\.env)
echo.

if /i "%MODE%"=="dev" (
  echo ==^> Starting in DEVELOPMENT mode on http://127.0.0.1:%PORT%  (Ctrl+C to stop^)
  %VPY% -m flask --app app run --debug --port %PORT%
) else if /i "%MODE%"=="prod" (
  echo ==^> Starting in PRODUCTION mode on port %PORT%  (Ctrl+C to stop^)
  .venv\Scripts\waitress-serve.exe --listen=0.0.0.0:%PORT% app:app
) else (
  echo Unknown mode "%MODE%". Use: start.bat  or  start.bat prod
  exit /b 1
)
