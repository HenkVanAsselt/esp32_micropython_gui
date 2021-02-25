"""Parameters file"""

import configparser
import enum

# COMPORT = ""
# COMPORT_DESC = ""


# Note: Enum is not implemented in the live code yet
class Mode(enum.Enum):
    MODE_COMMAND = 1
    MODE_REPL = 2

MODE_COMMAND = 1
MODE_REPL = 2

config = configparser.ConfigParser()
config.read('esp32cli.ini')

# ===============================================================================
if __name__ == "__main__":

    import esp32common

    config = esp32common.readconfig('esp32cli.ini')
    print(config.sections())

    # Note: Enum is not implemented in the live code yet
    print(Mode.MODE_REPL)
    print(repr(Mode.MODE_REPL))
    print(Mode.MODE_REPL.name)
    print(Mode.MODE_REPL.value)
    print()
    for mode in Mode:
        print(mode)

