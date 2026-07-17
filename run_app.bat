@echo off
echo ===================================================
echo Booting DME Fee Flow Server Core...
echo ===================================================

:: 1. Try activating venv without the dot
call venv\Scripts\activate

:: 2. Launch the Flask server in a minimized background window
start /min cmd /c "python app.py"

:: 3. Wait 5 seconds to give the server plenty of time to boot
timeout /t 5 /nobreak >nul

:: 4. Automatically open Chrome to the dashboard url
start http://127.0.0.1:5000/

exit