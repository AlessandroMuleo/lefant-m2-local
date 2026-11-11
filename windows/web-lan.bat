@echo off
title lefant-m2-local web on the LAN (keep this window open)
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
echo If Windows asks about the firewall, allow Python on private networks.
%PY% web_app.py --lan --port 8766
pause
