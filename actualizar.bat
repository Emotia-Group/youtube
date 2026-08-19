@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ================================================
echo    Actualizar ytstudio
echo  ================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] No se encontro Git. Instalalo desde https://git-scm.com
  echo  o con: winget install Git.Git
  echo.
  pause
  exit /b 1
)

rem Rama en la que estas: se actualiza ESA, no una fija.
set RAMA=
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set RAMA=%%b
if not defined RAMA (
  echo  [ERROR] Esta carpeta no es un repositorio de Git.
  echo  Deberias estar en la carpeta donde clonaste el programa.
  echo.
  pause
  exit /b 1
)

rem Version ANTES: primer encabezado del CHANGELOG (lo mismo que muestra la
rem interfaz arriba a la izquierda).
set ANTES_V=
for /f "tokens=2" %%v in ('findstr /b /c:"## v" CHANGELOG.md 2^>nul') do (
  if not defined ANTES_V set ANTES_V=%%v
)

echo  Rama:           %RAMA%
echo  Version ahora:  %ANTES_V%
echo.
echo  Trayendo cambios de origin/%RAMA%...
echo.

rem --ff-only: avanza solo si no hay conflicto. Nunca crea un merge raro ni
rem abre un editor a media actualizacion.
git pull --ff-only origin %RAMA%
if errorlevel 1 goto :fallo

rem Version DESPUES
set DESPUES_V=
for /f "tokens=2" %%v in ('findstr /b /c:"## v" CHANGELOG.md 2^>nul') do (
  if not defined DESPUES_V set DESPUES_V=%%v
)

echo.
if "%ANTES_V%"=="%DESPUES_V%" (
  echo  ------------------------------------------------
  echo   YA ESTABAS AL DIA: no habia nada nuevo.
  echo   Version: %DESPUES_V%
  echo  ------------------------------------------------
  echo.
  echo  Si esperabas una version mas nueva, comprueba que estas
  echo  en la rama correcta. La tuya es: %RAMA%
  echo  Para ver las que hay en el servidor:  git branch -r
  echo.
  pause
  exit /b 0
)

echo  ------------------------------------------------
echo   ACTUALIZADO: %ANTES_V%  ^-^-^>  %DESPUES_V%
echo  ------------------------------------------------
echo.
echo  Ultimo cambio:
git log -1 --oneline
echo.

echo  Instalando dependencias nuevas (si las hay)...
py -m pip install -r requirements.txt --quiet
echo.
echo  ------------------------------------------------
echo   IMPORTANTE: si el programa estaba abierto, CIERRALO
echo   y vuelve a abrirlo (iniciar.bat o panel.bat).
echo   Hasta entonces sigue corriendo la version vieja.
echo  ------------------------------------------------
echo.
pause
exit /b 0

:fallo
echo.
echo  ################################################
echo   NO SE PUDO ACTUALIZAR. Sigues en %ANTES_V%.
echo  ################################################
echo.
echo  Causas habituales, y como salir de cada una:
echo.
echo  1) Tienes cambios locales en archivos del programa.
echo     Ver cuales:      git status
echo     Descartarlos:    git checkout .
echo     (Tus proyectos, tus claves .env, config.local.yaml y los datos
echo      del panel NO se tocan: viven fuera del repositorio.)
echo.
echo  2) La rama "%RAMA%" no existe en el servidor todavia.
echo     Ver las que hay: git branch -r
echo.
echo  3) Tu historial se separo del remoto.
echo     En ese caso:     git pull --rebase origin %RAMA%
echo.
echo  Copia TODO lo que sale arriba y pasaselo a Claude.
echo.
pause
exit /b 1
