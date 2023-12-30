"""Parameters file"""

import configparser

config = configparser.ConfigParser()
config.read('esp32cli.ini')

is_gui = False          # Meaning, the bare CLI is used. Will have to be set to true in GUI version
gui_mainwindow = None   # Save it, so it can be used by functions in the GUI.
worker = None

port_str = ''           # Port string, like "COM10", "COM4"

# ===============================================================================
if __name__ == "__main__":

    import esp32common

    config = esp32common.readconfig('esp32cli.ini')
    print(config.sections())
