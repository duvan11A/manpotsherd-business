@echo off
chcp 65001 >nul
cd /d "%~dp0"
python app\main.py 2> error_log.txt
if %errorlevel% neq 0 (
    echo.
    echo ================= OCURRIO UN ERROR =================
    type error_log.txt
    echo ===================================================
    echo.
    echo El error tambien quedo guardado en error_log.txt
    echo Mandame ese archivo o esta pantalla.
    pause
)
