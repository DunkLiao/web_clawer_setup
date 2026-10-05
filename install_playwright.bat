@echo off
chcp 65001 > nul
title Playwright Environment Setup

echo =====================================
echo Creating Python virtual environment
echo =====================================

if not exist .venv (
    python -m venv .venv
)

echo.
echo =====================================
echo Activating virtual environment
echo =====================================

call .venv\Scripts\activate.bat

echo.
echo =====================================
echo Upgrading pip
echo =====================================

python -m pip install --upgrade pip

echo.
echo =====================================
echo Installing packages
echo =====================================

pip install ^
playwright ^
pandas ^
openpyxl ^
beautifulsoup4 ^
lxml ^
requests ^
PyYAML

echo.
echo =====================================
echo Installing Chromium
echo =====================================

python -m playwright install chromium

echo.
echo =====================================
echo Done.
echo Virtual environment: %CD%\.venv
echo =====================================

pause
