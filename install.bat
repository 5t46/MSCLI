@echo off
setlocal enabledelayedexpansion

echo =================================================================
echo        Movies Downloader ^& Subtitles - Auto Installer
echo =================================================================
echo.

@set "MSCLI_DIR=%USERPROFILE%\Downloads\MSCLI"

rem If requirements.txt exists in the current directory, we're already inside the repo
if exist "%~dp0requirements.txt" (
    echo [OK] MSCLI project detected in current directory.
    set "MSCLI_DIR=%~dp0"
    goto :SKIP_CLONE
)

rem Check if MSCLI exists in the Downloads folder
if exist "%MSCLI_DIR%\requirements.txt" (
    echo [OK] MSCLI already downloaded at "%MSCLI_DIR%".
    goto :SKIP_CLONE
)

rem MSCLI not found — clone it
echo [INFO] MSCLI not found. Downloading to "%MSCLI_DIR%" ...
echo.

rem Check for Git
git --version >nul 2>&1
if !errorlevel! equ 0 goto :SKIP_GIT_INSTALL

echo [INFO] Git is not installed. Installing Git automatically...
echo.

rem Download Git installer using PowerShell
set "GIT_INSTALLER=%TEMP%\Git-Installer.exe"
powershell -Command "Write-Host '[INFO] Downloading Git for Windows...' ; try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/Git-2.47.1.2-64-bit.exe' -OutFile '%GIT_INSTALLER%' -UseBasicParsing } catch { Write-Host '[ERROR] Download failed'; exit 1 }"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to download Git installer.
    echo Please install Git manually from https://git-scm.com/
    pause
    exit /b 1
)

echo [INFO] Running Git installer (this may take a minute)...
start /wait "" "%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
if !errorlevel! neq 0 (
    echo [ERROR] Git installation failed.
    pause
    exit /b 1
)

rem Clean up installer
del /f /q "%GIT_INSTALLER%" 2>nul

rem Refresh PATH so git is available in this session
set "PATH=%PATH%;C:\Program Files\Git\cmd"

git --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Git was installed but is not accessible. Please restart and try again.
    pause
    exit /b 1
)

echo [OK] Git installed successfully.
echo.

:SKIP_GIT_INSTALL

git clone https://github.com/5t46/MSCLI.git "%MSCLI_DIR%"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to clone MSCLI repository.
    pause
    exit /b 1
)

echo [OK] MSCLI downloaded successfully.

:SKIP_CLONE
rem Move into the MSCLI project directory
pushd "%MSCLI_DIR%"

rem Check for Python
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Python is not installed or not in your PATH. 
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if !errorlevel! neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate
if !errorlevel! neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [3/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [4/4] Setting up project structure...
if not exist "logs" mkdir "logs"
if not exist "config.json" (
    echo [INFO] config.json will be created when you first run the app.
)

echo.
echo.
echo =================================================================
echo [SUCCESS] Setup complete! 
echo.
echo To start the app, double-click the "run_app.bat" file!
echo =================================================================
echo.
pause
