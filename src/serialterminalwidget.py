"""PySide2 Serial Terminal widget
"""

# Source: https://iosoft.blog/2019/04/30/pyqt-serial-terminal/

import queue
import sys
import time
import serial


from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QTextEdit, QWidget, QApplication, QVBoxLayout

from lib.helper import debug, clear_debug_window
from lib.decorators import dumpFuncname, dumpArgs

VERSION = "v0.09"

WIN_WIDTH, WIN_HEIGHT = 684, 400  # Window size
SER_TIMEOUT = 0.1  # Timeout for serial Rx
RETURN_CHAR = "\r"  # Char to be sent when Enter key pressed
PASTE_CHAR = "\x16"  # Ctrl code for clipboard paste
baudrate = 115200  # Default baud rate
portname = "COM5"  # Default port name
hexmode = False  # Flag to enable hex display


def str_bytes(s):
    """Convert a string to bytes.
    """
    return s.encode('latin-1')


def bytes_str(d):
    """ Convert bytes to string
    """
    return d if type(d) is str else "".join([chr(b) for b in d])


def hexdump(data):
    """Return hexadecimal values of data.

    :param data: Hexadecimal values
    :return: String of hexadecimal representation
    """
    return " ".join(["%02X" % ord(b) for b in data])


def textdump(data):
    """Return a string with high-bit chars replaced by hex values.

    :param data:
    :return:
    """
    return "".join(["[%02X]" % ord(b) if b > '\x7e' else b for b in data])


def display(s):
    """Display incoming serial data.

    :param s:
    :return:
    """

    if not hexmode:
        sys.stdout.write(textdump(str(s)))
    else:
        sys.stdout.write(hexdump(s) + ' ')


class TerminalTextBox(QTextEdit):
    """ Custom text box, catching keystrokes.
    """

    def __init__(self, *args):
        QTextEdit.__init__(self, *args)

    def keyPressEvent(self, event):  # Send keypress to parent's handler
        self.parent().keypress_handler(event)


class SerialTerminalWidget(QWidget):
    """Main Widget.
    """

    # text_update = QtCore.pyqtSignal(str)  # QT5
    text_update = QtCore.Signal(str)        # PySide2

    def __init__(self, *args):
        """Initialize the serial terminal widget
        """
        QWidget.__init__(self, *args)
        self.textbox = TerminalTextBox()    # Create custom text box
        font = QtGui.QFont()
        font.setFamily("Courier New")       # Monospaced font
        font.setPointSize(10)
        self.textbox.setFont(font)
        layout = QVBoxLayout()
        layout.addWidget(self.textbox)
        self.setLayout(layout)
        self.resize(WIN_WIDTH, WIN_HEIGHT)                  # Set window size

        self.serth = SerialThread(portname, baudrate)       # Define the serial thread

        self.text_update.connect(self.append_text)  # noqa  # Connect text update to handler
        self.org_stdout = sys.stdout                        # Save the original stdout handler

    @dumpArgs
    def mousePressEvent(self, event):
        """Start the thread when a right-mouseclick is happening in this window
        """
        debug("Starting repl (2)")
        self.serth.start()
        debug("Repl started (2)")

    @dumpArgs
    def write(self, text):
        """Handle sys.stdout.write: update display

        :param text: Text to display in the terminal window
        :return: Nothing
        """
        self.text_update.emit(text)  # noqa  # Send signal to synchronise call with main thread

    def flush(self):
        """Handle sys.stdout.flush: do nothing

        :return: Nothing
        """
        pass

    @staticmethod
    def isatty():
        """ to check if the given file descriptor is open and connected to tty(-like) device or not

        :return: True
        """
        return False

    @staticmethod
    def fileno():
        """Return -1 as the fileno, to satisfy cmd2 redirection.
        """
        return -1

    def append_text(self, text):
        """Text display update handler.

        :param text: Text to display
        :return: Nothing
        """

        # debug(f"Append text \"{text=}\"")
        cur = self.textbox.textCursor()
        cur.movePosition(QtGui.QTextCursor.End)  # Move cursor to end of text
        s = str(text)
        while s:
            head, sep, s = s.partition("\n")  # Split line at LF
            head = head.replace("\r", "")     # Remove the Carriage Returns to avoid double linespacing.
            cur.insertText(head)  # Insert text at cursor
            if sep:  # New line if LF
                cur.insertBlock()
        self.textbox.setTextCursor(cur)  # Update visible cursor

    def keypress_handler(self, event):  # Handle keypress from text box
        if not self.serth.running:
            self.append_text('REPL is not active, Serial thread is not running\n')
            return

        k = event.key()
        if k == QtCore.Qt.Key_Escape:
            s = 'ESC has been pressed, terminating thread'
            debug(s)
            print(s)
            self.stop_repl()
            debug('End of thread, closing application')
            try:
                app.quit()      # And close this application if running standalone
            except NameError:
                pass
            return

        s = RETURN_CHAR if k == QtCore.Qt.Key_Return else event.text()
        if len(s) > 0 and s[0] == PASTE_CHAR:  # Detect ctrl-V paste
            # debug(f"Pasting {s=}")
            cb = QApplication.clipboard()
            self.serth.ser_out(cb.text())  # Send paste string to serial driver
        else:
            # debug(f'Sending {s=}')
            self.serth.ser_out(s)  # ..or send keystroke

    @dumpArgs
    def start_repl(self):
        debug(f"sys.stdout was {sys.stdout=}")
        sys.stdout = self                                   # Redirect sys.stdout to self
        self.serth.start()
        debug(f"now sys.stdout is {sys.stdout=}")

    @dumpArgs
    def stop_repl(self):
        self.serth.running = False      # Stop the serial thread
        self.serth.wait()               # Wait until serial thread terminates
        debug(f"sys.stdout was {sys.stdout=}")
        sys.stdout = self.org_stdout    # Restore stdout
        debug(f"now sys.stdout is {sys.stdout=}")

    @dumpArgs
    def closeEvent(self, event):  # Window closing
        self.stop_repl()


