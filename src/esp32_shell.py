# global imports
import sys
import py_cui
import subprocess
import ampy.pyboard

# local imports
from lib.helper import debug
from lib.decorators import dumpArgs
import comport

portlist = comport.serial_ports(usb=True)
try:
    COMPORT = portlist[0]
    print(COMPORT)
except IndexError:
    print("\nERROR: Could not find an active COM port to the device\nIs any device connected?\n")
    sys.exit(-1)


class Esp32Shell:

    def __init__(self, master):

        self.master = master

        # Textbox for entering a  command
        self.cmd_textbox = self.master.add_text_box('Literal command', 0, 0, column_span=6)
        self.cmd_textbox.add_key_command(py_cui.keys.KEY_ENTER, self.get_literal_command_on_enter)

        # The scrolled list cells that will contain our tasks in each of the three categories
        self.list_of_commands = ["ls", "esptool", "RShell", "mpfshell"]
        self.cell_commandlist = self.master.add_scroll_menu('Command List', 1, 0, row_span=5, column_span=1)
        self.cell_commandlist.add_item_list(self.list_of_commands)
        self.cell_commandlist.add_key_command(py_cui.keys.KEY_ENTER, self.cell_command_on_enter)

        self.output_text_block = self.master.add_text_block('Output', 1, 1, row_span=5, column_span=3)

        self.master.move_focus(self.cmd_textbox)

        # Local variables
        self.filename = None
        self.foldername = None

    def get_literal_command_on_enter(self):
        """

        :return:
        """

        command = self.cmd_textbox.get()
        if not command:
            debug("No command given")
            return
        if command not in self.list_of_commands:
            self.list_of_commands.append(command)
            self.cell_commandlist.add_item(command)
        self.cmd_textbox.clear()
        self.do_command(command)
        self.master.move_focus(self.cmd_textbox)

    def cell_command_on_enter(self):
        """
        """

        command_str = self.cell_commandlist.get()
        if command_str is None:
            self.master.show_error_popup('No command given', 'No command in the command list')
            return
        self.do_command(command_str)

    @dumpArgs
    def do_command(self, commandstr):

        out = ""
        err = ""

        if commandstr == 'quit' or commandstr == 'exit':
            sys.exit(0)

        elif commandstr == 'ls' or commandstr == 'dir':
            proc = subprocess.Popen(['ampy', '-p', COMPORT, 'ls'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

        elif commandstr.startswith("get"):
            cmd = ""
            srcfile = ""
            targetfile = ""
            nr_arguments = len(commandstr.split())
            debug(f"get {nr_arguments=}")
            if nr_arguments == 1:
                self.master.show_error_popup("Missing argument", "GET needs the name of the file to get, and the target filename.")
                self.cmd_textbox.clear()
                self.master.move_focus(self.cmd_textbox, auto_press_buttons=True)
                return
            if nr_arguments == 2:
                cmd, srcfile = commandstr.split()
                targetfile = srcfile
            if nr_arguments == 3:
                cmd, srcfile, targetfile = commandstr.split()
            debug(f"{cmd=} {srcfile=} {targetfile=}")
            self.output_text_block.set_text("getting " + self.filename)
            proc = subprocess.Popen(['ampy', '-p', COMPORT, 'get', srcfile, targetfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

        elif commandstr.startswith("put"):
            cmd = ""
            srcfile = ""
            targetfile = ""
            nr_arguments = len(commandstr.split())
            debug(f"put {nr_arguments=}")
            if nr_arguments == 1:
                self.master.show_error_popup("Missing argument", "PUT needs the name of the file to send, and the target filename.")
                self.master.move_focus(self.cmd_textbox, auto_press_buttons=True)
                return
            if nr_arguments == 2:
                cmd, srcfile = commandstr.split()
                targetfile = srcfile
            if nr_arguments == 3:
                cmd, srcfile, targetfile = commandstr.split()
            debug(f"{cmd=} {srcfile=} {targetfile=}")
            self.output_text_block.set_text("putting " + self.filename)
            proc = subprocess.Popen(['ampy', '-p', COMPORT, 'put', srcfile, targetfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

        elif commandstr == "reset":
            self.output_text_block.set_text("resetting remote device")
            proc = subprocess.Popen(['ampy', '-p', COMPORT, 'reset'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

        elif commandstr.startswith("mkdir"):
            nr_arguments = len(commandstr.split())
            debug(f"mkdir {nr_arguments=}")
            if nr_arguments == 1:
                self.master.show_error_popup("Missing argument", "mkdir needs the name of the folder to create.")
                self.master.move_focus(self.cmd_textbox, auto_press_buttons=False)
            elif nr_arguments == 2:
                cmd, foldername = commandstr.split()
                self.output_text_block.set_text("creating " + foldername)
                proc = subprocess.Popen(['ampy', '-p', COMPORT, 'mkdir', foldername], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                out, err = proc.communicate()

        elif commandstr.startswith("rmdir"):
            nr_arguments = len(commandstr.split())
            if nr_arguments == 1:
                self.master.show_error_popup("Missing argument", "rmdir needs the name of the folder to remove.")
                self.master.move_focus(self.cmd_textbox, auto_press_buttons=False)
            elif nr_arguments == 2:
                cmd, foldername = commandstr.split()
                self.output_text_block.set_text("Removing folder " + foldername)
                try:
                    proc = subprocess.Popen(['ampy', '-p', COMPORT, 'rmdir', foldername], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    out, err = proc.communicate()
                except ampy.pyboard.PyboardError:
                    err = f"Problem in removing {foldername}"
                    pass

        elif commandstr.startswith("rm"):
            self.filename = ""
            nr_arguments = len(commandstr.split())
            if nr_arguments == 1:
                self.master.show_error_popup("Missing argument", "rm needs the name of the file to remove.")
                self.master.move_focus(self.cmd_textbox, auto_press_buttons=False)
            elif nr_arguments == 2:
                cmd, filename = commandstr.split()
                debug(f"{cmd=} {filename=}")
                self.output_text_block.set_text("removing file " + filename)
                try:
                    proc = subprocess.Popen(['ampy', '-p', COMPORT, 'rm', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    out, err = proc.communicate()
                except (ampy.pyboard.PyboardError, RuntimeError):
                    err = f"Problem in removing {filename}"

        else:
            self.master.show_error_popup("Error", f"Unknown command {commandstr}.")

        self.display(out, err)

    @dumpArgs
    def display(self, err, out):
        text_to_display = ""
        if out:
            text_to_display += out.decode()
        if err:
            text_to_display += err.decode()
        debug(f"{text_to_display=}")
        if text_to_display:
            self.output_text_block.set_text(text_to_display)
        self.master.move_focus(self.cmd_textbox, auto_press_buttons=False)

    # @dumpArgs
    # def literal_command_on_enter(self):
    #     cmd = self.cmd_textbox.get()
    #     debug(f"{cmd=}")
    #     # self.master.show_message_popup("command", cmd)
    #     self.do_command(cmd)
    #     self.cell_commandlist.add_item(cmd)


if __name__ == "__main__":
    # Create the CUI with x rows and y  columns, pass it to the wrapper object, and start it
    root = py_cui.PyCUI(7, 6)
    root.set_title('ESP32 Shell')
    root.set_widget_cycle_key(forward_cycle_key=py_cui.keys.KEY_TAB)
    s = Esp32Shell(root)
    root.start()
