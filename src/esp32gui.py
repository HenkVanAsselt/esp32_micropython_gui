"""ESP32 GUI Shell (pyside2) main module"""

# Global imports

import sys
import subprocess
from PySide2.QtWidgets import QApplication, QMainWindow
from PySide2.QtGui import QTextCursor

# Local imports
from esp32shell_qt_design import Ui_MainWindow
from lib.helper import debug, clear_debug_window
from lib.decorators import dumpFuncname

COMPORT = ""
COMPORT_DESC = ""

MODE_COMMAND = 1
MODE_REPL = 2


# -----------------------------------------------------------------------------
# Determine active USB to Serial COM port
# -----------------------------------------------------------------------------
def get_comport() -> tuple:

    import comport

    global COMPORT
    global COMPORT_DESC

    portlist, desclist = comport.serial_ports(usb=True)
    try:
        print(f"portlist = {portlist}")
        COMPORT = portlist[0]
        COMPORT_DESC = desclist[0]
        print(COMPORT)
        print(COMPORT_DESC)
        return COMPORT, COMPORT_DESC
    except IndexError:
        err = "ERROR: Could not find an active COM port to the device\nIs any device connected?\n"
        return "", err


# -----------------------------------------------------------------------------
def ampy(*args) -> tuple:
    """Run an ampy.exe command with the given arguments

    :param args: Variable length of arguments
    :returns: tuple of stdout and stderr text
    """

    ampy_command_list = ["ampy", "-p", COMPORT]
    for arg in args:
        ampy_command_list.append(arg)

    proc = subprocess.Popen(
        ampy_command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
def rshell(*args) -> tuple:
    """Run an rshell.exe command with the given arguments

    :param args: Variable length of arguments
    :returns: tuple of stdout and stderr text
    """

    command_list = ["rshell", "-p", COMPORT, "repl"]
    for arg in args:
        command_list.append(arg)

    # proc = subprocess.Popen(
    #     command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    # )
    # out, err = proc.communicate()

    subprocess.Popen(command_list)
    return "", ""


# -----------------------------------------------------------------------------
def putty() -> tuple:
    """Run putty.exe with the given arguments

    :returns: tuple of stdout and stderr text
    """

    putty_command_list = ["putty", "-serial", COMPORT, "-sercfg", "115200,8,n,1,N"]

    proc = subprocess.Popen(
        putty_command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate(input="\r\n")
    return out.decode(), err.decode()


# -----------------------------------------------------------------------------
def miniterm() -> tuple:
    """Run putty.exe with the given arguments

    :returns: tuple of stdout and stderr text
    """

    command_list = ["pyserial-miniterm.exe", COMPORT, "115200"]

    subprocess.run(command_list, shell=True)
    return "", ""


# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """QT Main Window
    """

    def __init__(self):
        """Intialize the QT window
        """

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # If neccessary, set properties of some elements
        self.set_ui_properties()

        # After a command is entered, and ENTER is pressed, react on it
        self.ui.command_input.returnPressed.connect(self.do_command)

        # If a command from the list of commands is clicked, execute it
        self.list_of_commands = []
        self.ui.commandlist.itemClicked.connect(self.do_clicked_command)

        # Handle the switch from repl mode to command mode and visa versa
        self.ui.radioButton_commandmode.clicked.connect(self.do_changemode)
        self.ui.radioButton_replmode.clicked.connect(self.do_changemode)

        # Show the serial port which will be used
        self.show_text(f"Using {COMPORT} ({COMPORT_DESC}\r\n")
        self.ui.label_comport.setText(f"{COMPORT} ({COMPORT_DESC}")

        self.mode = MODE_COMMAND        # Start in Command mode

    # -------------------------------------------------------------------------
    @dumpFuncname
    def do_changemode(self, new_mode=None):
        """Handle the switch from repl mode to command mode and visa versa.
        """

        if not new_mode:

            if self.ui.radioButton_commandmode.isChecked():
                debug("commandmode is checked")
                new_mode = MODE_COMMAND

            elif self.ui.radioButton_replmode.isChecked():
                debug("replmode is checked")
                new_mode = MODE_REPL

        if new_mode == MODE_COMMAND:
            self.ui.radioButton_replmode.setChecked(False)
            self.ui.radioButton_commandmode.setChecked(True)
            # @todo: change background of repl window to gray
            self.ui.Repl.stop_repl()
            self.ui.command_input.setFocus()
            self.show_text("Now working in command mode")
            self.mode = MODE_COMMAND

        elif new_mode == MODE_REPL:
            self.ui.radioButton_commandmode.setChecked(False)
            self.ui.radioButton_replmode.setChecked(True)
            self.show_text("Switchng to REPL mode")
            self.ui.Repl.start_repl()
            self.show_text("Now working in REPL mode")
            self.ui.Repl.textbox.setFocus()
            self.ui.Repl.textbox.moveCursor(QTextCursor.End, QTextCursor.MoveAnchor)
            self.mode = MODE_REPL

        else:
            debug(f"ERROR, unknown mode {new_mode}")



    # -------------------------------------------------------------------------
    @dumpFuncname
    def get_ui_properties(self):
        """Get the values from the UI textfields, checkboxes and radiobuttons"""

        return

    # -------------------------------------------------------------------------
    @dumpFuncname
    def set_ui_properties(self) -> bool:
        """Get the values from the UI textfields, checkboxes and radiobuttons"""

        try:

            # Main window properties
            self.setWindowTitle("ESP32 microPython GUI/Shell")

        except Exception as e:
            debug(e)
            return False
        return True

    # -------------------------------------------------------------------------
    def show_result(self, out: str, err: str):
        """Print the stdout and stderr strings in the output window.
        :param out: Stdout string or another normal output string
        :param err: Stderr string or another error message
        :returns: Nothing
        """

        if out:
            self.ui.text_output.append(out)
        if err:
            self.ui.text_error_output.append("ERROR:\r\n")
            self.ui.text_error_output.append(err)

        if not err:
            self.ui.text_error_output.clear()

        return

    # -------------------------------------------------------------------------
    def show_text(self, out: str):
        """Print the stdout string in the output window.
        :param out: Stdout string or another normal output string
        :returns: Nothing
        """

        if out:
            self.ui.text_output.append(out)
        return

    # -------------------------------------------------------------------------
    def show_error(self, err: str):
        """Print the stderr string in the output window.
        :param err: Stderr string or another error message
        :returns: Nothing
        """

        if err:
            self.ui.text_error_output.append("\r\nERROR:\r\n")
            self.ui.text_error_output.append(err)
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

        out = ""
        err = ""

        if self.mode == MODE_REPL:
            self.show_text("Switching to command mode")
            self.do_changemode(MODE_COMMAND)

        if not cmd_str:
            cmd_str = self.ui.command_input.text()

        if cmd_str == "cls": 
            self.ui.text_error_output.setText("")
            self.ui.text_output.setText("")
            self.ui.Repl.textbox.setText("")

        elif cmd_str == "putty":
            out, err = putty()
            self.show_result(out, err)

        elif cmd_str == "repl":
            # out, err = rshell()
            # self.show_result(out, err)
            self.do_changemode(MODE_REPL)

        elif cmd_str == "cmd":
            # out, err = rshell()
            # self.show_result(out, err)
            self.do_changemode(MODE_COMMAND)

        # elif cmd_str == "miniterm":
        #     out, err = miniterm()
        #     self.show_result(out, err)

        elif cmd_str == "reset":
            self.show_result("", "Resetting connected device")
            out, err = ampy("reset")
            self.show_result(out, err)

        elif cmd_str == "ls" or cmd_str == "dir":
            out, err = ampy("ls", "-l")
            self.show_text("Files and folders on connected device:")
            self.show_result(out, err)

        elif cmd_str.startswith("run"):
            nr_arguments = len(cmd_str.split())
            debug(f"get {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("ERROR: GET needs the name of the file to get, and the target filename.")
                return
            elif nr_arguments == 2:
                cmd, targetfile = cmd_str.split()
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return
            debug(f"{cmd_str=} {targetfile=}")
            out, err = ampy("run", targetfile)
            self.show_result(out, err)

        elif cmd_str.startswith("get"):
            nr_arguments = len(cmd_str.split())
            debug(f"get {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("ERROR: GET needs the name of the file to get, and the target filename.")
                return
            elif nr_arguments == 2:
                cmd, srcfile = cmd_str.split()
                targetfile = srcfile
            elif nr_arguments == 3:
                cmd, srcfile, targetfile = cmd_str.split()
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return
            debug(f"{cmd_str=} {srcfile=} {targetfile=}")
            out, err = ampy("get", srcfile, targetfile)
            self.show_result(out, err)

        elif cmd_str.startswith("put"):
            nr_arguments = len(cmd_str.split())
            debug(f"get {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("ERROR: PUT needs the name of the file to get, and the target filename.")
                return
            elif nr_arguments == 2:
                cmd, srcfile = cmd_str.split()
                targetfile = srcfile
            elif nr_arguments == 3:
                cmd, srcfile, targetfile = cmd_str.split()
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return
            debug(f"{cmd_str=} {srcfile=} {targetfile=}")
            out, err = ampy("put", srcfile, targetfile)
            self.show_result(out, err)

        elif cmd_str.startswith("rm"):
            nr_arguments = len(cmd_str.split())
            debug(f"get {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("ERROR: PUT needs the name of the file to get, and the target filename.")
                return
            elif nr_arguments == 2:
                cmd, targetfile = cmd_str.split()
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return
            debug(f"{cmd_str=} {targetfile=}")
            out, err = ampy("rm", targetfile)
            self.show_result(out, err)

        elif cmd_str.startswith("mkdir"):
            nr_arguments = len(cmd_str.split())
            debug(f"mkdir {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("mkdir ERROR: No foldername given.")
                return
            elif nr_arguments == 2:
                cmd, foldername = cmd_str.split()
                out, err = ampy('mkdir', foldername)
                self.show_result(out, err)
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return

        elif cmd_str.startswith("rmdir"):
            nr_arguments = len(cmd_str.split())
            debug(f"rmdir {nr_arguments=}")
            if nr_arguments == 1:
                self.show_error("rmdir ERROR: No foldername given.")
                return
            elif nr_arguments == 2:
                cmd, foldername = cmd_str.split()
                out, err = ampy('rmdir', foldername)
                self.show_result(out, err)
            else:
                self.show_error(f"Invalid number of commands in \"{cmd_str}\"")
                return
        else:
            err = f"ERROR: Unknown command \"{cmd_str}\""
            self.ui.text_error_output.setText(err)

        # If no error was found, clear the input window and add the command to the list
        # of executed commands, but only if it is not in there yet
        if not err:
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
            else:
                print(f"command \"{cmd_str}\" is already in the list of commands")


# -----------------------------------------------------------------------------
if __name__ == "__main__":

    clear_debug_window()

    port, desc = get_comport()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
