"""Determine the available communication ports (serial and/or usb serial)
"""

# Global imports
import serial.tools.list_ports


def serial_ports(verbose=False, usb=True):
    """Lists serial port names.

    :param verbose: If True, print verbose port information
    :param usb: If True, only list USB to UART bridges (like the one on an ESP32)
    :returns: A list of the serial ports available on the system
    """

    portlist = []
    desclist = []

    ports = serial.tools.list_ports.comports()

    for port, desc, hwid in sorted(ports):
        if verbose:
            print(f"{port} {desc} {hwid}")
        if usb:     # If we should only return USB serial ports
            if "USB" in desc.upper():
                portlist.append(port)
                desclist.append(desc)
        # else:
        #     portlist.append(port)
    return portlist, desclist


if __name__ == "__main__":
    print(serial_ports(verbose=True, usb=True))
