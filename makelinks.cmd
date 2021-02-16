REM --- This Win32 script makes links to existing folders to re-use libraries already available.
REM --- Run this from an elevated CMD, or use SUDO (see  https://github.com/gerardog/gsudo)
mklink /D src\lib d:\hva\projects\TelnetTester\src\lib
mklink /D src\mp D:\hva\projects\micropython\mpfshell-henka-fork\mp