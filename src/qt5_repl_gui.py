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
from qt5_repl import REPLConnection


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
        self.setAcceptRichText(False)
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
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

        # debug(f"{key=}")
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
            # debug(f"Sending {data.text()=}")
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
        i: int = 0
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
