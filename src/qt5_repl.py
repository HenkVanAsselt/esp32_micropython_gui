"""repl connection class, specifically to be used with PyQT5.

Uses PyQt5 Serial port functionality.
"""

# Default imports


# 3rd party imports
from serial import Serial
from PyQt5.QtCore import QObject, pyqtSignal, QIODevice, QTimer
from PyQt5.QtSerialPort import QSerialPort

# Local imports
from lib.helper import debug, clear_debug_window, dumpFuncname, dumpArgs

ENTER_RAW_MODE = b"\x01"  # CTRL-A
EXIT_RAW_MODE = b"\x02"  # CTRL-B
KEYBOARD_INTERRUPT = b"\x03"  # CTRL-C
SOFT_REBOOT = b"\x04"  # CTRL-C


# =============================================================================
class REPLConnection(QObject):
    """Class for the Micropython REPL connection.
    """

    serial = None
    data_received = pyqtSignal(bytes)
    connection_error = pyqtSignal(str)

    # -------------------------------------------------------------------------
    def __init__(self, port: str, baudrate: int = 115200):
        """Intialize this REPL connection class.

        :param port: Portname, e.g. COM4
        :param baudrate: The connection speed in bps.
        """

        debug("Initializing REPLConnection")
        super().__init__()
        self._port: str = port  # Example: "COM4"
        self._baudrate: int = baudrate
        self.is_connected: bool = False
        self.create_serial_port()

    # -------------------------------------------------------------------------
    @dumpFuncname
    def create_serial_port(self) -> QSerialPort:
        """Create the serial port
        """
        self.serial = QSerialPort()
        self.serial.setPortName(self._port)
        self.serial.setBaudRate(self._baudrate)
        self.is_connected: bool = False
        return self.serial

    # -------------------------------------------------------------------------
    @property
    def port(self):
        """Return the name of the port.
        """

        if self.serial:
            # perhaps return self.serial.portName()?
            return self._port

        # else:
        return None

    # -------------------------------------------------------------------------
    @property
    def baudrate(self):
        """Get the baudrate.
        :returns: Current baudrate or None if there was no serial connction defined.
        """
        if self.serial:
            # perhaps return self.serial.baudRate()
            return self._baudrate
        #else:
        return None

    # -------------------------------------------------------------------------
    @dumpFuncname
    def open(self) -> None:
        """Open the serial REPL link to the connected device.
        """

        # debug("REPLConnection open()")
        debug("Connecting to REPL on port: {}".format(self.port))

        if not self.serial:
            self.serial = self.create_serial_port()
            # debug("Created new instance of QSerialPort")

        if not self.serial.open(QIODevice.ReadWrite):
            msg = "Cannot connect to device on port {}".format(self.port)
            # debug(msg)
            raise IOError(msg)

        self.serial.setDataTerminalReady(True)
        if not self.serial.isDataTerminalReady():
            # Using pyserial as a 'hack' to open the port and set DTR
            # as QtSerial does not seem to work on some Windows :(
            # See issues #281 and #302 for details.
            self.serial.close()
            pyser = Serial(self.port)  # open serial port w/pyserial
            pyser.dtr = True
            pyser.close()
            self.serial.open(QIODevice.ReadWrite)
        self.serial.readyRead.connect(self._on_serial_read)

        debug("Connected to REPL on port: %s" % self.port)
        self.is_connected = True

    # -------------------------------------------------------------------------
    @dumpFuncname
    def close(self) -> None:
        """Close and clean up the currently open serial link.
        :returns: Nothing
        """

        debug(f"Closing repl connection. {self.port=} {self.serial=}")
        if self.serial:
            self.serial.close()
            self.serial.close()
            self.serial = None
            self.is_connected = False

    # -------------------------------------------------------------------------
    def _on_serial_read(self) -> None:
        """Called when data is ready to be send from the device.
        """
        data = bytes(self.serial.readAll())
        debug(f"_on_serial_read() Received {data=}")
        self.data_received.emit(data)

    # -------------------------------------------------------------------------
    def read(self) -> bytes:
        """Read the available bytes from the serial port.
        """
        data = bytes(self.serial.readAll())
        debug(f"read() Received {data=}")
        return data

    # -------------------------------------------------------------------------
    def write(self, data: bytes) -> None:
        """Write the given data to the serial port.
        :param data: data to write
        :returns: Nothing
        """
        debug(f"Serial write {data=}")
        self.serial.write(data)

    # -------------------------------------------------------------------------
    @dumpFuncname
    def send_interrupt(self) -> None:
        """Send interrupt sequence to connected devce.

        This contains CTRL+B (exit raw mode) and CTRL+C (interrupt running process).
        :returns: Nothing
        """

        self.write(EXIT_RAW_MODE)  # CTRL-B
        self.write(KEYBOARD_INTERRUPT)  # CTRL-C

    # -------------------------------------------------------------------------
    @dumpFuncname
    def send_exit_raw_mode(self) -> None:
        """Send interrupt sequence to connected devce.

        This contains CTRL+B (exit raw mode)
        :returns: Nothing
        """

        self.write(EXIT_RAW_MODE)  # CTRL-B

    # -------------------------------------------------------------------------
    @dumpArgs
    def execute(self, commands: list) -> None:
        """Execute a series of commands over a period of time.
         (scheduling remaining commands to be run in the next iteration of the event loop).
        :returns: Nothing
        """
        debug(f"execute {commands=}")
        if commands:
            command = commands[0]
            debug("Sending command %s" % command)
            self.write(command)
            remainder = commands[1:]
            remaining_task = lambda commands=remainder: self.execute(commands)
            QTimer.singleShot(2, remaining_task)

    # -------------------------------------------------------------------------
    @dumpArgs
    def send_commands(self, commands: list) -> None:
        """Send commands to the REPL via raw mode.
        :param commands: list of commands
        First will send a raw_on, then the commands, raw_off, followed by a soft reboot.
        :returns: Nothing
        """
        # Sequence of commands to get into raw mode (From pyboard.py).
        raw_on = [
            KEYBOARD_INTERRUPT,
            KEYBOARD_INTERRUPT,
            ENTER_RAW_MODE,
            SOFT_REBOOT,
            KEYBOARD_INTERRUPT,
            KEYBOARD_INTERRUPT,
        ]

        debug(f"send_commands {commands=}")

        newline = [b'print("\\n");']
        commands = [c.encode("utf-8") + b"\r" for c in commands]
        commands.append(b"\r")
        commands.append(SOFT_REBOOT)
        raw_off = [EXIT_RAW_MODE]
        command_sequence = raw_on + newline + commands + raw_off
        self.execute(command_sequence)


# ============================================================================
if __name__ == "__main__":

    clear_debug_window()

    connection = REPLConnection("COM4", 115200)
    connection.open()
    connection.send_interrupt()
    print(connection.read())

    # connection.send_commands(["import os", "os.listdir()"])
    # print(connection.read())
