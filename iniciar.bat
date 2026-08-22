@echo off
setlocal EnableDelayedExpansion

rem ===================================================================
rem  AgroScout IA Lite -- arranque del sistema
rem
rem  Abre una ventana por servicio: la API (uvicorn, :8001) y la SPA
rem  (vite, :3000). Espera a que las dos escuchen y abre el navegador.
rem  Los logs se ven en vivo en cada ventana.
rem
rem  Uso:
rem    iniciar.bat            API + SPA
rem    iniciar.bat worker     ademas el worker de Procrastinate
rem    iniciar.bat recarga    la API con --reload (desarrollo)
rem
rem  Para pararlo todo: detener.bat
rem ===================================================================

cd /d "%~dp0"
title AgroScout -- arranque

set "CON_WORKER=0"
set "RECARGA="

:leer_args
if "%~1"=="" goto args_leidos
if /i "%~1"=="worker"    set "CON_WORKER=1"
if /i "%~1"=="--worker"  set "CON_WORKER=1"
if /i "%~1"=="recarga"   set "RECARGA=--reload"
if /i "%~1"=="--recarga" set "RECARGA=--reload"
shift
goto leer_args
:args_leidos

echo.
echo ==================================================
echo   AgroScout IA Lite -- arrancando
echo ==================================================
echo.

rem --- Requisitos ---------------------------------------------------
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No encuentro 'uv' en el PATH.
    echo         La API corre con uv; venv\ es otro entorno y no trae fastapi.
    goto abortar
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No encuentro 'npm' en el PATH. La SPA lo necesita.
    goto abortar
)

if not exist ".env" (
    echo [ERROR] Falta .env en la raiz. Copia .env.example y rellenalo.
    goto abortar
)

if not exist "frontend\node_modules" (
    echo [ .. ] frontend\node_modules no existe: instalando dependencias.
    call npm install --prefix frontend
    if errorlevel 1 (
        echo [ERROR] npm install fallo. No sigo.
        goto abortar
    )
)

if not exist "logs" mkdir "logs"

rem --- Puertos libres -----------------------------------------------
call :puerto_en_uso 8001
if "!EN_USO!"=="1" (
    echo [ERROR] El puerto 8001 ya esta ocupado: la API ya corre, o algo la suplanta.
    echo         Ejecuta detener.bat y vuelve a intentarlo.
    goto abortar
)
call :puerto_en_uso 3000
if "!EN_USO!"=="1" (
    echo [ERROR] El puerto 3000 ya esta ocupado.
    echo         Ejecuta detener.bat y vuelve a intentarlo.
    goto abortar
)

rem --- Contexto, para no arrancar a ciegas ---------------------------
set "APP_DB="
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"APP_DB=" ".env"`) do set "APP_DB=%%b"
set "API_SPA="
if exist "frontend\.env.local" (
    for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"VITE_API_URL=" "frontend\.env.local"`) do set "API_SPA=%%b"
)
if not defined API_SPA set "API_SPA=http://localhost:8001  [por defecto: no hay frontend\.env.local]"

echo   Estado de aplicacion .... !APP_DB!
echo   La SPA llamara a ........ !API_SPA!
echo.

rem --- Lanzar --------------------------------------------------------
echo [ .. ] Abriendo la ventana de la API en :8001
start "AgroScout API" cmd /k "title AgroScout API&&set PYTHONIOENCODING=utf-8&&uv run uvicorn api.main:app --host 0.0.0.0 --port 8001 !RECARGA!"

echo [ .. ] Abriendo la ventana de la SPA en :3000
start "AgroScout SPA" /d "%~dp0frontend" cmd /k "title AgroScout SPA&&npx vite --host 0.0.0.0 --port 3000"

if "!CON_WORKER!"=="1" (
    echo [ .. ] Abriendo la ventana del worker de Procrastinate
    start "AgroScout Worker" cmd /k "title AgroScout Worker&&set PYTHONIOENCODING=utf-8&&uv run python scripts\start_worker.py"
)

rem --- Esperar a la API ----------------------------------------------
set "API_OK=0"
set "SPA_OK=0"
echo.
echo [ .. ] Esperando a la API. El primer arranque carga bge-m3 en RAM y tarda.
set /a INTENTOS=0
:esperar_api
call :puerto_en_uso 8001
if "!EN_USO!"=="1" goto api_arriba
set /a INTENTOS+=1
if !INTENTOS! GEQ 90 (
    echo.
    echo [AVISO] La API no escucha en :8001 despues de 3 minutos.
    echo         El motivo esta en la ventana "AgroScout API".
    goto tras_api
)
<nul set /p "=."
ping -n 3 127.0.0.1 >nul
goto esperar_api
:api_arriba
set "API_OK=1"
echo.
echo [ OK ] API escuchando en :8001
:tras_api

rem --- Esperar a la SPA ----------------------------------------------
set /a INTENTOS=0
:esperar_spa
call :puerto_en_uso 3000
if "!EN_USO!"=="1" goto spa_arriba
set /a INTENTOS+=1
if !INTENTOS! GEQ 30 (
    echo [AVISO] La SPA no escucha en :3000 despues de 1 minuto.
    echo         El motivo esta en la ventana "AgroScout SPA".
    goto tras_spa
)
<nul set /p "=."
ping -n 3 127.0.0.1 >nul
goto esperar_spa
:spa_arriba
set "SPA_OK=1"
echo [ OK ] SPA escuchando en :3000
:tras_spa

echo.
echo ==================================================
if "!API_OK!!SPA_OK!"=="11" (
    echo   En pie
) else (
    echo   Arranque incompleto
)
echo ==================================================
if "!SPA_OK!"=="1" (
    echo   SPA ......... http://localhost:3000
) else (
    echo   SPA ......... no responde en :3000 -- el motivo, en su ventana
)
if "!API_OK!"=="1" (
    echo   API ......... http://localhost:8001
    echo   Salud ....... http://localhost:8001/health
    echo   Contratos ... http://localhost:8001/docs
) else (
    echo   API ......... no responde en :8001 -- el motivo, en su ventana
)
echo.
echo   Para pararlo todo: detener.bat
echo.

rem  El navegador solo si hay algo que mirar: una pestana en blanco no
rem  distingue "aun arrancando" de "reventado".
if "!SPA_OK!"=="1" start "" "http://localhost:3000"

echo Esta ventana ya no hace falta: los servicios viven en las suyas.
pause
endlocal
exit /b 0

rem --- Subrutinas -----------------------------------------------------

:puerto_en_uso
rem  %1 = puerto.  Deja EN_USO a 1 si alguien escucha ahi.
set "EN_USO=0"
netstat -ano -p TCP | findstr /r /c:":%~1 .*LISTENING" >nul 2>&1
if not errorlevel 1 set "EN_USO=1"
exit /b

:abortar
echo.
echo Arranque cancelado: no se ha levantado nada.
echo.
pause
endlocal
exit /b 1
