##
# @file get_serial_list.py
# @brief Lists serial port names

"""Lists serial port names.

    :raises ImportError: When pyserial is not installed.
    :return: A list of the serial ports available on the system
"""

import sys

try:
    import serial.tools.list_ports

    print([comport.device for comport in serial.tools.list_ports.comports()])

except ImportError:
    print("Pyserial is not installed for %s." % sys.executable)
    sys.exit(1)
