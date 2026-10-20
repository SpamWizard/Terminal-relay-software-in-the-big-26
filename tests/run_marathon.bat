@echo off
cd /d "%~dp0\.."
set RELAY_MARATHON_SECONDS=3300
set PYTHONUNBUFFERED=1
set PYTHONPATH=src
echo Marathon started %DATE% %TIME% seconds=%RELAY_MARATHON_SECONDS%> tests\_marathon_run.log
python -u -m pytest tests/ -o addopts= -m "marathon or not marathon" -v --tb=line -s >> tests\_marathon_run.log 2>&1
echo Marathon finished %DATE% %TIME% exit=%ERRORLEVEL%>> tests\_marathon_run.log
exit /b %ERRORLEVEL%
