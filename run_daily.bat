@echo off
rem Daily pipeline: scrape 100 IG home-feed images, then caption them with BLIP.
rem Register with Task Scheduler (see README) to run every day at 06:00.
setlocal

cd /d "%~dp0"

set "PY_SCRAPER=%USERPROFILE%\miniconda3\envs\scraper\python.exe"
set "PY_CAPTION=%USERPROFILE%\miniconda3\envs\img2txt\python.exe"

if not exist logs mkdir logs
set "LOG=logs\daily.log"

rem Pin one date for the whole run, so a scrape that stalls (e.g. laptop
rem sleeps mid-run) and resumes the next day still pairs with its captions.
for /f %%i in ('"%PY_SCRAPER%" -c "import datetime; print(datetime.date.today().isoformat())"') do set "RUN_DATE=%%i"

echo ==== run_daily started %date% %time% (RUN_DATE=%RUN_DATE%) ==== >> "%LOG%"
"%PY_SCRAPER%" scraper.py --limit 100 --date %RUN_DATE% >> "%LOG%" 2>&1
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
