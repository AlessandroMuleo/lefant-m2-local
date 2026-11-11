@echo off
title lefant-m2-local setup
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
%PY% -m pip install -r requirements.txt || (pause & exit /b 1)
echo.
echo The wizard asks for the Access ID and Access Secret of your Tuya project.
echo Region: eu (or yours). Device ID: any of yours. Download DP mappings: Y.
%PY% -m tinytuya wizard
pause
