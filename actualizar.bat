@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Actualizando ytstudio a la ultima version...
git pull
echo.
echo Instalando dependencias nuevas (si las hay)...
py -m pip install -r requirements.txt --quiet
echo.
echo Listo. Ya puedes abrir el programa con iniciar.bat
pause
