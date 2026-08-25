@echo off
setlocal EnableDelayedExpansion

rem ===================================================================
rem  AgroScout IA Lite -- actualizacion completa del snapshot 2026-07
rem
rem  Corre las cinco etapas en orden y manda un correo de estado cada
rem  hora a la direccion de SMTP_DESTINO:
rem
rem    1. canasta   cosecha de 400 formas de producto en Peru
rem    2. imagenes  imagen_url verificada de los 28.642 productos OFF
rem    3. merge     OFF + USDA + terminados + canasta
rem    4. indexar   embeddings bge-m3 de lo nuevo (incremental)
rem    5. manifest  SHA256 y estadisticas recalculadas
rem
rem  Las etapas 1 y 2 se reanudan solas: si esto se corta a medias,
rem  volver a ejecutar pipeline.bat continua donde se quedo.
rem
rem  Uso:
rem    pipeline.bat                    todo, con correo
rem    pipeline.bat --sin-correo       todo, sin correo
rem    pipeline.bat --solo merge,indexar,manifest
rem ===================================================================

cd /d "%~dp0"
title AgroScout -- pipeline del snapshot

echo.
echo ==================================================
echo   AgroScout -- actualizacion del snapshot
echo ==================================================
echo.

rem --- Requisitos ------------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Falta venv\Scripts\python.exe
    echo         Es el entorno con lancedb, sentence-transformers y torch.
    echo         Sin el no se pueden generar embeddings.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [AVISO] No hay .env: el pipeline correra sin mandar correos.
    echo         Para activarlos, copia .env.example a .env y rellena
    echo         SMTP_USUARIO, SMTP_PASSWORD y SMTP_DESTINO.
    echo.
)

if not exist "logs" mkdir logs

rem --- Ejecucion -------------------------------------------------------
rem  El orquestador vive en Python y no aqui porque tiene que hacer dos
rem  cosas a la vez: correr las etapas y mandar el parte cada hora. Un
rem  .bat no sabe hacer eso sin abrir otra ventana que luego nadie cierra.
echo [INFO] Arrancando. El avance se escribe en logs\pipeline_snapshot.log
echo [INFO] Se puede cerrar esta ventana con Ctrl+C; al relanzar, continua.
echo.

venv\Scripts\python.exe -m scripts.pipeline_snapshot %*
set CODIGO=%ERRORLEVEL%

echo.
if "%CODIGO%"=="0" (
    echo [ OK ] Pipeline completo.
) else (
    echo [FALLO] El pipeline se detuvo. Mira logs\pipeline_snapshot.log
    echo         Al arreglarlo, vuelve a ejecutar pipeline.bat: las etapas
    echo         de descarga continuan donde se quedaron.
)
echo.

rem  El `pause` es para quien lo abre con doble clic: sin el, la ventana se
rem  cierra antes de que se pueda leer el resultado. Estorba en una corrida
rem  desatendida, donde nadie va a pulsar nada y el proceso quedaria colgado
rem  para siempre, asi que se salta con AGROSCOUT_SIN_PAUSA=1.
if not defined AGROSCOUT_SIN_PAUSA pause
endlocal
exit /b %CODIGO%
