@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ================================================
echo   Traer la ultima version (pull rapido)
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

rem Rama en la que estas ahora: se trae ESA, no una fija. Asi el .bat sirve
rem igual en la rama del panel que en cualquier otra.
set RAMA=
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set RAMA=%%b
if not defined RAMA (
  echo  [ERROR] Esta carpeta no es un repositorio de Git.
  echo  Deberias estar en la carpeta donde clonaste el programa.
  echo.
  pause
  exit /b 1
)

rem Punto de partida, para saber DESPUES que cambio exactamente.
for /f "tokens=*" %%h in ('git rev-parse HEAD') do set ANTES=%%h

echo  Rama: %RAMA%
echo  Trayendo cambios de origin/%RAMA%...
echo.

rem --ff-only: avanza solo si no hay conflicto. Nunca crea un merge raro ni
rem abre un editor de texto a media actualizacion.
git pull --ff-only origin %RAMA%
if errorlevel 1 goto :fallo

for /f "tokens=*" %%h in ('git rev-parse HEAD') do set DESPUES=%%h

echo.
if "%ANTES%"=="%DESPUES%" (
  echo  Ya estabas al dia: no habia nada nuevo.
  goto :version
)

echo  Actualizado. Ultimo cambio:
git log -1 --oneline
echo.

rem Si cambiaron las dependencias, un pull solo no basta: hay que avisar.
git diff --name-only %ANTES% %DESPUES% > "%TEMP%\ytpull_cambios.txt" 2>nul
findstr /i "requirements.txt" "%TEMP%\ytpull_cambios.txt" >nul
if not errorlevel 1 (
  echo  [!] Esta version cambio las dependencias de Python.
  echo      Ejecuta actualizar.bat una vez para instalarlas.
  echo.
)
del "%TEMP%\ytpull_cambios.txt" >nul 2>nul

:version
rem Version activa = primer encabezado del CHANGELOG (lo mismo que muestra
rem la interfaz arriba a la izquierda).
set VERSION=
for /f "tokens=2" %%v in ('findstr /b /c:"## v" CHANGELOG.md 2^>nul') do (
  if not defined VERSION set VERSION=%%v
)
if defined VERSION echo  Version en disco: %VERSION%
echo.
echo  Recuerda: si el programa estaba abierto, cierralo y vuelve a abrirlo
echo  (iniciar.bat o panel.bat) para que corra la version nueva.
echo.
pause
exit /b 0

:fallo
echo.
echo  ------------------------------------------------
echo   No se pudo actualizar. Causas habituales:
echo  ------------------------------------------------
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
echo  3) Tu historial se separo del remoto (hiciste commits propios).
echo     En ese caso:     git pull --rebase origin %RAMA%
echo.
pause
exit /b 1