class SerialThread(QtCore.QThread):
    """Thread to handle incoming & outgoing serial data.
    """

    def __init__(self, portname, baudrate):
        """Initialise with serial port details.
        :param portname:
        :param baudrate:
        """

        QtCore.QThread.__init__(self)
        self.portname, self.baudrate = portname, baudrate
        self.txq = queue.Queue()
        self.running = False
        self.ser = None

    def ser_out(self, s):
        """Write outgoing data to serial port if open.
        :param s: The data to write
        :returns: Nothing
        """
        self.txq.put(s)  # ..using a queue to sync with reader thread

    def ser_in(self, s):
        """Write incoming serial data to screen.
        """
        display(s)

    @dumpFuncname
    def run(self):
        """Run serial reader thread.
        """

        try:
            debug("Opening %s at %u baud %s" % (self.portname, self.baudrate,
                                                "(hex display)" if hexmode else ""))
            print("Opening %s at %u baud %s" % (self.portname, self.baudrate,
                                                "(hex display)" if hexmode else ""))
            self.ser = serial.Serial(self.portname, self.baudrate, timeout=SER_TIMEOUT)
            time.sleep(SER_TIMEOUT * 1.2)
            self.ser.flushInput()
            self.ser.write(b'\r')    # Send a CR to show the repl prompt
        except Exception as e:
            debug(e)
            debug("Error in opening comport")
            self.ser = None
            time.sleep(0.1)
        if not self.ser:
            debug("Can't open port")
            print("Can't open port")
            self.running = False
        self.running = True
        while self.running:
            s = self.ser.read(self.ser.in_waiting or 1)
            if s:  # Get data from serial port
                debug(f'Getting data from serial port: {s=}')
                self.ser_in(bytes_str(s))  # ..and convert to string
            if not self.txq.empty():
                txd = str(self.txq.get())  # If Tx data in queue, write to serial port
                debug(f"Writing \"{txd}\" to serial port")
                self.ser.write(str_bytes(txd))
        if self.ser:  # Close serial port when thread finished
            self.ser.close()
            self.ser = None


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    clear_debug_window()

    app = QApplication(sys.argv)
    opt = err = None
    for arg in sys.argv[1:]:  # Process command-line options
        if len(arg) == 2 and arg[0] == "-":
            opt = arg.lower()
            if opt == '-x':  # -X: display incoming data in hex
                hexmode = True
                opt = None
        else:
            if opt == '-b':  # -B num: baud rate, e.g. '9600'
                try:
                    baudrate = int(arg)
                except ValueError:
                    err = "Invalid baudrate '%s'" % arg
            elif opt == '-c':  # -C port: serial port name, e.g. 'COM1'
                portname = arg
    if err:
        print(err)
        sys.exit(1)
    w = SerialTerminalWidget()
    w.setWindowTitle('PyQT Serial Terminal ' + VERSION)
    w.show()
    sys.exit(app.exec_())
