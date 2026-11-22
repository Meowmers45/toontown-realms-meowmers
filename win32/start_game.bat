@echo off
title Toontown Realms - Game Client
cd ..

rem Prefer the configured interpreter; fall back to the per-user Panda3D installer.
set "PPYTHON_PATH="
if exist PPYTHON_PATH set /P PPYTHON_PATH=<PPYTHON_PATH
set "PPYTHON_PATH=%PPYTHON_PATH:"=%"
if defined PPYTHON_PATH (
    if exist "%PPYTHON_PATH%" goto startGame
    where /Q "%PPYTHON_PATH%"
    if not errorlevel 1 goto startGame
)
set "PPYTHON_PATH=%LOCALAPPDATA%\Panda3D-TTRMDev-1.11.0-x64\python\ppython.exe"
if not exist "%PPYTHON_PATH%" (
    echo Panda3D Python was not found. Install Panda3D or update PPYTHON_PATH.
    pause
    exit /b 1
)

:startGame
set TTOFF_PLAY_TOKEN=dev
set TTOFF_GAME_MODE=0

"%PPYTHON_PATH%" -m toontown.launcher.ToontownOfflineQuickStartLauncher
pause
