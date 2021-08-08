rem 
rem Run Vulture to discover Unused functions and variables.
rem

pushd src
vulture.exe . --exclude=lib,tracetool.py,dict4ini.py,cmd2.py,run.py,images.py,adb_wrapper_test.py,devil_env.py,platform-tools,archive,ttrace_demo26.py,device_utils.py,conf.py,src\upydev
popd