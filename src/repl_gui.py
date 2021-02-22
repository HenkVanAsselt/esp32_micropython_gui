"""Micropython REPL GUI, based on MU-Editor
"""

"""
Contains the UI classes used to populate the various panes used by Mu.

Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import platform
import codecs
import re

import logging
logger = logging.getLogger(__name__)

# from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QIODevice, QTimer
from PyQt5.QtGui import QKeySequence, QTextCursor, QCursor
from PyQt5.QtWidgets import QTextEdit, QMenu, QApplication, QMainWindow
from PyQt5.QtSerialPort import QSerialPort

from lib.helper import clear_debug_window, debug, dumpArgs

from serial import Serial

PANE_ZOOM_SIZES = {
    "xs": 8,
    "s": 10,
    "m": 14,
    "l": 16,
    "xl": 18,
    "xxl": 24,
    "xxxl": 28,
}

# The default font size.
DEFAULT_FONT_SIZE = 14
# All editor windows use the same font
FONT_NAME = "Source Code Pro"

VT100_RETURN = b"\r"
VT100_BACKSPACE = b"\b"
VT100_DELETE = b"\x1B[\x33\x7E"
VT100_UP = b"\x1B[A"
VT100_DOWN = b"\x1B[B"
VT100_RIGHT = b"\x1B[C"
VT100_LEFT = b"\x1B[D"
VT100_HOME = b"\x1B[H"
VT100_END = b"\x1B[F"

ENTER_RAW_MODE = b"\x01"  # CTRL-A
EXIT_RAW_MODE = b"\x02"  # CTRL-B
KEYBOARD_INTERRUPT = b"\x03"  # CTRL-C
SOFT_REBOOT = b"\x04"  # CTRL-C


class MicroPythonREPLPane(QTextEdit):
    """
    REPL = Read, Evaluate, Print, Loop.

    This widget represents a REPL client connected to a device running
    MicroPython.

    The device MUST be flashed with MicroPython for this to work.
    """

    def __init__(self, parent):
        debug("intializing MircopythonREPLPane.")
        super().__init__(parent)
        self.connection = None
        # self.setFont(Font().load())       # todo: reimplement this
        self.setAcceptRichText(False)
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        # self.setContextMenuPolicy(Qt.CustomContextMenu)   # todo: reimplement this
        self.customContextMenuRequested.connect(self.context_menu)
        # The following variable maintains the position where we know
        # the device cursor is placed. It is initialized to the beginning
        # of the QTextEdit (i.e. equal to the Qt cursor position)
        self.device_cursor_position = self.textCursor().position()
        self.setObjectName("ReplPane")
        self.unprocessed_input = b""  # used by process_bytes
        self.decoder = codecs.getincrementaldecoder("utf8")("replace")
        self.vt100_regex = re.compile(
            r"\x1B\[(?P<count>[\d]*)(;?[\d]*)*(?P<action>[A-Za-z])"
        )

    def set_connection(self, connection):
        if connection:
            self.connection = connection

    def paste(self):
        """
        Grabs clipboard contents then sends to the REPL.
        """
        clipboard = QApplication.clipboard()
        if clipboard and clipboard.text():
            to_paste = (
                clipboard.text().replace("\n", "\r").replace("\r\r", "\r")
            )
            if self.connection:
                self.connection.write(bytes(to_paste, "utf8"))
            else:
                debug("WARNING: in paste(): No connection was established yet")

    def context_menu(self) -> None:
        """Creates custom context menu with just copy and paste.
        :returns: Nothing
        """
        menu = QMenu(self)
        if platform.system() == "Darwin":
            copy_keys = QKeySequence(Qt.CTRL + Qt.Key_C)
            paste_keys = QKeySequence(Qt.CTRL + Qt.Key_V)
        else:
            copy_keys = QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_C)
            paste_keys = QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_V)

        menu.addAction("Copy", self.copy, copy_keys)
        menu.addAction("Paste", self.paste, paste_keys)
        menu.exec_(QCursor.pos())

    def set_theme(self, theme):
        """Set Theme. Does not do anything right now.
        """
        pass

    def send(self, msg):
        if self.connection:
            self.connection.write(msg)
        else:
            debug("WARINING: In send(): No connection was established yet")

    @dumpArgs
    def keyPressEvent(self, data):
        """
        Called when the user types something in the REPL.

        Correctly encodes it and sends it to the connected device.
        """
        tc = self.textCursor()
        key = data.key()
        ctrl_only = data.modifiers() == Qt.ControlModifier
        meta_only = data.modifiers() == Qt.MetaModifier
        ctrl_shift_only = (
            data.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
        )
        shift_down = data.modifiers() & Qt.ShiftModifier
        on_osx = platform.system() == "Darwin"

        debug(f"{key=}")
        if key == Qt.Key_Return:
            # Move cursor to the end of document before sending carriage return
            tc.movePosition(QTextCursor.End, mode=QTextCursor.MoveAnchor)
            self.device_cursor_position = tc.position()
            self.send(VT100_RETURN)
        elif key == Qt.Key_Backspace:
            if not self.delete_selection():
                self.send(VT100_BACKSPACE)
        elif key == Qt.Key_Delete:
            if not self.delete_selection():
                self.send(VT100_DELETE)
        elif key == Qt.Key_Up:
            self.send(VT100_UP)
        elif key == Qt.Key_Down:
            self.send(VT100_DOWN)
        elif key == Qt.Key_Right:
            if shift_down:
                # Text selection - pass down
                super().keyPressEvent(data)
            elif tc.hasSelection():
                self.move_cursor_to(tc.selectionEnd())
            else:
                self.send(VT100_RIGHT)
        elif key == Qt.Key_Left:
            if shift_down:
                # Text selection - pass down
                super().keyPressEvent(data)
            elif tc.hasSelection():
                self.move_cursor_to(tc.selectionStart())
            else:
                self.send(VT100_LEFT)
        elif key == Qt.Key_Home:
            self.send(VT100_HOME)
        elif key == Qt.Key_End:
            self.send(VT100_END)
        elif (on_osx and meta_only) or (not on_osx and ctrl_only):
            # Handle the Control key. On OSX/macOS/Darwin (python calls this
            # platform Darwin), this is handled by Qt.MetaModifier. Other
            # platforms (Linux, Windows) call this Qt.ControlModifier. Go
            # figure. See http://doc.qt.io/qt-5/qt.html#KeyboardModifier-enum
            if Qt.Key_A <= key <= Qt.Key_Z:
                # The microbit treats an input of \x01 as Ctrl+A, etc.
                self.send(bytes([1 + key - Qt.Key_A]))
        elif ctrl_shift_only or (on_osx and ctrl_only):
            # Command-key on Mac, Ctrl-Shift on Win/Lin
            if key == Qt.Key_C:
                self.copy()
            elif key == Qt.Key_V:
                self.delete_selection()
                self.paste()
        else:
            self.delete_selection()
            debug(f"Sending {data.text()=}")
            self.send(bytes(data.text(), "utf8"))

    def set_qtcursor_to_devicecursor(self):
        """
        Resets the Qt TextCursor to where we know the device has the cursor
        placed.
        """
        tc = self.textCursor()
        tc.setPosition(self.device_cursor_position)
        self.setTextCursor(tc)

    def set_devicecursor_to_qtcursor(self):
        """
        Call this whenever the cursor has been moved by the user, to send
        the cursor movement to the device.
        """
        self.move_cursor_to(self.textCursor().position())

    def move_cursor_to(self, new_position):
        """Move the cursor, by sending vt100 left/right signals through
        serial. The Qt cursor is first returned to the known location
        of the device cursor.  Then the appropriate number of move
        left or right signals are send.  The Qt cursor is not moved to
        the new_position here, but will be moved once receiving a
        response (in process_tty_data).
        """
        # Reset Qt cursor position
        self.set_qtcursor_to_devicecursor()
        # Calculate number of steps
        steps = new_position - self.device_cursor_position
        # Send the appropriate right/left moves
        if steps > 0:
            # Move cursor right if positive
            self.send(VT100_RIGHT * steps)
        elif steps < 0:
            # Move cursor left if negative
            self.send(VT100_LEFT * abs(steps))

    def delete_selection(self):
        """
        Returns true if deletion happened, returns false if there was no
        selection to delete.
        """
        tc = self.textCursor()
        if tc.hasSelection():
            # Calculate how much should be deleted (N)
            selection_size = tc.selectionEnd() - tc.selectionStart()
            # Move cursor to end of selection
            self.move_cursor_to(tc.selectionEnd())
            # Send N backspaces
            self.send(VT100_BACKSPACE * selection_size)
            return True
        return False

    def mouseReleaseEvent(self, mouse_event):
        """Called whenever a user have had a mouse button pressed, and
        releases it. We pass it through to the normal way Qt handles
        button pressed, but also sends as cursor movement signal to
        the device (except if a selection is made, for selections we first
        move the cursor on deselection)
        """
        super().mouseReleaseEvent(mouse_event)

        # If when a user have clicked and not made a selection
        # move the device cursor to where the user clicked
        if not self.textCursor().hasSelection():
            self.set_devicecursor_to_qtcursor()

    def process_tty_data(self, data: bytes) -> None:
        """
        Given some incoming bytes of data, work out how to handle / display
        them in the REPL widget.
        If received input is incomplete, stores remainder in
        self.unprocessed_input.

        Updates the self.device_cursor_position to match that of the device
        for every input received.
        """
        i = 0
        data = self.decoder.decode(data)
        if len(self.unprocessed_input) > 0:
            # Prepend bytes from last time, that wasn't processed
            data = self.unprocessed_input + data
            self.unprocessed_input = ""

        # Reset cursor. E.g. if doing a selection, the qt cursor and
        # device cursor will not match, we reset it here to make sure
        # they do match (this removes any selections when new input is
        # received)
        self.set_qtcursor_to_devicecursor()
        tc = self.textCursor()

        while i < len(data):
            if data[i] == "\b":
                tc.movePosition(QTextCursor.Left)
                self.device_cursor_position = tc.position()
            elif data[i] == "\r":
                # Carriage return. Do nothing, we handle newlines when
                # reading \n
                pass
            elif data[i] == "\x1b":
                # Escape
                if len(data) > i + 1 and data[i + 1] == "[":
                    # VT100 cursor detected: <Esc>[
                    match = self.vt100_regex.search(data[i:])
                    if match:
                        # move to (almost) after control seq
                        # (will ++ at end of loop)
                        i += match.end() - 1
                        count_string = match.group("count")
                        count = 1 if count_string == "" else int(count_string)
                        action = match.group("action")
                        if action == "A":  # up
                            tc.movePosition(QTextCursor.Up, n=count)
                            self.device_cursor_position = tc.position()
                        elif action == "B":  # down
                            tc.movePosition(QTextCursor.Down, n=count)
                            self.device_cursor_position = tc.position()
                        elif action == "C":  # right
                            tc.movePosition(QTextCursor.Right, n=count)
                            self.device_cursor_position = tc.position()
                        elif action == "D":  # left
                            tc.movePosition(QTextCursor.Left, n=count)
                            self.device_cursor_position = tc.position()
                        elif action == "K":  # delete things
                            if count_string == "":  # delete to end of line
                                tc.movePosition(
                                    QTextCursor.EndOfLine,
                                    mode=QTextCursor.KeepAnchor,
                                )
                                tc.removeSelectedText()
                                self.device_cursor_position = tc.position()
                        else:
                            # Unknown action, log warning and ignore
                            command = match.group(0).replace("\x1B", "<Esc>")
                            msg = "Received unsupported VT100 command: {}"
                            logger.warning(msg.format(command))
                    else:
                        # Cursor detected, but no match, must be
                        # incomplete input
                        self.unprocessed_input = data[i:]
                        break
                elif len(data) == i + 1:
                    # Escape received as end of transmission. Perhaps
                    # the transmission is incomplete, wait until next
                    # bytes are received to determine what to do
                    self.unprocessed_input = data[i:]
                    break
            elif data[i] == "\n":
                tc.movePosition(QTextCursor.End)
                self.device_cursor_position = tc.position() + 1
                self.setTextCursor(tc)
                self.insertPlainText(data[i])
            else:
                # Char received, with VT100 that should be interpreted
                # as overwrite the char in front of the cursor
                tc.deleteChar()
                self.device_cursor_position = tc.position() + 1
                self.insertPlainText(data[i])
            self.setTextCursor(tc)
            i += 1
        # Scroll textarea if necessary to see cursor
        self.ensureCursorVisible()

    def clear(self):
        """
        Clears the text of the REPL.
        """
        self.setText("")

    def set_font_size(self, new_size=DEFAULT_FONT_SIZE):
        """
        Sets the font size for all the textual elements in this pane.
        """
        font = self.font()
        font.setPointSize(new_size)
        self.setFont(font)

    def set_zoom(self, size):
        """
        Set the current zoom level given the "t-shirt" size.
        """
        self.set_font_size(PANE_ZOOM_SIZES[size])


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

        debug("REPLConnection open()")
        logger.info("Connecting to REPL on port: {}".format(self.port))

        if not self.serial:
            self.create_serial_port()
            debug("Created new instance of QSerialPort")

        if not self.serial.open(QIODevice.ReadWrite):
            msg = "Cannot connect to device on port {}".format(self.port)
            debug(msg)
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
        debug(f"Received {data=}")
        self.data_received.emit(data)

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

        newline = [b'print("\\n");']
        commands = [c.encode("utf-8") + b"\r" for c in commands]
        commands.append(b"\r")
        commands.append(SOFT_REBOOT)
        raw_off = [EXIT_RAW_MODE]
        command_sequence = raw_on + newline + commands + raw_off
        logger.info(command_sequence)
        self.execute(command_sequence)


class Demo(QMainWindow):
    def __init__(self):
        super(Demo, self).__init__()
        x, y, w, h = 500, 200, 300, 400
        self.setGeometry(x, y, w, h)

        connection = REPLConnection('COM4', 115200)
        repl_pane = MicroPythonREPLPane(parent=None)
        self.setCentralWidget(repl_pane)
        repl_pane.connection = connection
        connection.open()
        connection.send_interrupt()
        connection.data_received.connect(repl_pane.process_tty_data)


    def show_and_raise(self) -> None:
        self.show()
        self.raise_()


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    clear_debug_window()

    app = QApplication(sys.argv)

    demo = Demo()
    demo.show_and_raise()

    sys.exit(app.exec_())
