"""Graphical User Interface to ESP32
"""

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
import io
import logging
import os
import platform
import sys
import tempfile
import pathlib
import functools


# 3rd party imports
import cmd2  # type: ignore
from cmd2 import fg
from cmd2 import with_argparser
import colorama
import serial
from PyQt5.Qt import QEventLoop, QTimer
import keyboard

# Local imports
import param
from mp import version
from mp.conbase import ConError
from mp.mpfexp import MpFileExplorer
from mp.mpfexp import MpFileExplorerCaching
from mp.mpfexp import RemoteIOError
from mp.pyboard import PyboardError
# from mp.tokenizer import Tokenizer
import esp32common
from lib.helper import debug, dumpFuncname, dumpArgs
import webrepl


# -----------------------------------------------------------------------------
def must_be_connected(method):
    """A decorator which tests if we are actally connected to a device.
    """
    @functools.wraps(method)
    def _impl(self, *method_args, **method_kwargs):
        if self.fe:
            # print('Connected')
            return method(self, *method_args, **method_kwargs)
        else:
            print("ERROR: Not connected")
            return False

    return _impl


# -----------------------------------------------------------------------------
def erase_flash(comport="COM5") -> bool:
    """Erase flash memory of the connected ESP32.

    :param comport: The name of the comport to use
    :returns: True on success, False in case of an error
    """

    # Check if we can find the esptool executable
    esptool = pathlib.Path("../bin/esptool.exe")
    if not esptool.is_file():
        print(f"Error: Could not find {str(esptool)}")
        return False

    print(f"Trying to erase flash over {comport=}")
    cmdstr = f'"{esptool}" --chip esp32 --port {comport}: erase_flash'
    if param.is_gui:
        try:
            param.worker.run_command(cmdstr)
            while param.worker.active:
                # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
                loop = QEventLoop()
                QTimer.singleShot(250, loop.quit)
                loop.exec_()
        except Exception as err:
            print(err)
            return False

    # else:
    ret = esp32common.local_run(cmdstr)
    return ret


# -----------------------------------------------------------------------------
def write_flash_with_binfile(comport="COM5", binfile=None) -> bool:
    """Write flash of connected device with given binfile.

    :param comport: port to use
    :param binfile: file to write
    :returns: True on success, False in case of an error
    """

    # Check if we can find the esptool executable
    esptool = pathlib.Path("../bin/esptool.exe")
    if not esptool.is_file():
        print(f"Error: Could not find {str(esptool)}")
        return False

    print(f"Trying to write flash with {binfile}")
    cmdstr = f'"{esptool}" --chip esp32 --port {comport}: --baud 460800 write_flash -z 0x1000 "{binfile}"'
    debug(f"{cmdstr=}")

    if param.is_gui:
        param.worker.run_command(cmdstr)
        while param.worker.active:
            # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
            loop = QEventLoop()
            QTimer.singleShot(250, loop.quit)
            loop.exec_()
        return True

    # If we are here, then this was not the gui version, and have to run
    # this external command in a different way
    ret = esp32common.local_run(cmdstr)
    return ret


