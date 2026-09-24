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

echo [1/3] Testing microphone energy level...
.\qicli.exe --qi-url=tcp://192.168.1.122:9559 call ALAudioDevice.getFrontMicEnergy
echo.


echo All commands executed successfully.
pause