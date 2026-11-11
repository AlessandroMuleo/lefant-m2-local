@echo off
title lefant-m2-local get key
cd /d "%~dp0.."
set PY=
py -3 --version >nul 2>nul && set PY=py -3
if not defined PY (
  python --version >nul 2>nul && set PY=python
)
if not defined PY (
  echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
%PY% -m pip install -q -r requirements.txt
%PY% get_key.py
echo.
%PY% discover.py
pause