# =============================================================================
class ESPShell(cmd2.Cmd):
    """ESP32 Shell class.
    """

    # Define the help categories
    CMD_CAT_CONNECTING = "Connections"
    CMD_CAT_FILES = "Files and folders"
    CMD_CAT_EDIT = "Edit settings"
    CMD_CAT_WLAN = "WLAN related functions"
    CMD_CAT_DEBUG = "Debug and test"
    CMD_CAT_REBOOT = "Reboot related commands"
    CMD_CAT_RUN = "Execution commands"
    CMD_CAT_REPL = "REPL related functions"

    def __init__(self, color=False, caching=False, reset=False, port=""):
        """Initialialize class ESPShell instance."""

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

        self.port = port  # Name of the COM port
        debug(f"In ESPShell.__init__() {self.port=}")
        self.fe = None
        self.repl_connection = None
        # self.tokenizer = Tokenizer()

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

        if self.port:
            debug(f"Automatic trying to use {port=}")
            self.__connect(f"ser:{self.port}")

    # -------------------------------------------------------------------------
    def __del__(self):
        """Delete will disconnect."""
        self.__disconnect()

    # -------------------------------------------------------------------------
    def __intro(self):
        """Show the cmd intro."""

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

    # -------------------------------------------------------------------------
    def __set_prompt_path(self):
        """Set the shell prompt.
        """

        if self.fe:
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

    # -------------------------------------------------------------------------
    def __error(self, msg):
        """Show the error message."""

        if self.color:
            print("\n" + colorama.Fore.LIGHTRED_EX + msg + colorama.Fore.RESET + "\n")
        else:
            print("\n" + msg + "\n")

    # -------------------------------------------------------------------------
    @dumpArgs
    def __connect(self, port) -> bool:
        """Open MpFileExplorer connection over the given port.

        :param port: port to use
        :returns: True on success, False on error
        """
        print(f"Connecting with MpFileExplorer to device over {port=}")
        # self.port = port  # Save the portname
        try:
            self.__disconnect()

            if self.reset:
                print("Hard resetting device ...")
            if self.caching:
                self.fe = MpFileExplorerCaching(port, self.reset)
            else:
                self.fe = MpFileExplorer(port, self.reset)
            print("\nConnected to %s\n" % self.fe.sysname)
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

    # -------------------------------------------------------------------------
    @dumpFuncname
    def __disconnect(self) -> None:
        """Close current fe (file-exeplorer) connection.
        """

        debug("Terminating MpFileExplorer")
        if self.fe:
            try:
                self.fe.close()
                self.fe = None
                self.__set_prompt_path()
            except RemoteIOError as e:
                self.__error(str(e))
        else:
            debug("ERROR: No self.fe (MpFileExplorer) active, so cannot close it")

    # -------------------------------------------------------------------------
    def __is_open(self) -> bool:
        """Test if MpFileExplorer is active.

        :returns: True if active, False if not
        """
        if not self.fe:
            self.__error("Not connected to device. Use 'open' first.")
            return False
        return True

    # -------------------------------------------------------------------------
    def remote_exec(self, command: str) -> bytes:
        """Execute a single Python statement on the remote device.

        :param command: Command to execute
        :returns: The result as a bytestring

        Examples::

            exec blinky.blink()
            exec print(uos.listdir())
            exec print(uos.getcwd())
            exec print(uos.uname())
        """

        def data_consumer(_data: bytes) -> None:
            """Handle the incoming data.

            By default, it just prints it.
            :param _data: Data to process
            """
            # debug(f"data_consumer({data=})")
            # data = str(data.decode("utf-8"))
            # sys.stdout.write(data.strip("\x04"))
            pass

        debug(f"{command=}")

        try:
            self.fe.exec_raw_no_follow(command + "\n")
            ret = self.fe.follow(None, data_consumer)
            # debug(f"in exec, {ret=}")
            if len(ret[-1]):
                self.__error(ret[-1].decode("utf-8"))
            # else
            return ret[0].strip()

        except IOError as e:
            self.__error(str(e))
        except PyboardError as e:
            self.__error(str(e))

        return b""

    # -------------------------------------------------------------------------
    def get_ip(self) -> str:
        """Get wlan ip address of connected device.

        :returns: The IP address
        """
        try:
            self.remote_exec("from network import WLAN")
            self.remote_exec("wlan=WLAN()")
            ret = self.remote_exec("print(wlan.ifconfig()[0])")
            ip = ret.decode("utf-8")
            return ip
        except Exception as err:
            debug(f"Exception {err=}. Could not retrieve WLAN ip address")
            return ""

    # -------------------------------------------------------------------------
    def softreset(self) -> None:
        """Soft reset the device, should be equivalent with CTRL+D in repl.
        """
        print("performing a soft reset")
        self.remote_exec("import machine")
        self.remote_exec("machine.soft_reset()")

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_exit(self, _args):
        """Exit this shell."""
        self.__disconnect()
        return True

    do_EOF = do_exit

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_open(self, statement) -> None:
        """Open connection to device with given target.

        TARGET might be:

        - a serial port, e.g.       ttyUSB0, ser:/dev/ttyUSB0
        - a telnet host, e.g        tn:192.168.1.1 or tn:192.168.1.1,login,passwd
        - a websocket host, e.g.    ws:192.168.1.1 or ws:192.168.1.1,passwd
        """

        if isinstance(statement, str):
            args = statement
        else:
            args = statement.args

        debug(f"do_open() {args=}")
        self.port = args

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
                portstr = "ser:" + args  # e.g. "ser:COM5"
            else:
                portstr = "ser:/dev/" + args
        else:
            portstr = args

        ret = self.__connect(portstr)
        debug(f"{ret=}")

    # @staticmethod
    # def complete_open(*args):
    #     ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    #     return [i[5:] for i in ports if i[5:].startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_close(self, _args):
        """Close connection to device."""
        self.__disconnect()
        print("File Explorer connection has been closed.")

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    @must_be_connected
    def do_ls(self, _args):
        """List remote files."""

        # if not self.__is_open():
        #     print("No connectionn is open")
        #     return

        try:
            files = self.fe.ls(add_details=True)
            debug(f"ls {files=}")

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

        except IOError as err:
            debug(f"Exception: {err}")
            self.__error(str(err))

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    @must_be_connected
    def do_pwd(self, _args):
        """Print current remote directory."""

        # if not self.__is_open():
        #     print("No connectionn is open")
        #     return

        print(self.fe.pwd())

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    @must_be_connected
    def do_cd(self, statement) -> None:
        """cd <TARGET DIR>.

        Change remote directory on the target
        """

        if not statement.arg_list:
            self.__error("Missing argument: <REMOTE DIR>")
            return

        if len(statement.arg_list) != 1:
            self.__error("Only one argument allowed: <REMOTE DIR>")
            return

        # if not self.__is_open():
        #     self.__error("Not connected")
        #     return

        try:
            self.fe.cd(statement.args)
            self.__set_prompt_path()
        except IOError as e:
            self.__error(str(e))

    # def complete_cd(self, *args):
    #
    #     try:
    #         files = self.fe.ls(add_files=False)
    #     except Exception:
    #         files = []
    #
    #     return [i for i in files if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    @must_be_connected
    def do_md(self, statement):
        """md <TARGET DIR> or mkdir <TARGET DIR>.

        Create new remote directory.
        """

        debug(f"do_md {statement=}")

        if not statement.arg_list:
            self.__error("Missing argument: <REMOTE DIR>")
            return

        if len(statement.arg_list) != 1:
            self.__error("Only one argument allowed: <REMOTE DIR>")
            return

        # if not self.__is_open():
        #     self.__error("Not connected")
        #     return

        try:
            self.fe.md(statement.args)
        except IOError as e:
            self.__error(str(e))

    do_mkdir = do_md  # Create an alisas

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_lls(self, statement):
        """List files in current local directory."""

        # If a foldername is given, use that. The default is the current defined source folder
        if len(statement.arg_list) == 1:
            folder = pathlib.Path(statement.arg_list[0])
        else:
            folder = esp32common.get_sourcefolder()

        if not folder.is_dir():
            print(f"Could not find local folder {folder}")
            return

        # First print the directories
        files = folder.glob("*")  # Note: this returns an iterator, not just a list.
        print(f'\nLocal files in sourcefolder "{folder}":\n')
        for f in files:
            if f.is_dir():
                if self.color:
                    print(
                        colorama.Fore.MAGENTA
                        + (" <dir> %s" % str(f.name))
                        + colorama.Fore.RESET
                    )
                else:
                    print(" <dir> %s" % str(f.name))

        # Then print the files
        files = folder.glob("*")  # Note: this returns an iterator, not just a list.
        for f in files:
            if f.is_file():
                if self.color:
                    print(
                        colorama.Fore.CYAN
                        + ("       %s" % str(f.name))
                        + colorama.Fore.RESET
                    )
                else:
                    print("       %s" % str(f.name))

        print("")

    # -------------------------------------------------------------------------
    lcd_parser = argparse.ArgumentParser()
    lcd_parser.add_argument(
        "srcfolder", nargs="?", default="", help="Folder with microPython source files"
    )

    @with_argparser(lcd_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_lcd(self, statement):
        """Change current PC source folder to the given folder."""

        if not statement.srcfolder:
            current_folder = esp32common.get_sourcefolder()
            print("No new sourcefolder was given.")
            print(f"Current sourecefolder is {current_folder}")
            return

        foldername = pathlib.Path(statement.srcfolder)
        if not foldername.is_dir():
            print(f"Folder {foldername} does not exist.")
            print("You have to create it first.")
            return

        try:
            esp32common.set_sourcefolder(foldername)
        except OSError as e:
            self.__error(str(e).split("] ")[-1])

    # @staticmethod
    # def complete_lcd(*args):
    #     dirs = [o for o in os.listdir(".") if os.path.isdir(os.path.join(".", o))]
    #     return [i for i in dirs if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_lpwd(self, _args):
        """Print current local source directory.
        """

        sourcefolder = esp32common.get_sourcefolder()
        print(sourcefolder)

    # -------------------------------------------------------------------------
    put_parser = argparse.ArgumentParser()
    put_parser.add_argument("srcfile", help="Source file on the computer")
    put_parser.add_argument(
        "dstfile", nargs="?", default="", help="Optional destination name"
    )

    @with_argparser(put_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_put(self, statement):
        """put <srcfile> [<dstfile>].

        Upload local file.
        If the second parameter is given, its value is used for the remote file name.
        Otherwise the remote file will be named the same as the local file.
        """

        debug(f"do_put {statement=}")

        local_filename = statement.srcfile

        if not pathlib.Path(local_filename).is_absolute():
            sourcefolder = esp32common.get_sourcefolder()
            local_filename = str(sourcefolder / local_filename)

        if statement.dstfile:
            # Use the given destination filename.
            rfile_name = statement.dstfile
        else:
            # If no destination filename was given, use the same name as the source, but only the basic filename.
            # This also implies it will be written to the root.
            rfile_name = pathlib.Path(statement.srcfile).name

        # Perform the upload.
        try:
            self.fe.put(local_filename, rfile_name)
        except IOError as e:
            self.__error(str(e))

    # @staticmethod
    # def complete_put(*args):
    #     files = [o for o in os.listdir(".") if os.path.isfile(os.path.join(".", o))]
    #     return [i for i in files if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    mput_parser = argparse.ArgumentParser()
    mput_parser.add_argument(
        "filemask", help="filemask, like *.py or even * for all files"
    )

    @with_argparser(mput_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_mput(self, statement):
        """Upload all local files that match the given filemask.

        The remote files will be named the same as the local files.
        Note "mput" does not upload folders, and it is not recursive.
        """

        sourcefolder = esp32common.get_sourcefolder()
        debug(f"mput() {sourcefolder=}")
        debug(f"{statement.filemask=}")

        try:
            self.fe.mput(sourcefolder, statement.filemask, True)
        except IOError as e:
            self.__error(str(e))

    # -------------------------------------------------------------------------
    get_parser = argparse.ArgumentParser()
    get_parser.add_argument("srcfile", help="Source file on connected device")
    get_parser.add_argument(
        "dstfile", nargs="?", default="", help="Optional destination name"
    )

    @with_argparser(get_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_get(self, statement):
        """get <REMOTE FILE> [<LOCAL FILE>].

        Download the given remote file.
        If the PC destination is given, its value is used for the local file name.
        If it is not an absolute path, it will be placed in the current source folder.
        Otherwise the locale file will be named the same as the remote file.
        """

        debug(f"do_get() {statement=}")

        remote_filename = statement.srcfile

        if statement.dstfile:
            local_filename = statement.dstfile
            # If this is not an absolute path, then make sure the file is stored
            # in the current sourecefolder.
            if not pathlib.Path(local_filename).is_absolute():
                sourcefolder = esp32common.get_sourcefolder()
                local_filename = str(sourcefolder / local_filename)
        else:
            # If no PC filename was given, use the same name as the sourcefile,
            # and make sure the file will be stored in the current source folder.
            sourcefolder = esp32common.get_sourcefolder()
            local_filename = str(sourcefolder / remote_filename)

        # Now, get and store the remote file.
        try:
            debug(f"calling self.fe.get() {remote_filename=} {local_filename=}")
            self.fe.get(remote_filename, local_filename)
        except IOError as e:
            debug(str(e))
            self.__error(str(e))

    # -------------------------------------------------------------------------
    mget_parser = argparse.ArgumentParser()
    mget_parser.add_argument(
        "filemask", help="filemask, like *.py or even * for all files"
    )

    @with_argparser(mget_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_mget(self, statement):
        """Download all remote files that match the filemask.

        The local files will be named the same as the remote files.

        The targetfolder will be the current sourcefolder (use 'lcd' to verify or change it)

        .. note:: :py:func:`mget` does not get directories, and it is not recursive.

        Makes use of :py:func:`get`
        """
        local_sourcefolder = esp32common.get_sourcefolder()
        debug(f"mget() {local_sourcefolder=}")

        try:
            self.fe.mget(local_sourcefolder, statement.filemask, True)
        except IOError as e:
            self.__error(str(e))

    # -------------------------------------------------------------------------
    rm_parser = argparse.ArgumentParser()
    rm_parser.add_argument(
        "filename", help="name of the file to remove from the connected device"
    )

    @with_argparser(rm_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rm(self, statement):
        """rm <REMOTE FILE or DIR>.

        Remove/delete a remote file or directory.

        Note: only empty directories can be removed.
        """

        try:
            self.fe.rm(statement.filename)
        except IOError as e:
            self.__error(str(e))
        except PyboardError:
            self.__error("Unable to send request to %s" % self.fe.sysname)

    # -------------------------------------------------------------------------
    mrm_parser = argparse.ArgumentParser()
    mrm_parser.add_argument(
        "filemask", help="filemask, like *.py or even * for all files"
    )

    @with_argparser(mrm_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_mrm(self, statement):
        """Delete all remote files that match the given fnmatch mask.

        Note: "mrm" does not delete directories, and it is not recursive.
        """

        try:
            self.fe.mrm(statement.filemask, True)
        except IOError as e:
            self.__error(str(e))

    # def complete_rm(self, *args):
    #
    #     try:
    #         files = self.fe.ls()
    #     except Exception:
    #         files = []
    #
    #     return [i for i in files if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_cleanfs(self, _statement):
        """Clean the filesystem of the connected device.

        Will delete all files and folders on the device.
        """

        print("cleanfs is not implemented yet.")
        pass

        # print('Cleaning the filesystem')
        # for name in files.ls(long_format=False):
        #     if force or name not in exclude_files:
        #         try:
        #             print(f"removing file {name}")
        #             files.rm(name)
        #         except (RuntimeError, PyboardError):
        #             try:
        #                 print(f"removing folder {name}")
        #                 files.rmdir(name)
        #             except (RuntimeError, PyboardError):
        #                 print('Unknown Error removing file {}'.format(name),
        #                       file=sys.stderr)

    # -------------------------------------------------------------------------
    cat_parser = argparse.ArgumentParser()
    cat_parser.add_argument("filename", help="name of the file to show")

    @with_argparser(cat_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_cat(self, statement):
        """Print the contents of a remote file."""

        remote_file = statement.filename

        # Use a temporary folder to save the device file in.
        # Using 'with', it will be cleaned up after this 'function'
        # is completed
        with tempfile.TemporaryDirectory() as temp_dir:

            tempfilename = os.path.join(temp_dir, os.path.basename(remote_file))
            debug(f"do_cat() temporary local_filename is {tempfilename}")

            debug(f"Retrieving {remote_file}")
            try:
                self.fe.get(remote_file, tempfilename)
            except IOError as e:
                self.__error(str(e))
                return

            # Open the file in the temporary folder, read it and
            # print the contents.
            with open(tempfilename, "r") as f:
                s = f.read()
                print(s)
            print()

    # -------------------------------------------------------------------------
    @must_be_connected
    @cmd2.with_category(CMD_CAT_RUN)
    def do_exec(self, statement):
        """Execute a single Python statement on the remote device.

        Examples::

            exec blinky.blink()
            exec print(uos.listdir())
            exec print(uos.getcwd())
            exec print(uos.uname())
        """

        self.remote_exec(statement.args)

    # -------------------------------------------------------------------------
    @must_be_connected
    @cmd2.with_category(CMD_CAT_RUN)
    def do_execfile(self, statement):
        """Execute a local python file on the remote device.
        """

        sourcefile = statement.args

        if not pathlib.Path(sourcefile).is_file():
            self.__error(f"Could not find {sourcefile}")
            return

        ret = self.fe.execfile(sourcefile).decode("utf8")
        print(f"execfile returned {ret=}")
        print(ret)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_RUN)
    def do_run(self, statement):
        """Run the given local file on the connected device."""

        debug(f"{statement=}")
        filename = statement.arg_list[0]

        sourcefolder = esp32common.get_sourcefolder()
        localfile = sourcefolder.joinpath(filename)
        debug(f"run() {localfile=}")

        with open(localfile, "r") as f:
            code = f.read()

        python_script = code.split("\n")
        debug(f"{python_script=}")

        print("run/start is not functional yet")

        # @todo: Send the python file contents:
        # if self.repl_connection and self.connection:
        #     self.connection.send_commands(python_script)

    do_start = do_run  # Create an alias

    # -------------------------------------------------------------------------
    repl_parser = argparse.ArgumentParser()
    repl_parser.add_argument(
        "-r", "--reboot", action='store_true', help="Soft-reboot the device after the REPL connection is made."
    )

    @with_argparser(repl_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_REPL)
    def do_repl(self, statement):
        """Enter Micropython REPL over serial connection.
        """

        if statement.reboot:
            self.start_repl(with_softreboot=True)
        else:
            self.start_repl(with_softreboot=False)

    # -------------------------------------------------------------------------
    def start_repl(self, with_softreboot=False) -> None:
        """Start the repl connection.
        """

        debug("=====")
        debug("start_repl()")
        if not self.repl_connection:

            debug("Importing mp.term Term")
            from mp.term import Term

            self.repl_connection = Term(self.fe.con)

            if platform.system() == "Windows":
                self.repl_connection.exit_character = chr(0x11)
            else:
                self.repl_connection.exit_character = chr(0x1D)

            debug(f"{self.repl_connection.exit_character=}")

            self.repl_connection.raw = True
            self.repl_connection.set_rx_encoding("UTF-8")
            self.repl_connection.set_tx_encoding("UTF-8")

        else:
            debug("Reusing self.fe.con")
            self.repl_connection.serial = self.fe.con

        # Save the current workdirectory of the device.
        saved_workdir = self.fe.pwd()
        debug(f"in do_repl, {saved_workdir=}")

        debug("Calling fe.teardown()")
        self.fe.teardown()

        debug("Calling repl.start()")
        self.repl_connection.start()
        if self.repl_connection.exit_character == chr(0x11):
            print("\n*** Exit REPL with Ctrl+Q ***")
        else:
            print("\n*** Exit REPL with Ctrl+] ***")

        # If required, perform a soft reboot of the connected device by sending CTRL+D
        if with_softreboot:
            # keyboard.write('\x04')
            keyboard.press_and_release('ctrl+d')

        try:
            debug("calling repl.join(True)")
            self.repl_connection.join(True)
        except Exception as err:
            debug(f"Exception: {err}")
            pass



        debug("-----")
        debug("Calling repl.console.cleanup()")
        self.repl_connection.console.cleanup()

        if self.caching:
            debug("Clearing the fe cache.")
            # Clear the file explorer cache so we can see any new files.
            self.fe.cache = {}

        debug("Calling self.fe.setup()")
        self.fe.setup()

        # Change back to the previous saved workfolder on the device
        try:
            debug(f"Trying to restore previous {saved_workdir=}")
            self.fe.cd(saved_workdir)
        except RemoteIOError as e:
            # Working directory does not exist anymore
            self.__error(str(e))
        finally:
            self.__set_prompt_path()
        print("")

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_RUN)
    def do_mpyc(self, statement):
        """mpyc <LOCAL PYTHON FILE>.
        Compile a Python file into byte-code by using mpy-cross (which needs to be in the path).
        The compiled file has the same name as the original file but with extension '.mpy'.
        """

        if not statement.arg_list:
            self.__error("Missing argument: <LOCAL FILE>")
            return

        if len(statement.arg_list) > 1:
            self.__error("Only 1 argument allowed")

        filename = statement.arg_list[0]

        sourcedir = esp32common.get_sourcefolder()
        sourcefile = sourcedir.joinpath(filename)
        if not pathlib.Path(sourcefile).is_file():
            self.__error(f"Could not find {sourcefile}")
            return

        try:
            self.fe.mpy_cross(sourcefile)
        except IOError as e:
            self.__error(str(e))

    # @staticmethod
    # def complete_mpyc(*args):
    #     files = [
    #         o
    #         for o in os.listdir(".")
    #         if (os.path.isfile(os.path.join(".", o)) and o.endswith(".py"))
    #     ]
    #     return [i for i in files if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_putc(self, statement):
        """mputc <LOCAL PYTHON FILE> [<REMOTE FILE>].
        Compile a Python file into byte-code by using mpy-cross (which needs to be in the
        path) and upload it. The compiled file has the same name as the original file but
        with extension '.mpy' by default.
        """

        if not self.__is_open():
            self.__error("No connection is open")
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
        debug(f"{sourcefile=}")

        if len(statement.arg_list) > 1:
            rfile_name = statement.arg_list[1]
            debug(f"1 {rfile_name=}")
        else:
            rfile_name = (
                sourcefile[: str(sourcefile).rfind(".")] if "." in sourcefile else sourcefile
            ) + ".mpy"
            debug(f"1 {rfile_name=}")

        _, tmp = tempfile.mkstemp()
        debug(f"{tmp=}")

        # debug(f"putc() {sourcefile=}, {tmp=}")

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

    # complete_putc = complete_mpyc

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_EDIT)
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
            # editor = pathlib.Path(r"C:\Users\HenkA\AppData\Local\Programs\Microsoft VS Code\Code.exe")
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

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_EDIT)
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

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_echo(self, statement):
        """Just print the given text back.

        Can be used for debugging purposes
        """
        print(statement)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_cls(self, _statement):
        """Clear the screen."""

        debug("do_cls()")
        if param.is_gui:
            pass  # This is implemented in esp32_gui_pyqt5.py in do_command()
        else:
            os.system("cls")

    # -------------------------------------------------------------------------
    sync_parser = argparse.ArgumentParser()
    sync_parser.add_argument(
        "-s", "--start", action='store_true', help="Start REPL and softreboot the device after all files are synced."
    )

    @with_argparser(sync_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_sync(self, statement):
        """Copy all python files (Sync) from the source folder to the connected device.

        Examples:
            * sync
            * sync --start

        If no foldername is given, then implicitly the internal source folder will be used.
        Does not support subfolders (yet).

        """

        debug(f"do_sync {statement=}")

        sourcefolder = esp32common.get_sourcefolder()

        if not sourcefolder.is_dir():
            print(f"Could not find folder {sourcefolder}")
            return

        print(f'Syncing all files from sourcefolder "{sourcefolder}" to device')
        for filename in sourcefolder.glob("*"):
            print(f" *  {filename}")
            if filename.is_file():
                try:
                    self.fe.put(filename, filename.name)
                except IOError as e:
                    self.__error(str(e))
            else:
                print(f"cannot sync subolder {filename} (yet)")

        if statement.start:
            if param.is_gui:
                param.gui_mainwindow.change_to_repl_mode(None)
                keyboard.press_and_release("ctrl+d")
            else:
                self.start_repl(with_softreboot=True)

    # -------------------------------------------------------------------------
    flash_parser = argparse.ArgumentParser()

    flash_parser.add_argument(
        "binfile",
        nargs="?",
        default="",
        help="Micropython binfile to flash on the device",
    )

    @with_argparser(flash_parser)
    @must_be_connected
    @cmd2.with_category(CMD_CAT_FILES)
    def do_flash(self, statement):
        """flash the connected device with the given binfile.

        If no file is given, a list of avaialble binfiles in the binfile folder will be shown.
        """

        # Check if we can find the esptool executable
        esptool = pathlib.Path("../bin/esptool.exe").resolve()
        if not esptool.is_file():
            print(f"Error: Could not find {str(esptool)}")
            return

        # Try if this is a full path
        binfile = pathlib.Path(statement.binfile)
        if not binfile.is_file():
            print(f"Error1: Could not find {str(binfile)}")
            # Try to find the binfile in the binfile path
            folder = pathlib.Path(param.config["src"]["binpath"])
            binfile = folder.joinpath(statement.binfile)
            if not binfile.is_file():
                print(f"Error2: Could not find {str(binfile)}")
                available_files = folder.glob("*.bin")
                print("Available files are:")
                for available_file in available_files:
                    print(f" * {available_file}")
                return
            print(f"Using {str(binfile)}")

        # Step 1 of 4: Close the current com port
        self.__disconnect()

        # Step 2 of 4: Erase the flash
        ret = erase_flash(self.port)
        if not ret:
            return

        # # Step 3 of 4: Program the binfile
        ret = write_flash_with_binfile(self.port, binfile)
        if not ret:
            return

        # Step 4 of 4: Open the com port again
        print(f"--- Connecting again to {self.port=}")
        self.do_open(self.port)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_eraseflash(self, _statement) -> None:
        """Erase the flash memory of the connected device.
        """

        erase_flash(comport=self.port)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_REPL)
    def do_putty(self, _statement) -> None:
        """Erase the flash memory of the connected device.
        """

        import time

        self.__disconnect()     # To free the COM port
        time.sleep(0.2)

        esp32common.putty(self.port)

        print(f"--- Connecting again to {self.port=}")
        self.do_open(self.port)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_WLAN)
    @cmd2.with_category(CMD_CAT_REPL)
    def do_webrepl(self, statement) -> None:
        """Start webrepl client.

        The IP address and portnumber can be given like::

            '192.168.178.149'   (which will use the default port 8266)
            '192.168.178.149:1111' (which will use portnumber 1111)
        """

        if statement.arg_list:
            ip = statement.arg_list[0]
            if len(statement.arg_list) > 1:
                password = statement.arg_list[1]
            else:
                password = "daan3006"
            # self.__disconnect() # Close the current connection over USB. @todo: figure out if this is neccessary.
            # webrepl.start_webrepl_html(ip)    # Open webrepl link over network/wifi
            url = webrepl.ip_to_url(ip)
            debug(f"{url=}")
            webrepl.start_webrepl_with_selenium(url, password=password)    # Open webrepl link over network/wifi
        else:
            print("No IP address for webrepl connection was given")
            return

    # -------------------------------------------------------------------------
    @must_be_connected
    @cmd2.with_category(CMD_CAT_WLAN)
    def do_getip(self, _statement) -> None:
        """Get IP address of the connected device.
        """

        ip = self.get_ip()
        print(ip)

    # -------------------------------------------------------------------------
    @must_be_connected
    @cmd2.with_category(CMD_CAT_REBOOT)
    def do_softreset(self, _statement) -> None:
        """Soft reset the device, should be equivalent with CTRL+D in repl.
        """

        self.softreset()
        # No __disconnect is neccessary here.

    # -------------------------------------------------------------------------
    @must_be_connected
    @cmd2.with_category(CMD_CAT_REBOOT)
    def do_hardreset(self, _statement) -> None:
        """Hard reset the device, equivalent with pressing the external RESET button.
        """

        self.remote_exec("import machine")
        self.remote_exec("machine.reset()")
        self.__disconnect()


# =============================================================================
def main():
    """main function of this module.
    """

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
        logging.basicConfig(
            format=logformat, filename=args.logfile, level=args.loglevel
        )
    else:
        logging.basicConfig(format=logformat, level=logging.CRITICAL)

    logging.info("Micropython File Shell v%s started" % version.FULL)
    logging.info(
        "Running on Python %d.%d using PySerial %s"
        % (sys.version_info[0], sys.version_info[1], serial.VERSION)
    )

    mpfs = ESPShell(not args.nocolor, not args.nocache, args.reset)

    if args.open is not None:
        debug("args.open is not None")
        if args.board is None:
            if not mpfs.do_open(args.open):
                return
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
        port, _description = esp32common.get_active_comport()
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


# =============================================================================
if __name__ == "__main__":

    from lib import helper

    helper.clear_debug_window()

    sys.exit(main())
