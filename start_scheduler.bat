@echo off
REM Start the Daily Report Scheduler
echo ================================================================================
echo STARTING DAILY REPORT SCHEDULER
echo ================================================================================
echo.
echo This will run in the background and send reports daily at 9:00 AM IST
echo 
echo.
echo Press Ctrl+C to stop the scheduler
echo.
echo ================================================================================
echo.

cd /d "%~dp0"
python scheduler.py

pause

