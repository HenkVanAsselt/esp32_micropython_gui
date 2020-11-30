@echo off

cdd tnsim

grep -l ">>>" *.py > doctestfiles.txt
echo *************************
echo Files with ">>>" doctests
type doctestfiles.txt
echo *************************

FOR /F %x IN (doctestfiles.txt) DO (
	IF "%x" == "tracetool.py" (
		ECHO Skipping %x
	) ELSE (	
		echo Doctest %x
		python -m doctest %x
	)
)

cdd -