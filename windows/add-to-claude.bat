@echo off
title lefant-m2-local add to Claude Desktop
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
%PY% add_to_claude.py
pause
