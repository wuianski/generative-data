@echo off
rem Daily pipeline: scrape 100 IG home-feed images, then caption them with BLIP.
rem Register with Task Scheduler (see README) to run every day at 06:00.
setlocal EnableExtensions

cd /d "%~dp0"

set "PY_SCRAPER=%USERPROFILE%\miniconda3\envs\scraper\python.exe"
set "PY_CAPTION=%USERPROFILE%\miniconda3\envs\img2txt\python.exe"

if not exist logs mkdir logs
set "LOG=logs\daily.log"

rem PowerShell date is locale-independent. The old `python -c` for /f
rem capture fails silently on many Windows setups (nested quotes),
rem which left RUN_DATE empty and aborted scraper.py on --date.
set "RUN_DATE="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`) do set "RUN_DATE=%%i"

echo ==== run_daily started %date% %time% (RUN_DATE=%RUN_DATE%) ==== >> "%LOG%"

if not defined RUN_DATE (
    echo WARNING: could not pin RUN_DATE, using scraper's default >> "%LOG%"
    "%PY_SCRAPER%" scraper.py --limit 100 >> "%LOG%" 2>&1
) else (
    "%PY_SCRAPER%" scraper.py --limit 100 --date %RUN_DATE% >> "%LOG%" 2>&1
)
if errorlevel 1 (
    echo scraper.py FAILED >> "%LOG%"
    exit /b 1
)

rem --missing captions every day folder without captions.json, so interrupted
rem earlier runs are healed automatically.
"%PY_CAPTION%" caption.py --missing >> "%LOG%" 2>&1
if errorlevel 1 (
    echo caption.py FAILED >> "%LOG%"
    exit /b 1
)
echo ==== run_daily finished %date% %time% ==== >> "%LOG%"
