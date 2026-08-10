@echo off
setlocal
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=D:\StabilityMatrix\Data\Packages\ComfyUI_W"
powershell -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1" -ComfyUIRoot "%ROOT%"
if errorlevel 1 (
  echo Installation failed.
  pause
  exit /b 1
)
echo.
echo Installation completed.
pause
