@echo off
echo Fixing permissions for Email Campaign Manager...
echo.

REM Get current user
for /f "tokens=2 delims==" %%a in ('wmic computersystem get username /value ^| find "="') do set "currentuser=%%a"

echo Current user: %currentuser%
echo.

REM Fix permissions for data_lists directory
echo Fixing permissions for data_lists directory...
icacls "data_lists" /grant "%currentuser%:(OI)(CI)F" /T
if %errorlevel% equ 0 (
    echo ✅ data_lists permissions fixed successfully
) else (
    echo ❌ Failed to fix data_lists permissions
)

echo.

REM Fix permissions for current directory
echo Fixing permissions for current directory...
icacls "." /grant "%currentuser%:(OI)(CI)F" /T
if %errorlevel% equ 0 (
    echo ✅ Current directory permissions fixed successfully
) else (
    echo ❌ Failed to fix current directory permissions
)

echo.
echo Permission fix completed!
echo You can now run the application without permission errors.
pause 