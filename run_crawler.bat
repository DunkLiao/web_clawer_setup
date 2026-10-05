@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] .venv not found. Please run install_playwright.bat first.
    exit /b 1
)

call ".venv\Scripts\activate.bat"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=example"

echo =====================================
echo Running crawler: %TARGET%
echo =====================================

python -m crawler --target %TARGET% %2 %3 %4 %5 %6
set EXITCODE=%ERRORLEVEL%

echo.
echo =====================================
echo Finished. exit code = %EXITCODE%
echo =====================================
exit /b %EXITCODE%
