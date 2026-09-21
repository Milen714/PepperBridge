@echo off
setlocal enabledelayedexpansion

:: 1. Change directory to Choregraphe bin
cd /d "C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin"

:: 2. Find Pepper's IP address via nslookup
echo Resolving Pepper's IP address...
set "PEPPER_IP="

for /f "tokens=2 delims=:" %%A in ('nslookup pepper 2^>nul ^| findstr /i "Address"') do (
    set "TEMP_IP=%%A"
    :: Strip leading spaces
    set "TEMP_IP=!TEMP_IP: =!"
    set "PEPPER_IP=!TEMP_IP!"
)

:: Check if IP was found
if "%PEPPER_IP%"=="" (
    echo [ERROR] Could not resolve IP for "pepper". Please check your network connection.
    pause
    exit /b
)

echo Found Pepper IP: %PEPPER_IP%
echo ----------------------------------------------------

:: 3. Execute the 3 qicli commands sequentially
echo [1/3] Setting AutonomousLife state to solitary...
.\qicli.exe --qi-url=tcp://%PEPPER_IP%:9559 call ALAutonomousLife.setState "solitary"
echo.

echo [2/3] Checking activity context permission violations...
.\qicli.exe --qi-url=tcp://%PEPPER_IP%:9559 call ALAutonomousLife.getActivityContextPermissionViolations "boot-config/."
echo.

echo [3/3] Switching focus to boot-config...
.\qicli.exe --qi-url=tcp://%PEPPER_IP%:9559 call ALAutonomousLife.switchFocus "boot-config/."
echo.

echo All commands executed successfully.
pause