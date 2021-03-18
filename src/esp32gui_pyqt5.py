"""ESP32 GUI Shell (pyside2) main module"""

# Global imports
import sys
import subprocess

# 3rd party imports
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import pyqtSlot
from PyQt5.Qt import QEventLoop, QTimer

# Local imports
import param
from esp32shell_qt_design import Ui_MainWindow
from lib.helper import debug, clear_debug_window, dumpFuncname, dumpArgs
import esp32common
import esp32cli
import qt5_repl_gui

from worker import Worker

# constants

MODE_COMMAND = 1
MODE_REPL = 2

# REPL modes:
INTERNAL = 1
PUTTY = 2
MINITERM = 3


# -----------------------------------------------------------------------------
def putty(port) -> tuple:
    """Run putty.exe with the given arguments

    :param port: Com port to use (string)
    :returns: tuple of stdout and stderr text
    """

    command_list = ["putty", "-serial", port, "-sercfg", "115200,8,n,1,N"]
    debug(f"Calling {' '.join(command_list)}")

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate(input=b"\r\n")
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
def miniterm(port) -> tuple:
    """Run putty.exe with the given arguments

    :param port: Com port to use (string)
    :returns: tuple of stdout and stderr text

    20210218, HenkA: Does not work yet, does not react on CTRL+C or CTRL+D
    """

    command_list = ["pyserial-miniterm.exe", port, "115200"]
    debug(f"Calling {' '.join(command_list)}")

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate(input=b"\r\n")
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
def save_command_list(cmdlist: list, filename='gui_cmd_history.txt') -> bool:
    """Save list of commands entered in the GUI to a file.
    This makes it possible to reload it later.

    :param cmdlist: List of commands to save
    :param filename: Name of the file to save the commands to
    :returns: True on success, False in case of an error.
    """

    with open(filename, 'w') as f:
        for s in cmdlist:
            f.write(s + '\n')
    return True


# -----------------------------------------------------------------------------
def load_command_list(filename='gui_cmd_history.txt') -> list:
    """Load a list of commands previously entered.

    :param filename: Name of the file to load the commands from
    :returns: List of loaded commands.
    """

    with open(filename, 'r') as f:
        cmdlist = f.readlines()

    stripped_list = [cmd.strip() for cmd in cmdlist]
    return stripped_list


# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """QT Main Window"""

    # text_update = QtCore.Signal(str)        # PySide2
    text_update = QtCore.pyqtSignal(str)

    def __init__(self):
        """Intialize the QT window"""

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        param.worker = Worker()
        param.worker.outSignal.connect(self.append_text)

        # After a command is entered, and ENTER is pressed, react on it
        self.ui.command_input.returnPressed.connect(self.do_entered_command)

        # After a new sourcepath is entered (and ENTER is pressed), react on it
        self.ui.lineEdit_srcpath.returnPressed.connect(self.get_ui_properties)
        self.ui.lineEdit_webrepl_ip.returnPressed.connect(self.get_ui_properties)

        # Load the list of previous commands from the file in which they were saved.
        self.list_of_commands = list(set(load_command_list()))
        for cmd_str in self.list_of_commands:
            s = cmd_str.strip()
            if s:
                self.ui.commandlist.addItem(s)
        # If a command from the list of commands is clicked, execute it
        self.ui.commandlist.itemClicked.connect(self.do_clicked_command)

        # Handle the switch from repl mode to command mode and visa versa
        self.ui.radioButton_commandmode.clicked.connect(self.change_to_command_mode)
        self.ui.radioButton_replmode.clicked.connect(self.change_to_repl_mode)

        # Handle the buttonclick for webrepl mode
        self.ui.pushButton_webrepl.clicked.connect(self.webrepl)

        # Read configuration
        self.config = esp32common.readconfig("esp32cli.ini")
        param.config = self.config

        self.port, desc = esp32common.get_active_comport()
        self.config["com"]["port"] = self.port
        self.config["com"]["desc"] = desc
        debug(f"Possible active com port is {self.port}")

        # If neccessary, set properties of some elements
        self.set_ui_properties()

        self.mode = MODE_COMMAND  # Start in Command mode

        debug(f"sys.stdout was {sys.stdout=}")
        self.org_stdout = sys.stdout
        sys.stdout = self
        sys.stderr = self
        debug(f"now sys.stdout is {sys.stdout=}")
        self.text_update.connect(
            self.append_text
        )  # noqa # Connect text update to handler
        self.ui.command_input.setFocus()

        # Prepare the repl window, but do not open a connection yet.
        # This should only be done when repl becomes active.
        self.repl_connection = qt5_repl_gui.REPLConnection(self.port, 115200)
        self.ui.ReplPane.set_connection(self.repl_connection)
        self.repl_connection.data_received.connect(self.ui.ReplPane.process_tty_data)

        self.cmdlineapp = esp32cli.ESPShell(port=self.port)

    # -------------------------------------------------------------------------
    # @dumpArgs
    def write(self, text):
        """Handle sys.stdout.write: update display

        :param text: Text to display
        :return: Nothing
        """
        self.text_update.emit(
            text
        )  # noqa # Send signal to synchronise call with main thread # noqa

    # -------------------------------------------------------------------------
    @pyqtSlot(str)
    def append_text(self, text: str) -> None:
        """Text display update handler.

        :param text: Text to display
        :return: Nothing
        """

        # debug(f"Append text \"{text=}\"")
        cur = self.ui.text_output.textCursor()
        cur.movePosition(QtGui.QTextCursor.End)  # Move cursor to end of text
        s = str(text)
        while s:
            head, sep, s = s.partition("\n")  # Split line at LF
            head = head.replace(
                "\r", ""
            )  # Remove the Carriage Returns to avoid double linespacing.
            cur.insertText(head)  # Insert text at cursor
            if sep:  # New line if LF
                cur.insertBlock()
        self.ui.text_output.setTextCursor(cur)  # Update visible cursor
        self.ui.text_output.update()

    @staticmethod
    def flush() -> None:
        """Handle sys.stdout.flush: do nothing

        :return: Nothing
        """
        pass

    @staticmethod
    def isatty() -> bool:
        """to check if the given file descriptor is open and connected to tty(-like) device or not

        :return: True
        """
        return False

    @staticmethod
    def fileno() -> int:
        """Return -1 as the fileno, to satisfy cmd2 redirection.
        @todo: This does not work for cmd2 !shellcommands yet.
        """
        return -1

    # -------------------------------------------------------------------------
    def change_radiobuttons_to_current_mode(self) -> None:
        """Set radioboxes to current mode
        :returns: Nothing
        """

        debug("Changing radio box settings")

        if self.mode == MODE_COMMAND:
            self.ui.radioButton_replmode.setChecked(False)
            self.ui.radioButton_commandmode.setChecked(True)
            return

        if self.mode == MODE_REPL:
            self.ui.radioButton_replmode.setChecked(True)
            self.ui.radioButton_commandmode.setChecked(False)
            return

    # -------------------------------------------------------------------------
    def change_to_command_mode(self) -> int:
        """Switch from serial repl to serial command mode.
        :returns: New mode (MODE_COMMAND or MODE_REPL)
        """

        debug("=====")
        debug("Change to command mode")

        if self.mode == MODE_COMMAND:
            debug("Already in COMMAND mode")
            return self.mode

        self.mode = MODE_COMMAND
        self.change_radiobuttons_to_current_mode()

        # Stop the REPL connection if that is active
        if self.repl_connection.serial:
            debug("self.repl_connection.serial is True. Closing repl_connection")
            self.repl_connection.close()
        else:
            debug("self.repl_connection.serial is False")

        # Open the serial connection for the commandline mode
        debug("Open the serial connection for the commandline mode")
        self.cmdlineapp.onecmd_plus_hooks(f"open {self.port}")

        self.ui.command_input.setFocus()
        debug(f"now sys.stdout was {sys.stdout=}")
        sys.stdout = self
        debug(f"now sys.stdout is {sys.stdout=}")

        return self.mode

    # -------------------------------------------------------------------------
    @dumpFuncname
    def change_to_repl_mode(self, method=INTERNAL) -> int:
        """Switch to REPL mode.
        :param method: The method to use (internal, pytty or miniterm)
        :returns: New method
        """

        debug("=====")

        if self.mode == MODE_REPL:
            debug("Already in REPL mode")
            return self.mode

        # Close the serial connection for the commandline mode
        self.cmdlineapp.onecmd_plus_hooks("close")

        self.mode = MODE_REPL
        self.change_radiobuttons_to_current_mode()

        if method == INTERNAL:
            if not self.repl_connection.is_connected:
                debug("Opening new repl connection")
                self.repl_connection.open()
            else:
                debug("reusing exiting active repl connection")
            self.ui.ReplPane.setFocus()
            self.ui.ReplPane.moveCursor(QTextCursor.End, QTextCursor.MoveAnchor)
            # self.repl_connection.send_interrupt()
            self.repl_connection.send_exit_raw_mode()
            return MODE_REPL

        if method == PUTTY:
            putty("COM4:")
            self.show_text("Putty has been terminated\n")
            self.mode = MODE_COMMAND
            return self.mode

        if method == MINITERM:
            miniterm("COM4")
            self.show_text("Miniterm has been terminated\n")
            self.mode = MODE_COMMAND
            return self.mode

        print(f"Unknown repl {method=}")
        self.mode = MODE_COMMAND
        return self.mode

    # -------------------------------------------------------------------------
    def webrepl(self) -> None:
        """Start webrepl in browser
        """

        debug("webrepl button clicked.")
        webrepl_ip = self.ui.lineEdit_webrepl_ip.text()
        esp32cli.webrepl(ip=webrepl_ip)

    # -------------------------------------------------------------------------
    @dumpFuncname
    def get_ui_properties(self) -> None:
        """Get the values from the UI textfields, checkboxes and radiobuttons

        And save them in the configuration file.
        """

        # Save GUI settings
        srcpath = self.ui.lineEdit_srcpath.text()
        esp32common.set_sourcefolder(srcpath)

        webrepl_ip = self.ui.lineEdit_webrepl_ip.text()
        self.config["wlan"]["ip"] = webrepl_ip

        # Save the (modified configuration file)
        esp32common.saveconfig(self.config)

    # -------------------------------------------------------------------------
    @dumpFuncname
    def set_ui_properties(self) -> bool:
        """Get the values from the UI textfields, checkboxes and radiobuttons"""

        # Main window properties
        self.setWindowTitle("ESP32 microPython PyQT5 GUI/Shell")

        # Show current uPython source path
        srcpath = esp32common.get_sourcefolder()
        self.ui.lineEdit_srcpath.setText(str(srcpath))

        # Show the serial port which will be used
        port = self.config["com"]["port"]
        desc = self.config["com"]["desc"]
        self.show_text(f"Using {port} {desc}\r\n")
        self.ui.label_comport.setText(f"{port} ({desc}")

        webrepl_ip = self.config["wlan"]["ip"]
        self.ui.lineEdit_webrepl_ip.setText(webrepl_ip)

        return True

    # -------------------------------------------------------------------------
    @dumpArgs
    def show_result(self, out: str, err: str) -> None:
        """Print the stdout and stderr strings in the output window.
        :param out: Stdout string or another normal output string
        :param err: Stderr string or another error message
        :returns: Nothing
        """

        if out:
            self.ui.text_output.append(out)

        if err:
            self.ui.text_output.append("ERROR: ")
            self.ui.text_output.append(err)
            self.ui.text_output.update()

    # -------------------------------------------------------------------------
    def show_text(self, text: str) -> None:
        """Print the stdout string in the output window.
        :param text: Stdout string or another normal output string
        :returns: Nothing
        """

        if text:
            self.ui.text_output.append(text)
            self.ui.text_output.update()

    # -------------------------------------------------------------------------
    def do_clicked_command(self, item) -> None:
        """Execute the command which was clicked on.

        :param item: The item which was clicked. The command to execute is in the text of that item.
        :returns: Nothing
        """

        cmd = item.text()
        # debug(f"do_entered command {cmd=}")
        self.do_command(cmd_str=cmd)

    # -------------------------------------------------------------------------
    def do_entered_command(self) -> None:
        """Perform the command as found in the 'command_input' box.

        This function is called when an 'Enter' was detected.
        It will grab the text from the input box and process that command

        :returns: Nothing
        """

        cmd = self.ui.command_input.text()
        self.do_command(cmd_str=cmd)

    # -------------------------------------------------------------------------
    def do_command(self, cmd_str=None) -> None:
        """Execute the given command
        :param cmd_str: The command to execute
        :returns: Nothing

        There are a number of special commands, e.g.::
        * `cls` (Clear Screen) will make output windows empty.
        * `repl` will put this application in repl mode
        * `cmd` will put this application in cmd mode.

        All other commands will make use of the defined actions in the cli.

        If it was a valid command, the command input window will be cleared after it's execution.

        """

        # Note: Only use return from one of the if/elif branches in case of an error.
        # At the end, the last command will be added to a list of commands.

        debug(f"do_command {cmd_str=}")
        if not cmd_str:
            debug("ERROR: No command given")

        if not self.mode == MODE_COMMAND:
            debug("We were not in command mode, switching to command mode now")
            self.change_to_command_mode()

        try:
            if cmd_str == "cls":
                debug("Clearing output windows.")
                self.ui.text_output.setText("")
                self.ui.ReplPane.setText("")
            elif cmd_str == "repl":
                self.change_to_repl_mode()
            elif cmd_str == "cmd":
                self.change_to_command_mode()
            elif cmd_str == "test":
                param.worker.run_command("ping 127.0.0.1")
                while param.worker.active:
                    # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
                    loop = QEventLoop()
                    QTimer.singleShot(250, loop.quit)
                    loop.exec_()
                param.worker.run_command("ping 192.168.178.1")
            else:
                self.cmdlineapp.onecmd_plus_hooks(cmd_str)
            # Clear the input window. This also indicates that the
            # command was executed without problem.
            self.ui.command_input.clear()
        except Exception as err:
            print(f"{err=}")

        # If this command is not in the list of commands entered till now,
        # add it and save the list in a text file.
        if cmd_str.strip() not in self.list_of_commands:
            self.list_of_commands.append(cmd_str.strip())
            self.ui.commandlist.addItem(cmd_str.strip())

            with open('gui_cmd_history.txt', 'w') as f:
                for s in self.list_of_commands:
                    f.write(s.strip() + '\n')


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    clear_debug_window()

    # port, desc = esp32common.get_comport()
    # config['com']['port'] = port
    # config['com']['desc'] = desc

    param.is_gui = True

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
