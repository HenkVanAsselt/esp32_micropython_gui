"""repl connection class.
Uses PyQt5 Serial port functionality
"""

# Default imports
import logging
logger = logging.getLogger(__name__)

# 3rd paty imports
from serial import Serial
from PyQt5.QtCore import QObject, pyqtSignal, QIODevice, QTimer
from PyQt5.QtSerialPort import QSerialPort

# Local imports
from lib.helper import debug, clear_debug_window

ENTER_RAW_MODE = b"\x01"  # CTRL-A
EXIT_RAW_MODE = b"\x02"  # CTRL-B
KEYBOARD_INTERRUPT = b"\x03"  # CTRL-C
SOFT_REBOOT = b"\x04"  # CTRL-C


# =============================================================================
class REPLConnection(QObject):

    serial = None
    data_received = pyqtSignal(bytes)
    connection_error = pyqtSignal(str)

    def __init__(self, port, baudrate=115200):
        debug("Initializing REPLConnection")
        super().__init__()
        self._port: str = port      # Example: "COM4"
        self._baudrate: int = baudrate
        self.is_connected: bool = False
        self.create_serial_port()

    def create_serial_port(self):
        self.serial = QSerialPort()
        self.serial.setPortName(self._port)
        self.serial.setBaudRate(self._baudrate)
        self.is_connected: bool = False

    @property
    def port(self):
        if self.serial:
            # perhaps return self.serial.portName()?
            return self._port
        else:
            return None

    @property
    def baudrate(self):
        if self.serial:
            # perhaps return self.serial.baudRate()
            return self._baudrate
        else:
            return None

    def open(self):
        """
        Open the serial link
        """

        # debug("REPLConnection open()")
        debug("Connecting to REPL on port: {}".format(self.port))

        if not self.serial:
            self.create_serial_port()
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

        debug(f"Connected to {self.port}")
        logger.info("Connected to REPL on port: {}".format(self.port))
        self.is_connected = True

    def close(self) -> None:
        """Close and clean up the currently open serial link.
        :returns: Nothing
        """
        logger.info("Closing connection to REPL on port: {}".format(self.port))
        if self.serial:
            self.serial.close()
            self.serial = None
            self.is_connected = False

    def _on_serial_read(self) -> None:
        """
        Called when data is ready to be send from the device
        """
        data = bytes(self.serial.readAll())
        debug(f"_on_serial_read() Received {data=}")
        self.data_received.emit(data)

    def read(self) -> bytes:
        data = bytes(self.serial.readAll())
        debug(f"read() Received {data=}")
        return data

    def write(self, data: bytes) -> None:
        debug(f"Serial write {data=}")
        self.serial.write(data)

    def send_interrupt(self) -> None:
        """Send interrupt sequence to connected devce.
        This contains CTRL+B (exit raw mode) and CTRL+C (interrupt running process).
        :returns: Nothing
        """
        debug("ReplConnection send_interrupt()")
        self.write(EXIT_RAW_MODE)  # CTRL-B
        self.write(KEYBOARD_INTERRUPT)  # CTRL-C

    def execute(self, commands: list) -> None:
        """Execute a series of commands over a period of time (scheduling
        remaining commands to be run in the next iteration of the event loop).
        :returns: Nothing
        """
        debug(f"execute {commands=}")
        if commands:
            command = commands[0]
            logger.info("Sending command {}".format(command))
            self.write(command)
            remainder = commands[1:]
            remaining_task = lambda commands=remainder: self.execute(commands)
            QTimer.singleShot(2, remaining_task)

    def send_commands(self, commands) -> None:
        """Send commands to the REPL via raw mode.
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

    connection = REPLConnection('COM4', 115200)
    connection.open()
    connection.send_interrupt()
    print(connection.read())

    # connection.send_commands(["import os", "os.listdir()"])
    # print(connection.read())