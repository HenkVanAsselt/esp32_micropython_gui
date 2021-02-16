"""ESP32 CLI Commandline shell.

This module contains the commandline loop, based on cmd2
"""

# Global imports
import os
import sys
import argparse
import pathlib
import tempfile

# 3rd party imports
import cmd2                 # type: ignore
from cmd2 import style, fg, bg, CommandResult

# Local imports
import param
import lib.helper as helper
from lib.helper import debug
import esp32common


# ===============================================================================
# CmdLineApp
# ===============================================================================
# noinspection PyUnusedLocal,PyShadowingNames
class CmdLineApp(cmd2.Cmd):
    """Class Command Line Application
    """

    # Define the help categories
    CMD_CAT_CONNECTING = "Connections"
    CMD_CAT_FILES = "Files and folders"
    CMD_CAT_EDIT = "Edit settings"
    CMD_CAT_INFO = "Information"
    CMD_CAT_DEBUG = "Debug and test"
    CMD_CAT_REBOOT = "Reboot related commands"

    # ===============================================================================
    # Class initializations. See https://cmd2.readthedocs.io/en/latest/features/initialization.html
    # ===============================================================================
    def __init__(self):

        startup_script = os.path.join(os.path.dirname(__file__), '.esp32clirc')
        super().__init__(multiline_commands=['echo'], startup_script=startup_script,
                         persistent_history_file='cmd2_history.dat')

        # Prints an intro banner once upon application startup
        self.intro = style("esp32 CLI (Command Line Interpreter)  \n'help' or '?' will show the available commands",
                           fg=fg.red, bg=bg.white, bold=True)

        # Show this as the prompt when asking for input
        self.prompt = 'esp32cli> '

        # Used as prompt for multiline commands after the first line
        self.continuation_prompt = '... '

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = 'cmd2 Built-in Commands'

        # Color to output text in with echo command
        self.foreground_color = 'cyan'

        # Make echo_fg settable at runtime
        self.add_settable(cmd2.Settable('foreground_color',
                                        str,
                                        'Foreground color to use with echo command',
                                        choices=fg.colors()))

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_put(self, statement):
        """Copy a file to the connected device

        put sourcefile targetfile

        If name of targetfile is not given, then it will become the same name as the sourcefile

        Example: put blinky.pu main.py
        """

        debug(f"do_put {statement=}")
        if len(statement.arg_list) == 1:
            srcfile = pathlib.Path(param.config['src']['srcpath'], statement.arg_list[0])
            targetfile = pathlib.Path(statement.arg_list[0])
        elif len(statement.arg_list) == 2:
            srcfile = pathlib.Path(param.config['src']['srcpath'], statement.arg_list[0])
            targetfile = pathlib.Path(statement.arg_list[1])
        else:
            self.perror("Invalid number of arguments")
            self.do_help('put')     # noqa to prevent: Expected type 'Namespace', got 'str' instead
            self.last_result = CommandResult('', 'Bad arguments')
            return

        out, err = esp32common.put(srcfile, targetfile)

        if err:
            self.perror(err)
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_get(self, statement):
        """Copy a file from the connected device to the PC

        get sourcefile targetfile

        If name of targetfile is not given, then it will become the same name as the sourcefile

        Example: get blinky.py blinky2.py
        """

        debug(f"do_get {statement=}")
        if len(statement.arg_list) == 1:
            srcfile = statement.arg_list[0]
            targetfile = pathlib.Path(param.config['src']['srcpath'], statement.arg_list[0])
        elif len(statement.arg_list) == 2:
            srcfile = statement.arg_list[0]
            targetfile = pathlib.Path(param.config['src']['srcpath'], statement.arg_list[1])
        else:
            self.perror("Invalid number of arguments")
            self.do_help('get')   # noqa to prevent: Expected type 'Namespace', got 'str' instead
            self.last_result = CommandResult('', 'Bad arguments')
            return

        out, err = esp32common.get(srcfile, targetfile)

        if err:
            self.perror(err)
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_reset(self, statement):
        """Reset the connected device.
        """
        out, err = esp32common.reset()
        if err:
            self.perror(err)
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_ls(self, statement):
        """Show the files and folders stored on the device.
        """
        out, err = esp32common.ls()
        if err:
            self.perror(err)
        if out:
            print(out)

    do_dir = do_ls      # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_ldir(self, statement):
        """List the files and folders in the source folder
        """

        sourcefolder = pathlib.Path(param.config['src']['srcpath'])
        if not sourcefolder.is_dir():
            self.perror(f"Could not find folder {sourcefolder}")
            return

        files = sorted(sourcefolder.glob('**/*'))
        filenames = [f.name for f in files if f.is_file()]
        for filename in filenames:
            print(f"{filename.strip()}\n")

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_ledit(self, statement):
        """Edit a file in the local source folder on the PC.

        If it is an absolute path is given, then use the absolute path.
        If not, then handle the filename as part of the defined micropython source folder

        """

        debug(f"edit {statement=}")
        filename = statement.args       # Just the raw argument string

        # If the given filename is not absolute, then assume it is located
        # in the current micropython sourcefolder
        if not pathlib.Path(filename).is_absolute():
            sourcefolder = esp32common.get_sourcefolder()
            sourcefile = sourcefolder.joinpath(filename)
        else:
            sourcefile = filename

        editor = pathlib.Path("C:/Program Files/Notepad++/notepad++.exe")
        cmdstr = f'"{editor}" "{sourcefile}"'
        esp32common.local_run(cmdstr)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_edit(self, statement):
        """Edit a file on the remote device.

        First check if the file is actually there.
        If so, get it as a local file.
        Edit it, and put it back when it was changed.
        """

        filename = statement.args
        if not filename.startswith('/'):
            self.perror(f"Error: {filename} does not start with an '/'")
            return

        with tempfile.TemporaryDirectory() as temp_dir:

            local_filename = os.path.join(temp_dir, os.path.basename(filename))
            debug(f"{local_filename=}")

            print(f"Retrieving {filename}")
            esp32common.get(filename, local_filename)

            editor = pathlib.Path("C:/Program Files/Notepad++/notepad++.exe")
            cmdstr = f'"{editor}" "{local_filename}"'
            esp32common.local_run(cmdstr)

            print(f"Updating {filename}")
            esp32common.put(local_filename, filename)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_lcd(self, statement):
        """Change the folder with sourcefiles
        """

        debug(f"lcd {statement=}")
        esp32common.set_sourcefolder(statement.args)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_run(self, statement):
        """Run the given file on the connected device
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.remote_run(targetfile)
        if err:
            self.perror(err)
        if out:
            print(out)

    do_start = do_run       # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rm(self, statement):
        """Remove/Delete file from the connected device.

        Example: rm blinky.py
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.rm(targetfile)
        if err:
            self.perror(err)
        if out:
            print(out)

    do_del = do_rm      # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_mkdir(self, statement):
        """Make a directory on the connected device.

        Example: mkdir testdir
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.mkdir(targetfile)
        if err:
            self.perror(err)
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rmdir(self, statement):
        """Remove a directory from the connected device.

        Example: rmdir testdir
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.rmdir(targetfile)
        print(out, err)

    # # ===========================================================================
    # @cmd2.with_category(CMD_CAT_FILES)
    # def do_repl(self, statement):
    #     """Remove a directory on the connected device.
    #     """
    #
    #     debug(f"{statement=}")
    #     out, err = esp32common.shell49("repl")
    #     print(out, err)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_echo(self, statement):
        """Just print the given text back. Can be used for debugging purposes
        """

        print(statement)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_cls(self, statement):
        """Clear the screen.
        """

        os.system('cls')

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_sync(self, statement):
        """Copy all python files (Sync) from the source folder to the connected device.

        Examples:
            * sync
            * sycn c:/temp/upython_files

        If no foldername is given, then implicitley hte internal default source
        folder will be used.

        """

        debug(f"do_sync {statement=}")

        sourcefolder = pathlib.Path(param.config['src']['srcpath'])
        if len(statement.arg_list) == 1:
            sourcefolder = pathlib.Path(statement.arg_list[0])

        if not sourcefolder.is_dir():
            print(f"Could not find folder {sourcefolder}")
            return

        # files = [e for e in sourcefolder.iterdir() if e.is_file()]
        # for filename in files:
        #     print(filename)

        for filename in sourcefolder.glob('*.py'):
            print(f"Syncing {filename}")
            out, err = esp32common.put(str(filename), str(filename))
            if err:
                self.perror(err)
            if out:
                print(out)


# -----------------------------------------------------------------------------
def main():

    helper.clear_debug_window()
    port, desc = esp32common.get_comport()
    debug(f"{port=}, {desc=}")

    # Read configuration
    config = esp32common.readconfig('esp32cli.ini')
    param.config = config

    param.config['com']['port'] = port
    param.config['com']['desc'] = desc

    debug("sys.argv = %s" % sys.argv)

    # Setup the argument parser
    parser = argparse.ArgumentParser(description="ESP32 CLI")
    command_help = (
        "Enter a command to run, if no command given, enter the interactive shell"
    )
    parser.add_argument("command", nargs="?", help=command_help)
    parser.add_argument("command_args", nargs=argparse.REMAINDER, help="optional arguments for command")
    arguments = parser.parse_args()
    debug(f"args = {repr(arguments)}")

    # Enter the commandline app
    app = CmdLineApp()
    if arguments.command:
        # A command was given. Execute it and stop this program
        app.onecmd_plus_hooks("{} {}".format(arguments.command, " ".join(arguments.command_args)))
        sys.exit(0)
    else:
        # No specific command was given, go to interactive CLI mode
        app.cmdloop()

    sys.exit(0)


# ===============================================================================
if __name__ == "__main__":

    main()
