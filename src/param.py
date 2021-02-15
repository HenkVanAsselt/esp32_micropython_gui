"""Parameters file"""

import configparser

# COMPORT = ""
# COMPORT_DESC = ""

MODE_COMMAND = 1
MODE_REPL = 2

# srcpath = Path('../upython_sources')        # @todo: Make this configurable

config = None

# ===============================================================================
if __name__ == "__main__":

    import esp32common

    config = esp32common.readconfig('esp32cli.ini')
    print(config.sections())
    p = config['src']['srcpath']
    print(p)
