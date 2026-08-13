@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ================================================
echo   Torre de Control - panel multicanal de YouTube
echo  ================================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] No se encontro Python. Instalalo desde python.org
  echo  o con: winget install Python.Python.3
  pause
  exit /b 1
)
echo  Iniciando... el navegador se abrira solo.
echo  Deja esta ventana abierta mientras uses el panel.
echo.
py -m ytpanel ui
pause
