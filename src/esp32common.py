"""ESP32 common tools. This module is used by esp32gui and esp32cli to perform tasks.
"""

# Global imports
import sys
import subprocess
import pathlib
import configparser
import os
import platform
import shlex
import time

# 3rd party imports
import serial.tools.list_ports  # type: ignore
import keyboard

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
def run_program(cmdstr) -> bool:
    """Run a local application, for example an editor.

    This function will only run the application, it does not return stdout and/or stderr

    In case you want to run a text based application, use execute_command() instead.

    :param cmdstr: The application to run.
    :returns: True in case of a normal termination of the application, False in case of an error.
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
def execute_command(command) -> tuple:
    """"Run a text based command on this PC.

    This function will not only show the stdout and stderr realtime (thus not
    waiting till the command is completely finished, but will also return the
    stdout and stderr output to the calling function.

    In case of a non-text based application, use run_program() instead.

    :param command: Command string or list of commands
    :returns: tuple of stdout and stderr results

    """

    # The commands can be given as a string or a list of strings.
    # In case it is not a list, split the line in substrings.
    command_list: list = []
    if isinstance(command, str):
        command_list = shlex.split(command)
    elif isinstance(command, list):
        command_list = command

    # Based on
    # https://stackoverflow.com/questions/22636420/python-subprocess-command-to-run-silent-prevent-cmd-from-appearing
    # Try to 'hide' the CMD window when ADB starts
    startupinfo = None
    if platform.system() == "Windows" or os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute the command, and print and capture the output
    with subprocess.Popen(
        command_list, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False
    ) as proc:

        total_std_output: bytes = b""
        total_err_output: bytes = b""

        while True:

            err_output = b''
            std_output = proc.stdout.read(1)

            if not std_output:
                err_output = proc.stderr.read(1)

            if not std_output and not err_output and proc.poll() is not None:
                break

            if std_output:
                # Print the output, but also append it to the total output bytestring
                print(std_output.decode(), end="", flush=True)
                total_std_output += std_output

            if err_output:
                # Print the error, but also append it to the total error bytestring
                print(err_output.decode(), end="", flush=True)
                total_err_output += err_output

        proc.poll()

    # Return the tuple of stdout and errout results.
    return total_std_output, total_err_output


# -----------------------------------------------------------------------------
def putty(port) -> tuple:
    """Run putty.exe with the given arguments

    :param port: Com port to use (string)
    :returns: tuple of stdout and stderr text
    """

    command_list = ["putty", "-serial", port, "-sercfg", "115200,8,n,1,N"]
    debug(f"Calling {' '.join(command_list)}")

    with subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as proc:

        # Wait some time, and then send Ctrl+b to exit raw repl (just to be sure).
        # We then should see the prompt:
        # MicroPython v1.14 on 2021-02-02; ESP32 module with ESP32
        # Type "help()" for more information.
        time.sleep(0.2)
        keyboard.press_and_release('ctrl+b')

        out, err = proc.communicate(input=b"\r\n")

    return out.decode(), err.decode()


# ===============================================================================
if __name__ == "__main__":

    # Read configuration
    cfg = readconfig('esp32cli.ini')
    param.config = cfg

    clear_debug_window()
    print(get_available_serial_ports(verbose=True, usb=True))
