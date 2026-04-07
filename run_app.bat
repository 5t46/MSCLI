@echo off
TITLE "Movie Downloader & Subtitles"
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [INFO] Please run "install.bat" first to prepare the app.
    pause
    exit /b
)

echo [SYSTEM] Launching Movie Downloader ^& Subtitles (Dark Premium)...
venv\Scripts\python.exe main.py
pause
