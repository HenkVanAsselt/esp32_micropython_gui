##
# The MIT License (MIT)
#
# Copyright (c) 2016 Stefan Wendler
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##
import argparse
import glob
import io
import logging
import os
import platform
import sys
import tempfile
import pathlib


# 3rd party imports
import cmd2  # type: ignore
# from cmd2 import style, fg, bg, CommandResult
from cmd2 import fg
import colorama
import serial

# Local imports
import param
from mp import version
from mp.conbase import ConError
from mp.mpfexp import MpFileExplorer
from mp.mpfexp import MpFileExplorerCaching
from mp.mpfexp import RemoteIOError
from mp.pyboard import PyboardError
from mp.tokenizer import Tokenizer

import esp32common
from lib.helper import debug


class MpFileShell(cmd2.Cmd):

    # Define the help categories
    CMD_CAT_CONNECTING = "Connections"
    CMD_CAT_FILES = "Files and folders"
    CMD_CAT_EDIT = "Edit settings"
    CMD_CAT_INFO = "Information"
    CMD_CAT_DEBUG = "Debug and test"
    CMD_CAT_REBOOT = "Reboot related commands"
    CMD_CAT_RUN = "Execution commands"

    def __init__(self, color=False, caching=False, reset=False):

        startup_script = os.path.join(os.path.dirname(__file__), ".esp32clirc")
        super().__init__(
            multiline_commands=["echo"],
            startup_script=startup_script,
            persistent_history_file="cmd2_history.dat",
        )

        if color:
            colorama.init()
            cmd2.Cmd.__init__(
                self,
                stdout=colorama.initialise.wrapped_stdout,
                startup_script=startup_script,
                persistent_history_file="cmd2_history.dat",
            )
        else:
            cmd2.Cmd.__init__(self)

        if platform.system() == "Windows":
            self.use_rawinput = False

        self.color = color
        self.caching = caching
        self.reset = reset

        self.port = ""      # Name of the COM port
        self.fe = None
        self.repl = None
        self.tokenizer = Tokenizer()

        self.__intro()
        self.__set_prompt_path()

        # Used as prompt for multiline commands after the first line
        self.continuation_prompt = "... "

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = "cmd2 Built-in Commands"

        # Color to output text in with echo command
        self.foreground_color = "cyan"

        # Make echo_fg settable at runtime
        self.add_settable(
            cmd2.Settable(
                "foreground_color",
                str,
                "Foreground color to use with echo command",
                choices=fg.colors(),
            )
        )

    def __del__(self):
        self.__disconnect()

    def __intro(self):

        if self.color:
            self.intro = (
                "\n"
                + colorama.Fore.GREEN
                + "** Micropython File Shell v%s, sw@kaltpost.de ** " % version.FULL
                + colorama.Fore.RESET
                + "\n"
            )
        else:
            self.intro = (
                "\n** Micropython File Shell v%s, sw@kaltpost.de **\n" % version.FULL
            )

        self.intro += "-- Running on Python %d.%d using PySerial %s --\n" % (
            sys.version_info[0],
            sys.version_info[1],
            serial.VERSION,
        )

    def __set_prompt_path(self):

        if self.fe is not None:
            pwd = self.fe.pwd()
        else:
            pwd = "/"

        if self.color:
            self.prompt = (
                # colorama.Fore.BLUE
                colorama.Fore.LIGHTGREEN_EX
                + "cli32 ["
                + colorama.Fore.LIGHTGREEN_EX
                + pwd
                # + colorama.Fore.BLUE
                + colorama.Fore.LIGHTGREEN_EX
                + "]> "
                + colorama.Fore.RESET
            )
        else:
            self.prompt = "cli32 [" + pwd + "]> "

    def __error(self, msg):

        if self.color:
            print("\n" + colorama.Fore.LIGHTRED_EX + msg + colorama.Fore.RESET + "\n")
        else:
            print("\n" + msg + "\n")

    def __connect(self, port):

        debug(f"MpFileShell __connect() {port=}")
        try:
            self.__disconnect()

            if self.reset:
                print("Hard resetting device ...")
            if self.caching:
                self.fe = MpFileExplorerCaching(port, self.reset)
            else:
                self.fe = MpFileExplorer(port, self.reset)
            print("Connected to %s" % self.fe.sysname)
            self.port = port        # Save the portname
            self.__set_prompt_path()
            return True
        except PyboardError as e:
            logging.error(e)
            self.__error(str(e))
        except ConError as e:
            logging.error(e)
            self.__error("Failed to open: %s" % port)
        except AttributeError as e:
            logging.error(e)
            self.__error("Failed to open: %s" % port)
        return False

    def __disconnect(self):

        debug("MpFileShell __disconnect()")
        if self.fe is not None:
            try:
                print(f"closing connection of {self.port}")
                self.fe.close()
                self.fe = None
                self.__set_prompt_path()
            except RemoteIOError as e:
                self.__error(str(e))

    def __is_open(self):
        if self.fe is None:
            self.__error("Not connected to device. Use 'open' first.")
            return False
        return True

    def __parse_file_names(self, args):

        tokens, rest = self.tokenizer.tokenize(args)

        if rest != "":
            self.__error("Invalid filename given: %s" % rest)
        else:
            return [token.value for token in tokens]
        return None

    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_exit(self, _args):
        """Exit this shell."""
        self.__disconnect()
        return True

    do_EOF = do_exit

    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_open(self, args) -> None:
        """open <TARGET>
        Open connection to device with given target. TARGET might be:

        - a serial port, e.g.       ttyUSB0, ser:/dev/ttyUSB0
        - a telnet host, e.g        tn:192.168.1.1 or tn:192.168.1.1,login,passwd
        - a websocket host, e.g.    ws:192.168.1.1 or ws:192.168.1.1,passwd
        """

        debug(f"do_open() {args=}")

        if not args:
            self.__error("Missing argument: <PORT>")
            return

        if (
            not args.startswith("ser:/dev/")
            and not args.startswith("ser:COM")
            and not args.startswith("tn:")
            and not args.startswith("ws:")
        ):

            if platform.system() == "Windows":
                args = "ser:" + args
            else:
                args = "ser:/dev/" + args

        _ret = self.__connect(args)

    @staticmethod
    def complete_open(*args):
        ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        return [i[5:] for i in ports if i[5:].startswith(args[0])]

    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_close(self, _args):
        """Close connection to device."""
        self.__disconnect()

    @cmd2.with_category(CMD_CAT_FILES)
    def do_ls(self, _args):
        """List remote files."""

        if self.__is_open():
            try:
                files = self.fe.ls(add_details=True)

                if self.fe.pwd() != "/":
                    files = [("..", "D")] + files

                print("\nRemote files in '%s':\n" % self.fe.pwd())

                for elem, elem_type in files:
                    if elem_type == "F":
                        if self.color:
                            print(
                                colorama.Fore.CYAN
                                + ("       %s" % elem)
                                + colorama.Fore.RESET
                            )
                        else:
                            print("       %s" % elem)
                    else:
                        if self.color:
                            print(
                                colorama.Fore.MAGENTA
                                + (" <dir> %s" % elem)
                                + colorama.Fore.RESET
                            )
                        else:
                            print(" <dir> %s" % elem)

                print("")

            except IOError as e:
                self.__error(str(e))

    @cmd2.with_category(CMD_CAT_FILES)
    def do_pwd(self, _args):
        """Print current remote directory."""
        if self.__is_open():
            print(self.fe.pwd())

    @cmd2.with_category(CMD_CAT_FILES)
    def do_cd(self, args):
        """cd <TARGET DIR>
        Change current remote directory to given target.
        """
        if not len(args):
            self.__error("Missing argument: <REMOTE DIR>")
        elif self.__is_open():
            try:
                s_args = self.__parse_file_names(args)
                if not s_args:
                    return
                elif len(s_args) > 1:
                    self.__error("Only one argument allowed: <REMOTE DIR>")
                    return

                self.fe.cd(s_args[0])
                self.__set_prompt_path()
            except IOError as e:
                self.__error(str(e))

    def complete_cd(self, *args):

        try:
            files = self.fe.ls(add_files=False)
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_FILES)
    def do_md(self, args):
        """md <TARGET DIR>
        Create new remote directory.
        """
        if not len(args):
            self.__error("Missing argument: <REMOTE DIR>")
        elif self.__is_open():
            try:
                s_args = self.__parse_file_names(args)
                if not s_args:
                    return
                if len(s_args) > 1:
                    self.__error("Only one argument allowed: <REMOTE DIR>")
                    return

                self.fe.md(s_args[0])
            except IOError as e:
                self.__error(str(e))

    @cmd2.with_category(CMD_CAT_FILES)
    def do_lls(self, statement):
        """List files in current local directory."""

        if len(statement.arg_list) == 1:
            folder = pathlib.Path(statement.arg_list[0])
        else:
            # folder = pathlib.Path(param.config["src"]["srcpath"])
            folder = esp32common.get_sourcefolder()

        if not folder.is_dir():
            print(f"Could not find folder {folder}")
            return

        files = folder.glob('*')
        debug(f"{files=}")
        print(f"\nLocal files in {folder}:\n")
        for f in files:
            debug(f"{f=}")
            if f.is_dir():
                if self.color:
                    print(
                        colorama.Fore.MAGENTA + (" <dir> %s" % str(f.name)) + colorama.Fore.RESET
                    )
                else:
                    print(" <dir> %s" % str(f.name))
        files = folder.glob('*')
        debug(f"{files=}")
        for f in files:
            debug(f"{f=}")
            if f.is_file():
                if self.color:
                    print(colorama.Fore.CYAN + ("       %s" % str(f.name)) + colorama.Fore.RESET)
                else:
                    print("       %s" % str(f.name))
        print("")

        # sourcefolder = pathlib.Path(param.config['src']['srcpath'])
        # if not sourcefolder.is_dir():
        #     self.perror(f"Could not find folder {sourcefolder}")
        #     return
        #
        # files = sorted(sourcefolder.glob('**/*'))
        # filenames = [f.name for f in files if f.is_file()]
        # for filename in filenames:
        #     print(f"{filename.strip()}\n")

    @cmd2.with_category(CMD_CAT_FILES)
    def do_lcd(self, statement):
        """lcd <TARGET DIR>
        Change current local directory to given target.
        """

        if len(statement.arg_list) == 1:
            folder = pathlib.Path(statement.arg_list[0])
        else:
            # folder = pathlib.Path(param.config["src"]["srcpath"])
            folder = esp32common.get_sourcefolder()

        if not folder.is_dir():
            print(f"Could not find new folder {folder}")
            return

        try:
            # os.chdir(folder)
            esp32common.set_sourcefolder(folder)
        except OSError as e:
            self.__error(str(e).split("] ")[-1])

    @staticmethod
    def complete_lcd(*args):
        dirs = [o for o in os.listdir(".") if os.path.isdir(os.path.join(".", o))]
        return [i for i in dirs if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_FILES)
    def do_lpwd(self, _args):
        """lpwd = Print current local directory."""

        # print(os.getcwd())
        print(esp32common.get_sourcefolder())


    @cmd2.with_category(CMD_CAT_FILES)
    def do_put(self, args):
        """put <LOCAL FILE> [<REMOTE FILE>]
        Upload local file. If the second parameter is given,
        its value is used for the remote file name. Otherwise the
        remote file will be named the same as the local file.
        """

        if not args:
            self.__error("Missing arguments: <LOCAL FILE> [<REMOTE FILE>]")

        elif self.__is_open():

            s_args = self.__parse_file_names(args)
            if not s_args:
                return
            elif len(s_args) > 2:
                self.__error(
                    "Only one ore two arguments allowed: <LOCAL FILE> [<REMOTE FILE>]"
                )
                return

            lfile_name = s_args[0]

            if len(s_args) > 1:
                rfile_name = s_args[1]
            else:
                rfile_name = lfile_name

            try:
                self.fe.put(lfile_name, rfile_name)
            except IOError as e:
                self.__error(str(e))

    @staticmethod
    def complete_put(*args):
        files = [o for o in os.listdir(".") if os.path.isfile(os.path.join(".", o))]
        return [i for i in files if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_FILES)
    def do_mput(self, statement):
        """mput <SELECTION REGEX>
        Upload all local files that match the given filemask.
        The remote files will be named the same as the local files.

        "mput" does not get directories, and it is not recursive.
        """

        if not statement.args:
            self.__error("Missing argument: <SELECTION REGEX>")
            return

        if not self.__is_open():
            debug("No connection open")
            return

        sourcefolder = esp32common.get_sourcefolder()
        debug(f"mput() {sourcefolder=}")
        pattern = statement.args
        debug(f"{pattern=}")

        try:
            self.fe.mput(sourcefolder, pattern, True)
        except IOError as e:
            self.__error(str(e))

    @cmd2.with_category(CMD_CAT_FILES)
    def do_get(self, statement):
        """get <REMOTE FILE> [<LOCAL FILE>].

        Download remote file. If the second parameter is given,
        its value is used for the local file name. Otherwise the
        locale file will be named the same as the remote file.
        """

        debug(f"do_get() {statement=}")

        if not statement.arg_list:
            self.__error("Missing arguments: <REMOTE FILE> [<LOCAL FILE>]")

        elif len(statement.arg_list) > 2:
            self.__error("Only one ore two arguments allowed: <REMOTE FILE> [<LOCAL FILE>]")

        elif self.__is_open():

            rfile_name = statement.arg_list[0]

            if len(statement.arg_list) > 1:
                lfile_name = statement.arg_list[1]
            else:
                sourcefolder = esp32common.get_sourcefolder()
                lfile_name = str(sourcefolder / rfile_name)
            try:
                debug(f"calling self.fe.get() {rfile_name=} {lfile_name=}")
                self.fe.get(rfile_name, lfile_name)
            except IOError as e:
                self.__error(str(e))

    @cmd2.with_category(CMD_CAT_FILES)
    def do_mget(self, statement):
        """mget <SELECTION REGEX>
        Download all remote files that match the given regular expression.
        The local files will be named the same as the remote files.

        The targetfolder will be the current sourcefolder (use 'lcd' to verify or change it)

        "mget" does not get directories, and it is not recursive.
        """

        if not statement.args:
            self.__error("Missing argument: <SELECTION REGEX>")

        elif self.__is_open():

            try:
                # Do not use the current working directory, like in this original code:
                # self.fe.mget(os.getcwd(), args, True)
                # Use the current sourecefolder instead
                targetfolder = esp32common.get_sourcefolder()
                debug(f"mget() {targetfolder=}")
                self.fe.mget(targetfolder, statement.args, True)
            except IOError as e:
                self.__error(str(e))

    def complete_get(self, *args):

        try:
            files = self.fe.ls(add_dirs=False)
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_FILES)
    def do_rm(self, args):
        """rm <REMOTE FILE or DIR>
        Delete a remote file or directory.

        Note: only empty directories could be removed.
        """

        if not len(args):
            self.__error("Missing argument: <REMOTE FILE>")
        elif self.__is_open():

            s_args = self.__parse_file_names(args)
            if not s_args:
                return
            elif len(s_args) > 1:
                self.__error("Only one argument allowed: <REMOTE FILE>")
                return

            try:
                self.fe.rm(s_args[0])
            except IOError as e:
                self.__error(str(e))
            except PyboardError:
                self.__error("Unable to send request to %s" % self.fe.sysname)

    @cmd2.with_category(CMD_CAT_FILES)
    def do_mrm(self, args):
        """mrm <SELECTION REGEX>
        Delete all remote files that match the given regular expression.

        "mrm" does not delete directories, and it is not recursive.
        """

        if not len(args):
            self.__error("Missing argument: <SELECTION REGEX>")

        elif self.__is_open():

            try:
                self.fe.mrm(args, True)
            except IOError as e:
                self.__error(str(e))

    def complete_rm(self, *args):

        try:
            files = self.fe.ls()
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_FILES)
    def do_cat(self, statement):
        """cat <REMOTE FILE>
        Print the contents of a remote file.
        """

        # if not len(args):
        #     self.__error("Missing argument: <REMOTE FILE>")
        # elif self.__is_open():
        #
        #     s_args = self.__parse_file_names(args)
        #     if not s_args:
        #         return
        #     elif len(s_args) > 1:
        #         self.__error("Only one argument allowed: <REMOTE FILE>")
        #         return
        #
        #     try:
        #         print(self.fe.gets(s_args[0]))
        #     except IOError as e:
        #         self.__error(str(e))

        filename = statement.args
        if not len(filename):
            self.__error("Missing argument: <REMOTE FILE>")
            return

        # Use a temporary folder to save the device file in.
        # Using 'with', it will be cleaned up after this 'function'
        # is completed
        with tempfile.TemporaryDirectory() as temp_dir:

            local_filename = os.path.join(temp_dir, os.path.basename(filename))
            debug(f"do_cat() temporary local_filename is {local_filename}")

            debug(f"Retrieving {filename}")
            try:
                self.fe.get(filename, local_filename)
            except IOError as e:
                self.__error(str(e))
                return

            # Open the file in the temporary folder, read it and
            # print the contents.
            with open(local_filename, "r") as f:
                s = f.read()
                print(s)
            print()

    complete_cat = complete_get

    @cmd2.with_category(CMD_CAT_RUN)
    def do_exec(self, args):
        """exec <STATEMENT>
        Execute a Python statement on remote.
        """

        def data_consumer(data):
            data = str(data.decode("utf-8"))
            sys.stdout.write(data.strip("\x04"))

        if not len(args):
            self.__error("Missing argument: <STATEMENT>")
        elif self.__is_open():

            try:
                self.fe.exec_raw_no_follow(args + "\n")
                ret = self.fe.follow(None, data_consumer)

                if len(ret[-1]):
                    self.__error(ret[-1].decode("utf-8"))

            except IOError as e:
                self.__error(str(e))
            except PyboardError as e:
                self.__error(str(e))

    @cmd2.with_category(CMD_CAT_FILES)
    def do_run(self, statement):
        """Run the given local file on the connected device"""

        debug(f"{statement=}")
        filename = statement.arg_list[0]

        sourcefolder = esp32common.get_sourcefolder()
        localfile = sourcefolder.joinpath(filename)

        with open(localfile, 'r') as f:
            code = f.read()

        python_script = code.split("\n")
        print(python_script)

        # @todo: Send the python file contents:
        # if not self.repl:
        #     self.toggle_repl(None)
        # if self.repl and self.connection:
        #     self.connection.send_commands(python_script)

    do_start = do_run  # Create an alias

    @cmd2.with_category(CMD_CAT_RUN)
    def do_repl(self, _args):
        """repl = Enter Micropython REPL."""

        import serial

        ver = serial.VERSION.split(".")

        if int(ver[0]) < 2 or (int(ver[0]) == 2 and int(ver[1]) < 7):
            self.__error(
                "REPL needs PySerial version >= 2.7, found %s" % serial.VERSION
            )
            return

        if self.__is_open():

            if self.repl is None:

                from mp.term import Term

                self.repl = Term(self.fe.con)

                if platform.system() == "Windows":
                    self.repl.exit_character = chr(0x11)
                else:
                    self.repl.exit_character = chr(0x1D)

                self.repl.raw = True
                self.repl.set_rx_encoding("UTF-8")
                self.repl.set_tx_encoding("UTF-8")

            else:
                self.repl.serial = self.fe.con

            pwd = self.fe.pwd()
            self.fe.teardown()
            self.repl.start()

            if self.repl.exit_character == chr(0x11):
                print("\n*** Exit REPL with Ctrl+Q ***")
            else:
                print("\n*** Exit REPL with Ctrl+] ***")

            try:
                self.repl.join(True)
            except Exception:
                pass

            self.repl.console.cleanup()

            if self.caching:
                # Clear the file explorer cache so we can see any new files.
                self.fe.cache = {}

            self.fe.setup()
            try:
                self.fe.cd(pwd)
            except RemoteIOError as e:
                # Working directory does not exist anymore
                self.__error(str(e))
            finally:
                self.__set_prompt_path()
            print("")

    @cmd2.with_category(CMD_CAT_RUN)
    def do_mpyc(self, args):
        """mpyc <LOCAL PYTHON FILE>
        Compile a Python file into byte-code by using mpy-cross (which needs to be in the path).
        The compiled file has the same name as the original file but with extension '.mpy'.
        """

        if not len(args):
            self.__error("Missing argument: <LOCAL FILE>")
            return

        s_args = self.__parse_file_names(args)
        if not s_args:
            return
        elif len(s_args) > 1:
            self.__error("Only one argument allowed: <LOCAL FILE>")
            return

        sourcedir = esp32common.get_sourcefolder()
        sourcefile = sourcedir.joinpath(s_args[0])
        if not pathlib.Path(sourcefile).is_file():
            self.__error(f"Could not find {sourcefile}")
            return

        try:
            self.fe.mpy_cross(sourcefile)
        except IOError as e:
            self.__error(str(e))

    @staticmethod
    def complete_mpyc(*args):
        files = [
            o
            for o in os.listdir(".")
            if (os.path.isfile(os.path.join(".", o)) and o.endswith(".py"))
        ]
        return [i for i in files if i.startswith(args[0])]

    @cmd2.with_category(CMD_CAT_RUN)
    def do_putc(self, statement):
        """mputc <LOCAL PYTHON FILE> [<REMOTE FILE>]
        Compile a Python file into byte-code by using mpy-cross (which needs to be in the
        path) and upload it. The compiled file has the same name as the original file but
        with extension '.mpy' by default.
        """

        if not self.__is_open():
            self.__error(f"No connection is open")
            return

        if len(statement.arg_list) != 2:
            self.__error(
                "Only one ore two arguments allowed: <LOCAL FILE> [<REMOTE FILE>]"
            )
            return

        sourcedir = esp32common.get_sourcefolder()
        sourcefile = sourcedir.joinpath(statement.arg_list[0])
        if not pathlib.Path(sourcefile).is_file():
            self.__error(f"Could not find {sourcefile}")
            return

        if len(statement.arg_list) > 1:
            rfile_name = statement.arg_list[1]
        else:
            rfile_name = (
                sourcefile[: sourcefile.rfind(".")]
                if "." in sourcefile
                else sourcefile
            ) + ".mpy"

        _, tmp = tempfile.mkstemp()

        debug(f"putc() {sourcefile=}, {tmp=}")

        try:
            self.fe.mpy_cross(src=sourcefile, dst=tmp)
            self.fe.put(tmp, rfile_name)
        except IOError as e:
            self.__error(str(e))

        try:
            os.unlink(tmp)
        except PermissionError as err:
            # @todo: Figure out what is causing the access problem
            debug(f"ERROR: Cannot unlink {tmp=}, {err}")

    complete_putc = complete_mpyc

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_edit(self, statement):
        """Edit a file on the remote device.

        First check if the file is actually there.
        If so, get it as a local file.
        Edit it, and put it back when it was changed.
        """

        filename = statement.args

        # Use a temporary folder to save the device file in.
        # Using 'with', it will be cleaned up after this 'function'
        # is completed
        with tempfile.TemporaryDirectory() as temp_dir:

            local_filename = os.path.join(temp_dir, os.path.basename(filename))
            debug(f"{local_filename=}")

            print(f"Retrieving {filename}")
            try:
                self.fe.get(filename, local_filename)
            except IOError as e:
                self.__error(str(e))
                return

            # Determine the current state, so we can see if the file has
            # been changed later. If so, we know to write it back.
            oldstat = os.stat(local_filename)

            # Determine the editor, and edit the file in the tempoarary folder
            # editor = pathlib.Path("C:/Program Files/Notepad++/notepad++.exe")
            editor = pathlib.Path(
                r"C:\Users\HenkA\AppData\Local\Programs\Microsoft VS Code\Code.exe"
            )
            editor = param.config["editor"]["exe"]
            cmdstr = f'"{editor}" "{local_filename}"'
            esp32common.local_run(cmdstr)

            # What is the new state?
            newstat = os.stat(local_filename)

            # If the state has been changed, the file contents might be modified, and
            # it has to be written back to the connected device.
            if oldstat != newstat:
                print(f"Updating {filename}")
                try:
                    self.fe.put(local_filename, filename)
                except IOError as e:
                    self.__error(str(e))
                    print("ERROR:", str(e))
            else:
                debug(f"{local_filename} was not modified")

    @cmd2.with_category(CMD_CAT_FILES)
    def do_ledit(self, statement):
        """Locally edit a file in the local source folder on the PC.

        If it is an absolute path is given, then use the absolute path.
        If not, then handle the filename as part of the defined micropython source folder
        """

        debug(f"edit {statement=}")
        filename = statement.args  # Just the raw argument string

        # If the given filename is not absolute, then assume it is located
        # in the current micropython sourcefolder
        if not pathlib.Path(filename).is_absolute():
            sourcefolder = esp32common.get_sourcefolder()
            sourcefile = sourcefolder.joinpath(filename)
        else:
            sourcefile = filename

        # editor = pathlib.Path("C:/Program Files/Notepad++/notepad++.exe")
        # editor = pathlib.Path(
        #     r"C:\Users\HenkA\AppData\Local\Programs\Microsoft VS Code\Code.exe"
        # )
        editor = param.config["editor"]["exe"]
        cmdstr = f'"{editor}" "{sourcefile}"'
        esp32common.local_run(cmdstr)

    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_echo(self, statement):
        """Just print the given text back.

        Can be used for debugging purposes
        """
        print(statement)

    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_cls(self, _statement):
        """Clear the screen.
        """
        os.system("cls")

    # ===========================================================================
    @cmd2.with_category(CMD_CAT_FILES)
    def do_sync(self, statement):
        """Copy all python files (Sync) from the source folder to the connected device.

        Examples:
            * sync
            * sync c:/temp/upython_files

        If no foldername is given, then implicitly the internal source
        folder will be used.

        """

        debug(f"do_sync {statement=}")

        if len(statement.arg_list) == 1:
            sourcefolder = pathlib.Path(statement.arg_list[0])
        else:
            sourcefolder = pathlib.Path(param.config["src"]["srcpath"])

        if not sourcefolder.is_dir():
            print(f"Could not find folder {sourcefolder}")
            return

        # files = [e for e in sourcefolder.iterdir() if e.is_file()]
        # for filename in files:
        #     print(filename)

        for filename in sourcefolder.glob("*.py"):
            print(f"Syncing {filename}")
            # out, err = esp32common.put(str(filename), str(filename))
            try:
                self.fe.put(filename, filename)
            except IOError as e:
                self.__error(str(e))


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--command",
        help="execute given commands (separated by ;)",
        default=None,
        nargs="*",
    )
    parser.add_argument(
        "-s", "--script", help="execute commands from file", default=None
    )
    parser.add_argument(
        "-n",
        "--noninteractive",
        help="non interactive mode (don't enter shell)",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--nocolor", help="disable color", action="store_true", default=False
    )
    parser.add_argument(
        "--nocache", help="disable cache", action="store_true", default=False
    )

    parser.add_argument("--logfile", help="write log to file", default=None)
    parser.add_argument(
        "--loglevel",
        help="loglevel (CRITICAL, ERROR, WARNING, INFO, DEBUG)",
        default="INFO",
    )

    parser.add_argument(
        "--reset",
        help="hard reset device via DTR (serial connection only)",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "-o",
        "--open",
        help="directly opens board",
        metavar="BOARD",
        action="store",
        default=None,
    )
    parser.add_argument(
        "board", help="directly opens board", nargs="?", action="store", default=None
    )

    args = parser.parse_args()
    debug(f"{args=}")

    logformat = "%(asctime)s\t%(levelname)s\t%(message)s"

    if args.logfile is not None:
        logging.basicConfig(format=logformat, filename=args.logfile, level=args.loglevel)
    else:
        logging.basicConfig(format=logformat, level=logging.CRITICAL)

    logging.info("Micropython File Shell v%s started" % version.FULL)
    logging.info(
        "Running on Python %d.%d using PySerial %s"
        % (sys.version_info[0], sys.version_info[1], serial.VERSION)
    )

    mpfs = MpFileShell(not args.nocolor, not args.nocache, args.reset)

    if args.open is not None:
        debug("args.open is not None")
        if args.board is None:
            if not mpfs.do_open(args.open):
                return 1
        else:
            print(
                "Positional argument ({}) takes precedence over --open.".format(
                    args.board
                )
            )
    if args.board is not None:
        debug("if args.board is not None")
        mpfs.do_open(args.board)

    if not args.board:
        debug("if not args.board")
        # Try to find a suitable port and open it
        port, desc = esp32common.get_active_comport()
        print(f"Automatic trying to use {port=}")
        mpfs.do_open(port)

    if args.command is not None:
        debug("args.command is not None")
        for acmd in " ".join(args.command).split(";"):
            debug(f"{acmd=}")
            scmd = acmd.strip()
            if len(scmd) > 0 and not scmd.startswith("#"):
                mpfs.onecmd(scmd)
                # alternatively:
                # mpfs.onecmd_plus_hooks("{} {}".format(args.command, " ".join(args.command_args)))
                # sys.exit(0)

    elif args.script is not None:
        debug("elif args.script is not None")

        if platform.system() == "Windows":
            mpfs.use_rawinput = True

        f = open(args.script, "r")
        script = ""

        for line in f:

            sline = line.strip()

            if len(sline) > 0 and not sline.startswith("#"):
                script += sline + "\n"

        if sys.version_info < (3, 0):
            sys.stdin = io.StringIO(script.decode("utf-8"))
        else:
            sys.stdin = io.StringIO(script)

        mpfs.intro = ""
        mpfs.prompt = ""

    if not args.noninteractive:
        debug("if not args.interactive")
        try:
            debug("Entering cmdloop")
            mpfs.cmdloop()
        except KeyboardInterrupt:
            print("keyboard interrupt")


if __name__ == "__main__":

    import lib.helper
    lib.helper.clear_debug_window()

    sys.exit(main())
