"""ESP32 GUI Shell (pyside2) main module"""

# Global imports

import sys
import subprocess
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QApplication, QMainWindow
from PySide2.QtGui import QTextCursor

# Local imports
import param
from esp32shell_qt_design import Ui_MainWindow
from lib.helper import debug, clear_debug_window, dumpFuncname, dumpArgs
import esp32common

import esp32cli

MODE_COMMAND = 1
MODE_REPL = 2


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

    # subprocess.run(command_list, shell=True)
    # return "", ""

    proc = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate(input=b"\r\n")
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """QT Main Window
    """

    text_update = QtCore.Signal(str)        # PySide2

    def __init__(self):
        """Intialize the QT window
        """

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # After a command is entered, and ENTER is pressed, react on it
        self.ui.command_input.returnPressed.connect(self.do_command)

        self.ui.lineEdit_srcpath.returnPressed.connect(self.get_ui_properties)

        # If a command from the list of commands is clicked, execute it
        self.list_of_commands = []
        self.ui.commandlist.itemClicked.connect(self.do_clicked_command)

        # Handle the switch from repl mode to command mode and visa versa
        self.ui.radioButton_commandmode.clicked.connect(self.change_to_command_mode)
        self.ui.radioButton_replmode.clicked.connect(self.change_to_repl_mode)

        # Read configuration
        self.config = esp32common.readconfig('esp32cli.ini')
        param.config = self.config

        port, desc = esp32common.get_active_comport()
        self.config['com']['port'] = port
        self.config['com']['desc'] = desc
        debug(f"Active com port is {port}")

        # If neccessary, set properties of some elements
        self.set_ui_properties()

        self.mode = MODE_COMMAND        # Start in Command mode

        debug(f"sys.stdout was {sys.stdout=}")
        self.org_stdout = sys.stdout
        sys.stdout = self
        sys.stderr = self
        debug(f"now sys.stdout is {sys.stdout=}")
        self.text_update.connect(self.append_text) # noqa # Connect text update to handler

        self.ui.command_input.setFocus()

        self.cmdlineapp = esp32cli.MpFileShell()

    # -------------------------------------------------------------------------
    # @dumpArgs
    def write(self, text):
        """Handle sys.stdout.write: update display

        :param text: Text to display
        :return: Nothing
        """
        self.text_update.emit(text)  # noqa # Send signal to synchronise call with main thread # noqa

    # -------------------------------------------------------------------------
    # @dumpArgs
    def append_text(self, text):
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
            head = head.replace("\r", "")     # Remove the Carriage Returns to avoid double linespacing.
            cur.insertText(head)  # Insert text at cursor
            if sep:  # New line if LF
                cur.insertBlock()
        self.ui.text_output.setTextCursor(cur)  # Update visible cursor

    @staticmethod
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
        @todo: This does not work for cmd2 !shellcommands yet.
        """
        return -1

    # -------------------------------------------------------------------------
    @dumpFuncname
    def change_to_command_mode(self):
        """Switch to command mode.
        """
        debug("radiobox command clicked")
        if not self.mode == MODE_COMMAND:
            self.change_to_mode(MODE_COMMAND)

    # -------------------------------------------------------------------------
    @dumpFuncname
    def change_to_repl_mode(self):
        """Switch to REPL mode.
        """
        debug("radiobox repl clicked")
        if not self.mode == MODE_REPL:
            self.change_to_mode(MODE_REPL)

    # -------------------------------------------------------------------------
    @dumpArgs
    def change_to_mode(self, new_mode=None):
        """Handle the switch from repl mode to command mode and visa versa.
        """

        INTERNAL = 1
        PUTTY = 2
        MINITERM = 3

        method = PUTTY

        if not new_mode:

            if self.ui.radioButton_commandmode.isChecked():
                debug("commandmode is checked")
                new_mode = MODE_COMMAND

            elif self.ui.radioButton_replmode.isChecked():
                debug("replmode is checked")
                new_mode = MODE_REPL

        if self.mode == MODE_REPL and new_mode == MODE_COMMAND:
            debug("Switching to COMMAND mode")
            self.ui.radioButton_replmode.setChecked(False)
            self.ui.radioButton_commandmode.setChecked(True)
            if method == INTERNAL:
                self.ui.Repl.stop_repl()
            self.ui.command_input.setFocus()
            debug(f"now sys.stdout was {sys.stdout=}")
            sys.stdout = self
            debug(f"now sys.stdout is {sys.stdout=}")
            self.mode = MODE_COMMAND
            print("Switched to COMMAND mode\n")

        elif self.mode == MODE_COMMAND and new_mode == MODE_REPL:
            debug("Switching to REPL mode")
            self.ui.radioButton_commandmode.setChecked(False)
            self.ui.radioButton_replmode.setChecked(True)
            self.show_text("Switching to REPL mode\n")
            if method == INTERNAL:
                self.mode = MODE_REPL
                self.ui.Repl.start_repl()
                self.ui.Repl.textbox.setFocus()
                self.ui.Repl.textbox.moveCursor(QTextCursor.End, QTextCursor.MoveAnchor)
            elif method == PUTTY:
                self.mode = MODE_REPL
                putty("COM4:")
                self.show_text("Putty has been terminated\n")
            elif method == MINITERM:
                self.mode = MODE_REPL
                miniterm("COM4")
                self.show_text("Miniterm has been terminated\n")
            else:
                print(f"Unknown repl {method=}")
                self.mode = MODE_COMMAND

        else:
            debug(f"ERROR, unknown mode {new_mode}")

    # -------------------------------------------------------------------------
    @dumpFuncname
    def get_ui_properties(self):
        """Get the values from the UI textfields, checkboxes and radiobuttons"""

        # Save GUI setting
        srcpath = self.ui.lineEdit_srcpath.text()
        self.config['src']['srcpath'] = srcpath

        # Save the (modified configuration file)
        esp32common.saveconfig(self.config)

        return

    # -------------------------------------------------------------------------
    @dumpFuncname
    def set_ui_properties(self) -> bool:
        """Get the values from the UI textfields, checkboxes and radiobuttons"""

        try:

            # Main window properties
            self.setWindowTitle("ESP32 microPython PySide2 GUI/Shell")

            # Show current uPython source path
            srcpath = self.config['src']['srcpath']
            self.ui.lineEdit_srcpath.setText(srcpath)

            # Show the serial port which will be used
            port = self.config['com']['port']
            desc = self.config['com']['desc']
            self.show_text(f"Using {port} {desc}\r\n")
            self.ui.label_comport.setText(f"{port} ({desc}")

        except Exception as e:
            debug(e)
            return False
        return True

    # -------------------------------------------------------------------------
    @dumpArgs
    def show_result(self, out: str, err: str):
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

        return

    # -------------------------------------------------------------------------
    def show_text(self, out: str):
        """Print the stdout string in the output window.
        :param out: Stdout string or another normal output string
        :returns: Nothing
        """

        if out:
            self.ui.text_output.append(out)
            self.ui.text_output.update()
        return

    # -------------------------------------------------------------------------
    def do_clicked_command(self, item):
        """Execute the command which was clicked on.
        :param item: The item which was clicked. The command to execute is in the text of that item.
        :returns: Nothing
        """

        cmd = item.text()
        self.do_command(cmd_str=cmd)

    # -------------------------------------------------------------------------
    def do_command(self, cmd_str=None):
        """Execute the given command
        :param cmd_str: The command to execute
        :returns: Nothing

        If it was a valid command, the command input window will be cleared after it's execution.

        """

        # Note: Only use return from one of the if/elif branches in case of an error.
        # At the end, the last command will be added to a list of commands.

        if not self.mode == MODE_COMMAND:
            self.change_to_command_mode()

        if not cmd_str:
            cmd_str = self.ui.command_input.text()

        if cmd_str == "cls":
            self.ui.text_output.setText("")
            self.ui.Repl.textbox.setText("")
        # elif cmd_str == "repl":
        #     self.change_to_repl_mode()
        elif cmd_str == "cmd":
            self.change_to_command_mode()
        else:
            self.cmdlineapp.onecmd_plus_hooks(cmd_str)

        # --- This will search in the QT list instead of the manually maintained list
        # --- Needs: from PySide2.QtCore import Qt
        # items = self.ui.commandlist.findItems(cmd_str, Qt.MatchExactly)
        # print(f"found items: {items=}")
        # for item in items:
        #     print(f"{item=} {item.text()}")
        self.ui.command_input.clear()
        if cmd_str not in self.list_of_commands:
            self.list_of_commands.append(cmd_str)
            self.ui.commandlist.addItem(cmd_str)
        # else:
        #     print(f"command \"{cmd_str}\" is already in the list of commands")


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    clear_debug_window()

    # port, desc = esp32common.get_comport()
    # config['com']['port'] = port
    # config['com']['desc'] = desc

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
