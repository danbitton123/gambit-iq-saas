@echo off
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  set "PYTHON_CMD=python"
)
if not exist ".venv\Scripts\python.exe" %PYTHON_CMD% -m venv .venv
call .venv\Scripts\activate.bat
python -c "import streamlit, plotly" >nul 2>&1
if errorlevel 1 python -m pip install -r requirements.txt
python -m streamlit run app.py
