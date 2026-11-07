@echo off
REM Build OfflineOCR.exe on Windows.
REM REQUIRES Python 3.11 (3.10 also works). Python 3.13/3.14 will FAIL because some
REM packages have no prebuilt wheels there (needs C++ Build Tools).
REM Also needs Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
setlocal
set PYV=3.11
py -%PYV% --version >nul 2>&1
if errorlevel 1 set PYV=3.10
py -%PYV% --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or 3.10 not found. Install Python 3.11 from
  echo https://www.python.org/downloads/release/python-3119/  ^(tick "Add to PATH"^)
  goto :err
)
echo Using Python %PYV%  ^(if you do not see this line you are running an OLD build_exe.bat^)
if exist venv rmdir /s /q venv
py -%PYV% -m venv venv || goto :err
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install --only-binary=:all: torch torchvision --index-url https://download.pytorch.org/whl/cpu || goto :err
pip install --only-binary=:all: -r requirements.txt || goto :err
python tools\prepare_vendor.py || goto :err
pyinstaller --noconfirm OfflineOCR.spec || goto :err
echo.
echo DONE:  dist\OfflineOCR\OfflineOCR.exe   (copy the whole OfflineOCR folder)
pause
exit /b 0
:err
echo BUILD FAILED
pause
exit /b 1
