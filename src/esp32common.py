"""ESP32 common tools. This module is used by esp32gui and esp32cli to perform tasks.
"""

# Global imports
import sys
import subprocess
import pathlib
import configparser

# 3rd party imports
import serial.tools.list_ports  # type: ignore

# Local imports
import param
from lib.helper import debug, clear_debug_window, dumpArgs


# -----------------------------------------------------------------------------
def get_available_serial_ports(verbose=False, usb=True) -> tuple:
    """Lists serial port names.

    :param verbose: If True, print verbose port information
    :param usb: If True, only list USB to UART bridges (like on an ESP32)
    :returns: A list of the serial ports available on the system
    """

    portlist = []
    desclist = []

    ports = serial.tools.list_ports.comports()

    for port, desc, hwid in sorted(ports):
        if verbose:
            print(f"{port} {desc} {hwid}")
        if usb:  # If we should only return USB serial ports
            if "USB" in desc.upper():
                portlist.append(port)
                desclist.append(desc)
        # else:
        #     portlist.append(port)
    return portlist, desclist


# -----------------------------------------------------------------------------
def get_active_comport() -> tuple:
    """Determine active USB to Serial COM port.

    :return: tuple of COMport string and verbose description

    Example: ("COM5", "(Silicon Labs CP210x USB to UART Bridge (COM5)")
    """

    portlist, desclist = get_available_serial_ports(usb=True)
    if not portlist:
        err = "ERROR: Could not find an active COM port to the device\nIs any device connected?\n"
        debug(err)
        return "", err

    port = portlist[0]
    desc = desclist[0]
    debug(f"get_comport() returns {port=}, {desc=}")
    return port, desc


# -----------------------------------------------------------------------------
@dumpArgs
def readconfig(filename="esp32cli.ini"):
    """Read configuration from the given INI file

    :param filename: Name of the configuration file to read
    """

    config = configparser.ConfigParser()
    config.read(filename)
    return config


# -----------------------------------------------------------------------------
@dumpArgs
def saveconfig(config, filename="esp32cli.ini"):
    """Read configuration from the given file.

    :param config: configparser instance
    :param filename: The name to which to write the configuration in
    """

    with open(filename, "w") as configfile:
        config.write(configfile)
    debug(f"Saved config to {filename}")


# -----------------------------------------------------------------------------
@dumpArgs
def set_sourcefolder(folder) -> bool:
    """Set sourcefolder in configuration

    :param folder: Foldername of the folder to change
    :returns: True on success, False in case of an error
    """

    debug(f"{folder=}")
    foldername = pathlib.Path(folder).resolve()
    if not foldername.is_dir():
        print(f"Could not find folder {folder}")
        return False

    param.config['src']['srcpath'] = str(foldername)
    print(f"Changed sourcefolder to {foldername}")
    saveconfig(param.config)
    return True


# -----------------------------------------------------------------------------
def get_sourcefolder() -> pathlib.Path:
    """Get micropython sourcefolder.

    :returns: Path to sourcefolder
    """

    folder = pathlib.Path(param.config['src']['srcpath'])
    if folder.is_dir():
        return folder

    # Return an empyt folder by default
    return pathlib.Path("")


# -----------------------------------------------------------------------------
@dumpArgs
def local_run(cmdstr) -> bool:
    """Run a local command, for example to start the editor
    """

    try:
        retcode = subprocess.call(cmdstr, shell=False)
        if retcode < 0:
            # print("Child was terminated by signal", -retcode, file=sys.stderr)
            return True
        # print("Child returned", retcode, file=sys.stderr)
        return True
    except OSError as error:
        print("Execution failed:", error, file=sys.stderr)
        return False


# ===============================================================================
if __name__ == "__main__":

    # Read configuration
    cfg = readconfig('esp32cli.ini')
    param.config = cfg

    clear_debug_window()
    print(get_available_serial_ports(verbose=True, usb=True))
