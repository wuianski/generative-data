@echo off
rem Daily pipeline: scrape 100 IG home-feed images, then caption them with BLIP.
rem Register with Task Scheduler (see README) to run every day at 06:00.
setlocal

cd /d "%~dp0"

set "PY_SCRAPER=%USERPROFILE%\miniconda3\envs\scraper\python.exe"
set "PY_CAPTION=%USERPROFILE%\miniconda3\envs\img2txt\python.exe"

if not exist logs mkdir logs
set "LOG=logs\daily.log"

echo ==== run_daily started %date% %time% ==== >> "%LOG%"
"%PY_SCRAPER%" scraper.py --limit 100 >> "%LOG%" 2>&1
if errorlevel 1 (
    echo scraper.py FAILED >> "%LOG%"
    exit /b 1
)
"%PY_CAPTION%" caption.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo caption.py FAILED >> "%LOG%"
    exit /b 1
)
echo ==== run_daily finished %date% %time% ==== >> "%LOG%"
