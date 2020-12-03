"""ESP32 CLI Commandline shell.

This module contains the commandline loop, based on cmd2
"""

# Global imports
import os
import sys
import functools
import subprocess
import datetime
import argparse
from pathlib import Path
import cmd2
from cmd2 import with_argparser
from cmd2 import style, fg, bg, CommandResult

# Local imports
import lib.helper as helper
from lib.helper import debug, clear_debug_window
from lib.decorators import dumpFuncname, dumpArgs
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
        super().__init__(multiline_commands=['echo'], startup_script=startup_script, persistent_history_file='cmd2_history.dat')

        # Prints an intro banner once upon application startup
        self.intro = style("esp32 CLI (Command Line Interpreter)  \n'help' or '?' will show the available commands", fg=fg.red, bg=bg.white, bold=True)

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
            srcfile = statement.arg_list[0]
            targetfile = statement.arg_list[0]
        elif len(statement.arg_list) == 2:
            srcfile = statement.arg_list[0]
            targetfile = statement.arg_list[1]
        else:
            self.perror("Invalid number of arguments")
            self.do_help('put')
            self.last_result = CommandResult('', 'Bad arguments')
            return

        out, err = esp32common.put(srcfile, targetfile)

        if err:
            self.perror(err)
            return
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_get(self, statement):
        """Copy a file from the connected device to the PC

        put sourcefile targetfile

        If name of targetfile is not given, then it will become the same name as the sourcefile
        """

        debug(f"do_get {statement=}")
        if len(statement.arg_list) == 1:
            srcfile = statement.arg_list[0]
            targetfile = statement.arg_list[0]
        elif len(statement.arg_list) == 2:
            srcfile = statement.arg_list[0]
            targetfile = statement.arg_list[1]
        else:
            self.perror("Invalid number of arguments")
            self.do_help('get')
            self.last_result = CommandResult('', 'Bad arguments')
            return

        out, err = esp32common.get(srcfile, targetfile)

        if err:
            self.perror(err)
            return
        if out:
            print(out)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_reset(self, statement):
        """Reset the connected device.
        """
        out, err = esp32common.reset()
        print(out, err)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_ls(self, statement):
        """Get files and folders from the device
        """
        out, err = esp32common.ls()
        print(out, err)

    do_dir = do_ls      # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_run(self, statement):
        """Run the given file on the connected device
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.run(targetfile)
        print(out, err)

    do_start = do_run       # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rm(self, statement):
        """Remove/Delete file from the connected device.
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.rm(targetfile)
        print(out, err)

    do_del = do_rm      # Create an alias

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_mkdir(self, statement):
        """Make a directory on the connected device.
        """

        debug(f"{statement=}")
        targetfile = statement.arg_list[0]
        out, err = esp32common.mkdir(targetfile)
        print(out, err)

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rmdir(self, statement):
        """Remove a directory on the connected device.
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


# ===============================================================================
if __name__ == "__main__":

    helper.clear_debug_window()
    esp32common.get_comport()

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