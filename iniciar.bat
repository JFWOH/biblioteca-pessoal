@echo off
setlocal

rem Diretório do próprio script — funciona em qualquer pasta/drive onde o
rem repositório for clonado (sem caminhos fixos de máquina).
set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%venv\Scripts\python.exe"

cd /d "%PROJECT_DIR%"

if not exist "%VENV_PYTHON%" (
    echo [ERRO] venv nao encontrado em: %VENV_PYTHON%
    echo Crie o ambiente virtual com Python 3.11:
    echo     python -m venv venv
    echo     venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%VENV_PYTHON%" -c "import sys; assert sys.version_info[:2] == (3,11), 'Python 3.11 esperado'" 2>nul
if errorlevel 1 (
    echo [ERRO] Versao do Python incorreta no venv. Recrie com Python 3.11.
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
