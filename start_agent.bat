@echo off
title FBR IRIS 2.0 Auto-Posting Suite
cd /d %~dp0
echo =======================================================
echo [*] Launching FBR IRIS Auto-Posting Dashboard...
echo [*] Interactive Desktop Mode: Chrome GUI Enabled
echo =======================================================
.\venv\Scripts\python.exe run.py
pause
