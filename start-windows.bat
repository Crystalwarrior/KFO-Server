@echo off
:while
echo Starting up server...
python start_server.py
echo Server has shut down, restarting...
timeout /t 2 /nobreak
goto :while
