@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean MRSS.spec
if errorlevel 1 exit /b %errorlevel%
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
