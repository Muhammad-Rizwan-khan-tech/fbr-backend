@echo off
setlocal enabledelayedexpansion

echo ====================================================================
echo  FBR Invoice Cloud — Windows Desktop Application Builder
echo ====================================================================

REM Ensure Rust tools write to E:\ drive to protect C:\ drive disk space
if not exist "E:\tools\cargo" mkdir "E:\tools\cargo"
if not exist "E:\tools\rustup" mkdir "E:\tools\rustup"

set "CARGO_HOME=E:\tools\cargo"
set "RUSTUP_HOME=E:\tools\rustup"
set "PATH=%CARGO_HOME%\bin;C:\Users\RizwaN\.cargo\bin;%PATH%"

echo [1/3] Building React & TypeScript Web Frontend Bundle...
cd /d "%~dp0..\frontend"
call npm.cmd run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed.
    exit /b %ERRORLEVEL%
)

echo [2/3] Checking Rust and Cargo Toolchain...
where cargo >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Cargo was not found in standard PATH.
    echo Please install Rust or ensure rustup stable is configured.
    echo Note: CARGO_HOME is set to %CARGO_HOME% to safeguard C:\ drive space.
    exit /b 1
)

echo [3/3] Compiling Tauri Desktop Binary and Windows Installer...
call npm.cmd run desktop:build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Tauri build failed.
    exit /b %ERRORLEVEL%
)

echo ====================================================================
echo  Build Complete! Windows application generated in:
echo  frontend\src-tauri\target\release\
echo ====================================================================
