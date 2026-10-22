@echo off
rem ArUco Tag Maker launcher for Windows. Double-click it, or run:
rem   run.bat                      open the app
rem   run.bat generate --names F   any aruco-tag-maker command works too
rem
rem First run: finds Python 3.11+, makes a private .venv next to this file and
rem installs everything into it. Later runs skip straight to launching unless
rem the dependencies changed. Nothing is installed system-wide.
rem Set ARUCO_TAG_MAKER_PYTHON=C:\path\to\python.exe to pick a Python.

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "HERE=%~dp0"
set "VENV=%HERE%.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "STAMP=%VENV%\.aruco-tag-maker-installed"
set "VERSION_OK=import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
set "IMPORTS=import aruco_tag_maker, cv2, manifold3d, numpy, PIL"

rem 1. Find a Python 3.11+ ---------------------------------------------------
set "PY="
if defined ARUCO_TAG_MAKER_PYTHON (
    "%ARUCO_TAG_MAKER_PYTHON%" -c "%VERSION_OK%" >nul 2>&1 && set PY="%ARUCO_TAG_MAKER_PYTHON%"
)
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3" "python" "python3") do (
    if not defined PY (
        %%~C -c "%VERSION_OK%" >nul 2>&1 && set "PY=%%~C"
    )
)
if not defined PY (
    echo.
    echo [aruco-tag-maker] PROBLEM: Python 3.11 or newer was not found.
    echo     Install it from https://www.python.org/downloads/windows/
    echo     In the installer, tick "Add python.exe to PATH" and keep "tcl/tk and IDLE" ticked.
    echo     Then double-click run.bat again.
    goto :fail
)
for /f "delims=" %%V in ('"%PY% -c "import sys; print('Python', sys.version.split()[0])""') do set "PYVER=%%V"
echo [aruco-tag-maker] Using %PYVER% (%PY%)

rem 2. Tk is needed for the window (not for generate / verify) --------------
set "NEEDS_WINDOW=1"
for %%A in (generate verify doctor -h --help --version) do if /i "%~1"=="%%A" set "NEEDS_WINDOW=0"
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    if "!NEEDS_WINDOW!"=="1" (
        echo.
        echo [aruco-tag-maker] PROBLEM: This Python has no tkinter, which the app window needs.
        echo     Re-run the Python installer from https://www.python.org/downloads/windows/
        echo     choose "Modify" and tick "tcl/tk and IDLE". Then double-click run.bat again.
        echo     Without Tk you can still script it: run.bat generate --names names.txt
        goto :fail
    )
    echo [aruco-tag-maker] Note: tkinter is missing; fine for "%~1", but the window will not open.
)

rem 3. Private virtual environment --------------------------------------------
if exist "%VPY%" (
    "%VPY%" -c "import sys" >nul 2>&1 || rmdir /s /q "%VENV%"
)
if not exist "%VPY%" (
    echo [aruco-tag-maker] First run: creating a private Python environment in .venv ^(one time only^)...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        if exist "%VENV%" rmdir /s /q "%VENV%"
        echo.
        echo [aruco-tag-maker] PROBLEM: Could not create the virtual environment.
        echo     Reinstall Python from https://www.python.org/downloads/windows/ and try again.
        goto :fail
    )
)

rem 4. Install / update only when pyproject.toml or Python changed ----------
set "WANT="
for /f "delims=" %%H in ('""%VPY%" -c "import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], 'rb').read() + sys.version.encode()).hexdigest())" "%HERE%pyproject.toml""') do set "WANT=%%H"
if not defined WANT (
    echo [aruco-tag-maker] PROBLEM: Could not read pyproject.toml next to run.bat.
    goto :fail
)
set "HAVE="
if exist "%STAMP%" set /p HAVE=<"%STAMP%"
set "INSTALL=0"
if not "!WANT!"=="!HAVE!" set "INSTALL=1"
"%VPY%" -c "%IMPORTS%" >nul 2>&1 || set "INSTALL=1"
if "!INSTALL!"=="1" (
    echo [aruco-tag-maker] Installing aruco-tag-maker and its libraries ^(numpy, OpenCV, manifold3d, Pillow^)...
    echo [aruco-tag-maker] This needs internet once and takes a minute or two.
    "%VPY%" -m pip install --disable-pip-version-check --quiet --upgrade pip
    "%VPY%" -m pip install --disable-pip-version-check --quiet --upgrade --editable "%HERE%."
    if errorlevel 1 (
        echo.
        echo [aruco-tag-maker] PROBLEM: Installing the Python libraries failed ^(see the pip messages above^).
        echo     Check your internet connection and run run.bat again.
        echo     To start over completely, delete the .venv folder.
        goto :fail
    )
    "%VPY%" -c "%IMPORTS%"
    if errorlevel 1 (
        echo.
        echo [aruco-tag-maker] PROBLEM: The libraries installed but do not import ^(see the error above^).
        echo     Delete the .venv folder and run run.bat again.
        goto :fail
    )
    > "%STAMP%" echo !WANT!
    echo [aruco-tag-maker] Install complete.
) else (
    echo [aruco-tag-maker] Everything is already installed.
)

rem 5. Launch ------------------------------------------------------------------
if "%~1"=="" echo [aruco-tag-maker] Opening the ArUco Tag Maker window...
"%VPY%" -m aruco_tag_maker %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo [aruco-tag-maker] The app exited with code %CODE%.
    if "%~1"=="" pause
)
exit /b %CODE%

:fail
echo.
pause
exit /b 1
