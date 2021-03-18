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
    debug(f"Set sourcefolder to {foldername}")
    saveconfig(param.config)
    return True


# -----------------------------------------------------------------------------
def get_sourcefolder() -> pathlib.Path:
    """Get micropython sourcefolder from the configuration.

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
    """Run a local command, for example to start the editor.

    This function will only run the command, it does not return stdout and/or stderr

    :param cmdstr: The command to execute.
    :returns: True in case of a normal termination of the command, False in case of an error.
    """

    try:
        retcode = subprocess.call(cmdstr, shell=False)
        if retcode < 0:
            debug(f"Child was terminated by signal -{retcode}")
            return True
        debug(f"Child returned {retcode=}")
        return True
    except OSError as error:
        debug(f"Execution failed: {error=}")
        print("Execution failed:", error, file=sys.stderr)
        return False


# -----------------------------------------------------------------------------
@dumpArgs
def local_exec(command_list) -> tuple:
    """"Run a local command, for example to start the editor.

    This function will also return the stdout and stderr results.

    :param command_list: List of commands
    :returns: tuple of stdout and stderr results

    """

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    debug(f"{out=}")
    debug(f"{err=}")
    if out:
        print(out.decode())
    if err:
        print(err.decode())

    return out, err


# ===============================================================================
if __name__ == "__main__":

    # Read configuration
    cfg = readconfig('esp32cli.ini')
    param.config = cfg

    clear_debug_window()
    print(get_available_serial_ports(verbose=True, usb=True))
