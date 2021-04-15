esp32-shell
===========

CLI / GUI to control a connected ESP32, running micropython.

The CLI is almost entirely based on mpfshell (see https://github.com/wendlers/mpfshell).

Instead of using the regular **cmd** package, **cmd2** is used to create a command shell.
(see https://github.com/python-cmd2/cmd2).

The GUI is written using PySide2 (similar to PyQT5) and makes use of commands defined in the CLI.

![Screenshot of the GUI] (https://github.com/HenkVanAsselt/esp32_micropython_gui/blob/master/doc/images/gui_main_window.png)

![Screenshot of the CLI] (https://github.com/HenkVanAsselt/esp32_micropython_gui/blob/master/doc/images/cli_example.png)


