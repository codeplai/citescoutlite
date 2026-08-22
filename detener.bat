@echo off
setlocal EnableDelayedExpansion

rem ===================================================================
rem  AgroScout IA Lite -- parada del sistema
rem
rem  Tres pasadas, de la mas precisa a la mas bruta:
rem    1. las ventanas que abrio iniciar.bat, por su linea de comandos
rem       (taskkill /T se lleva el arbol: cmd -> uv/npx -> python/node)
rem    2. el worker, que no ocupa puerto y hay que buscarlo por nombre
rem    3. lo que siga escuchando en :8001 o :3000, venga de donde venga
rem
rem  Uso: detener.bat
rem ===================================================================

cd /d "%~dp0"
title AgroScout -- parada

echo.
echo ==================================================
echo   AgroScout IA Lite -- deteniendo
echo ==================================================
echo.

set /a MUERTOS=0

rem --- 1 y 2. Por linea de comandos -----------------------------------
rem  El wrapper que abre iniciar.bat lleva "title AgroScout ..." en su
rem  propia linea de comandos, asi que se reconoce sin depender del
rem  filtro WINDOWTITLE de taskkill, que bajo Windows Terminal no siempre
rem  ve el titulo. El worker se busca ademas por el script, para cazarlo
rem  aunque lo hayan arrancado a mano. La consulta se excluye a si
rem  misma ($PID): el patron que busca viaja en su propia linea de
rem  comandos, asi que sin eso se encontraria siempre a ella.
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$todos = Get-CimInstance Win32_Process; foreach($x in $todos){ if($x.ProcessId -ne $PID -and ($x.CommandLine -like '*title AgroScout*' -or $x.CommandLine -like '*start_worker.py*')){ $x.ProcessId } }"`) do (
    taskkill /F /T /PID %%p >nul 2>&1 && (
        set /a MUERTOS+=1
        echo [ OK ] proceso %%p terminado ^(ventana de servicio^)
    )
)

rem --- 3. Lo que quede en los puertos ---------------------------------
call :matar_puerto 8001 "API"
call :matar_puerto 3000 "SPA"

rem --- Comprobacion ---------------------------------------------------
echo.
call :verificar 8001 "API"
call :verificar 3000 "SPA"

echo.
if !MUERTOS! EQU 0 (
    echo No habia nada corriendo.
) else (
    echo Detenidos !MUERTOS! procesos.
)
echo.
pause
endlocal
exit /b 0

rem --- Subrutinas ------------------------------------------------------

:matar_puerto
rem  %1 = puerto, %2 = etiqueta para el mensaje.
set "ENCONTRADO=0"
for /f "usebackq tokens=5" %%p in (`netstat -ano -p TCP ^| findstr /r /c:":%~1 .*LISTENING"`) do (
    taskkill /F /T /PID %%p >nul 2>&1 && (
        set "ENCONTRADO=1"
        set /a MUERTOS+=1
        echo [ OK ] %~2 :%~1 -- proceso %%p terminado
    )
)
if "!ENCONTRADO!"=="0" echo [ -- ] %~2 :%~1 -- no quedaba nada escuchando
exit /b

:verificar
rem  %1 = puerto, %2 = etiqueta.
netstat -ano -p TCP | findstr /r /c:":%~1 .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [ OK ] %~2 :%~1 libre
) else (
    echo [AVISO] %~2 :%~1 sigue ocupado. Quien lo tiene:  netstat -ano ^| findstr :%~1
)
exit /b
