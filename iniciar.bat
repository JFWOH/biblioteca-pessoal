@echo off
setlocal

set "PROJECT_DIR=G:\PROGRAMAS PYTHON\Biblioteca-pessoal"
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"

cd /d "%PROJECT_DIR%"

if not exist "%VENV_PYTHON%" (
    echo [ERRO] venv nao encontrado em: %VENV_PYTHON%
    echo Execute: C:\Users\jefer\AppData\Local\Programs\Python\Python311\python.exe -m venv venv
    pause
    exit /b 1
)

"%VENV_PYTHON%" -c "import sys; assert sys.version_info[:2] == (3,11), 'Python 3.11 esperado'" 2>nul
if errorlevel 1 (
    echo [ERRO] Versao do Python incorreta no venv.
    pause
    exit /b 1
)

echo Iniciando Biblioteca Pessoal...
"%VENV_PYTHON%" -m src.main

if errorlevel 1 (
    echo.
    echo [ERRO] O app encerrou com codigo de erro.
    pause
)

endlocal
