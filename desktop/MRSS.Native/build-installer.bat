@echo off
setlocal
cd /d "%~dp0"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
