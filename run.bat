@echo off
rem Doppio clic su Windows per avviare SplitterNSP (la prima volta installa PySide6).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Prima installazione: preparo l'ambiente Python...
  python -m venv .venv || goto :err
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -r requirements.txt || goto :err
)
start "" .venv\Scripts\pythonw.exe -m splitter_nsp %*
exit /b 0
:err
echo Serve Python 3.9 o superiore: https://www.python.org/downloads/
pause
