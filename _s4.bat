@echo off
cd /d C:\Users\Administrator\Desktop\Cloud-Stamping
start /B "CloudStamping" cmd /c "py -3.13 -X utf8 _run_server.py >> _server.log 2>&1"
timeout /t 4 /nobreak >nul
netstat -ano | findstr ":8000"
