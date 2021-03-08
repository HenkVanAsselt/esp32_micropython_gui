@echo off

rem -----------------------------------------------------------------------
rem Check command line parameters
rem -----------------------------------------------------------------------
if "%1"==""   goto usage
if "%1"=="?"  goto usage
if "%1"=="-?" goto usage
if "%1"=="-h" goto usage
if "%1"=="--help" goto usage
goto %1
goto _eof

:usage
echo -----------------------------------------------------------------
echo ESP32 SHELL makefile
echo -----------------------------------------------------------------
echo make pylint        Run pylint on the whole source folder
echo make flake8        Run flake 8 on the whole source folder
echo make vulture       Find dead code
echo.
echo make pip           Install all (updated) requirements.
echo make ui2py         Convert QT5 UIO design file to py design file
echo make clean         Clean up temporary file
echo.
echo make sphinx        Generate sphinx user documentation
echo make apidoc        Generate sphinx api documentation
echo make doxygen       Make doxygen documentation
echo.
echo make installer      make full installation (py2exe and nsis installer)
echo make doxygen        make doxygen documentation
echo.
goto _eof


rem --- Run pylint
:pylint
    pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" -r n -d E0611,R0201,C0301 --extension-pkg-whitelist=win32api --ignore=esp32shell_qt_design.py src
    goto _eof

rem --- Run flake8 
:flake8
    flake8 --exclude=lib,tests,*_qt_design*,doc --max-line-length=140 --ignore=
    goto _eof

rem --- Run vulture to detect unused functions and/or variables
:vulture
    vulture.cmd
    goto _eof

rem --- Update Python libraries (using requirements.txt)
:pip
    python.exe -m pip install --upgrade pip
    pip install -r requirements.txt --upgrade
    goto _eof

rem --- convert QT designer UI file to .py file
:ui2py
    pushd src
    rem pyside2-uic.exe esp32shell_qt_design.ui -o esp32shell_qt_design.py
	C:\Users\HenkA\AppData\Local\Programs\Python\Python38\Scripts\pyuic5.exe esp32shell_qt_design.ui -o esp32shell_qt_design.py
    popd
    goto _eof

rem --- Generate DOXYGEN documentation
:doxygen
    call doxygen 
    goto _eof
	
:show_doxygen
	"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" doc\doxygen\html\index.html
	goto _eof

:sphinx
    pushd doc & call make html & popd
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" doc\_build\html\index.html
    goto _eof
    
:apidoc
    sphinx-apidoc -o ./doc/_modules ./src
    goto _eof
    
:pyinstaller
    REM --- Create the CLI executable with all supporting python files
    pyinstaller src\esp32cli.py
    REM --- Create the standalone CLI executable 
    pyinstaller --onefile src\esp32cli.py
    REM --- Create the GUI executable with all supporting python files
    pyinstaller src\esp32gui.py
    REM --- Create the standalone GUI executable 
    pyinstaller --onefile src\esp32gui.py   
    goto _eof
    
:mypy
    pushd src
    mypy .
    popd 
    goto _eof

:clean
    del /S *.bak
    pushd src & rmdir /S /Q __pycache__ & popd
    pushd src & rmdir /S /Q .pytest_cache & popd
    pushd src\lib & rmdir /S /Q .pytest_cache & popd
    pushd doc\doxygen & rmdir /S /Q html & popd
    pushd doc & make clean & popd

:_eof