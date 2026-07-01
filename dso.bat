@echo off
REM DSO launcher (Windows).
REM   - typed in cmd/powershell -> runs the dashboard right here
REM   - double-clicked          -> Windows opens a console window and runs there
REM Same file for both. install.py adds this folder to PATH so `dso` works anywhere.
where python >nul 2>nul && (set PY=python) || (set PY=py)
"%PY%" "%~dp0src\dso.py" %*
