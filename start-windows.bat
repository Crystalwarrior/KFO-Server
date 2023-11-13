@echo off
:while
echo Starting up server...
venv\Scripts\python start_server.py
echo Server has shut down, restarting...
timeout /t 2 /nobreak
goto :while
