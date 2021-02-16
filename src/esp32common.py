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
def get_comport() -> tuple:
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
def ampy(*args) -> tuple:
    """Run an ampy.exe command with the given arguments

    :param args: Variable length of arguments
    :returns: tuple of stdout and stderr text
    """

    port = param.config["com"]["port"]
    command_list = ["ampy", "-p", port]
    for arg in args:
        command_list.append(arg)

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
def shell49(*args) -> tuple:
    """Run an shell49.exe command with the given arguments

    :param args: Variable length of arguments
    :returns: tuple of stdout and stderr text
    """

    command_list = ["shell49"]
    for arg in args:
        command_list.append(arg)
    debug(f"{command_list=}")

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
@dumpArgs
def put(srcfile: str, targetfile: str) -> tuple:
    """

    :param srcfile: path to sourcefile
    :param targetfile: path to target
    :return: tuple of return stdout and stderr messages
    """

    # Check if sourcefile can be found
    source = pathlib.Path(srcfile)
    if not source.is_file():
        out = ""
        err = f"Could not find {source}"
        debug(f"{out=}, {err=}")
        return out, err

    # Use Adafruit's ampy put command
    out, err = ampy("put", source, targetfile)
    if not err:
        out = f"Copied {source} to device as {targetfile}"

    debug(f"{out=}, {err=}")
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def get(srcfile, targetfile) -> tuple:
    """Get a file from the connected device. Makes use of ampy

    :param srcfile: path to sourcefile (on the device)
    :param targetfile: path to targetfile (on the PC)
    :return: tuple of stdout and stderr messages
    """

    # Add the path to uPython sources
    target = pathlib.Path(targetfile)

    # Use Adafruit's ampy get command
    out, err = ampy("get", srcfile, target)

    if not err:
        out = f"Copied \"{srcfile}\" from device to \"{target}\""
    else:
        print("Error in copying {srcfile}")
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def reset() -> tuple:
    """Soft reset the connected device.

    :return: tuple of stdout and stderr messages
    """
    print("Resetting connected device")
    out, err = ampy("reset")
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def ls() -> tuple:
    """Show the files/folders on the connected device

    :return: tuple of stdout and stderr messages
    """
    out, err = ampy("ls", "-l")
    print("Files and folders on connected device:")
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def listdir() -> list:
    """Get a list of files from the connected device

    :return: list of filenames
    """
    out, err = ampy("ls")
    if err:
        print(f"ERROR: {err}")
        return []

    ret_list = out.split()
    debug(f"listdir() {ret_list=}")
    return ret_list


# -----------------------------------------------------------------------------
@dumpArgs
def remote_run(targetfile) -> tuple:
    """Run the given file on the connected device.

    :param targetfile: The file to run
    :return: tuple of stdout and stderr messages

    Note: The file must already exist
    """
    print(f"Start runing {targetfile}")
    out, err = ampy("run", targetfile)
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def rm(targetfile) -> tuple:
    """Remove/Delete the given file from the connected device

    :param targetfile: The file to remove
    :return: tuple of stdout and stderr messages
    """
    print(f"Removing {targetfile}")
    out, err = ampy("rm", targetfile)
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def mkdir(targetfolder) -> tuple:
    """Create the given folder/directory on the connected device

    :param targetfolder: The folder to create
    :return: tuple of stdout and stderr messages
    """

    print(f"Creating folder {targetfolder}")
    out, err = ampy("mkdir", targetfolder)
    return out, err


# -----------------------------------------------------------------------------
@dumpArgs
def rmdir(targetfolder) -> tuple:
    """Remove a folder from the remote device.

    :param targetfolder: Foldr to remove
    :return: tuple of output and error messages
    """

    print(f"Removing folder {targetfolder}")
    out, err = ampy("rmdir", targetfolder)
    return out, err


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
    listdir()
