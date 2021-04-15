"""Parameters file"""

import configparser
import enum

# COMPORT = ""
# COMPORT_DESC = ""


config = configparser.ConfigParser()
config.read('esp32cli.ini')

is_gui = False      # Meaning, bare CLI is used. Will be set to true in GUI version
gui_mainwindow = None   # Save it, so it can be used by the commands in the CLI
worker = None

# ===============================================================================
if __name__ == "__main__":

    import esp32common

    config = esp32common.readconfig('esp32cli.ini')
    print(config.sections())


