@echo off
title 26AS Parser with Auto-Cleanup
echo ========================================
echo   26AS PDF to Excel Converter
echo   Professional Edition with Auto-Cleanup
echo ========================================
echo.
echo Starting automatic cleanup system...
echo This will delete files older than 10 hours
echo from uploads and output folders.
echo.
echo Starting Flask application...
echo.

REM Start the cleanup script in the background
start /B python cleanup_old_files.py

REM Start the main Flask application
python app.py

REM When Flask app is closed, cleanup script will also stop
echo.
echo Application stopped.
echo Cleanup system will continue running in background.
echo To stop cleanup, close the cleanup console window.
pause