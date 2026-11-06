@echo off
cd /d "%~dp0"
python videoease.py
if errorlevel 1 pause
