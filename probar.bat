@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ================================================
echo   ytstudio - revision de salud del programa
echo  ================================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] No se encontro Python. Instalalo desde python.org
  echo  o con: winget install Python.Python.3
  pause
  exit /b 1
)
echo  Corriendo las baterias de prueba. Tarda unos minutos.
echo  No usa claves de API ni internet, y no toca tus proyectos.
echo.
py tests\probar_todo.py %*
echo.
pause
