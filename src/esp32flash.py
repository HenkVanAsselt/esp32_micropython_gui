"""ESP32 flash related functions
* eraseflash
* flash with binfile
"""

# default imports
import sys
import pathlib
import argparse

# local imports
import param
import esp32common
from lib.helper import debug

# 3rd party imports
from PyQt5.Qt import QEventLoop, QTimer


def find_esptool():
    """ Find esptool.exe and return the full path

    :return: Full path to esptool.exe
    """

    # Check if we can find the esptool executable
    esptool = pathlib.Path("../bin/esptool.exe")
    if not esptool.is_file():
        print(f"Error: Could not find {str(esptool)}")
        return ""
    return esptool

# -----------------------------------------------------------------------------
def erase_flash(comport="COM5") -> bool:
    """Erase flash memory of the connected ESP32.

    :param comport: The name of the comport to use
    :returns: True on success, False in case of an error
    """

    esptool = find_esptool()
    if not esptool:
        return False

    if comport.endswith(":"):
        comport = comport[:-1]

    print(f"Trying to erase flash over {comport=}")
    cmdstr = f'"{esptool}" --chip esp32 --port {comport} erase_flash'
    debug(f"Running {cmdstr}")
    if param.is_gui:
        try:
            param.worker.run_command(cmdstr)
            while param.worker.active:
                # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
                loop = QEventLoop()
                QTimer.singleShot(250, loop.quit)
                loop.exec_()
        except Exception as err:
            print(err)
            return False

    # else:
    out, err = esp32common.execute_command(cmdstr)
    debug(f"eraseflash {out=} {err=}")

    if b"fatal error" in out.lower() or b"invalid head of packet" in out.lower():
        return False
    return True


# -----------------------------------------------------------------------------
def write_flash_with_binfile(comport="COM5", binfile=None) -> bool:
    """Write flash of connected device with given binfile.

    :param comport: port to use
    :param binfile: file to write
    :returns: True on success, False in case of an error
    """

    # Remove a possible trailing colon
    if comport.endswith(":"):
        comport = comport[:-1]

    # Check if we can find the esptool executable
    esptool = find_esptool()
    if not esptool:
        return False

    # Test if the given binfile acutally exists
    if not pathlib.Path(binfile).is_file():
        print(f"Error: Could not find {binfile}")
        return False

    print(f"Trying to write flash with {binfile}")
    cmdstr = f'"{esptool}" --chip esp32 --port {comport} --baud 460800 write_flash -z 0x1000 "{binfile}"'
    debug(f"{cmdstr=}")

    if param.is_gui:
        param.worker.run_command(cmdstr)
        while param.worker.active:
            # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
            loop = QEventLoop()
            QTimer.singleShot(250, loop.quit)
            loop.exec_()
        return True

    # If we are here, then this was not the gui version, and have to run
    # this external command in a different way
    out, err = esp32common.execute_command(cmdstr)
    debug(f"write_flash_with_binfile {out=} {err=}")
    if b"fatal error" in out.lower() or b"invalid head of packet" in out.lower():
        return False
    return True


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    param.is_gui = False    # We are in a CLI application.

    parser = argparse.ArgumentParser(description='ESP32 erase and program flash with Micropython')
    parser.add_argument('-e', '--erase', action="store_true", help="erase flash")
    parser.add_argument('-p', '--port', type=str, default="auto", help="COM port to use, 'auto' will find active COM port")
    parser.add_argument('-f', '--file', type=str, default="", help="Micropython binfile to flash")
    args = parser.parse_args()

    # Determine if a specific COM port was specified, or if the active port
    # needs to be determined.
    if args.port == 'auto':
        port = esp32common.get_active_comport()[0]
    else:
        port = args.port

    # Remove a possible trailing colon
    if port.endswith(":"):
        port = port[:-1]

    # Do we want to erase the flash memory before reprogramming?
    # Commonly, that will be the case
    if args.erase:
        success = erase_flash(comport=port)
        if not success:
            sys.exit(-1)

    # If a filename was given, program the device with this file.
    if args.file:
        success = write_flash_with_binfile(comport=port, binfile=args.file)
        if not success:
            sys.exit(1)
