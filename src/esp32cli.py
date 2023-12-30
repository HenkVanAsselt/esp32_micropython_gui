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
import time
import textwrap

# 3rd party imports
import cmd2  # type: ignore

# import mpremote.main
from cmd2 import (
    Bg,
    Fg,
    style,
)
from cmd2 import with_argparser
import colorama
import serial  # type: ignore
import keyboard

# Local imports
import param  # type: ignore

# from mp import version
# from mp.conbase import ConError
# from mp.mpfexp import MpFileExplorer
# from mp.mpfexp import MpFileExplorerCaching
# from mp.mpfexp import RemoteIOError
# from mp.pyboard import PyboardError

# from mp.tokenizer import Tokenizer
import esp32common  # type: ignore
from lib.helper import debug, dumpArgs, debug_indent, debug_unindent
import webrepl  # type: ignore
import esp32flash # type: ignore

from local_mpremote import main as mpremote

config = mpremote.load_user_config()
mpremote.prepare_command_expansions(config)


# -----------------------------------------------------------------------------
def must_have_port(method):
    """A decorator which tests if we are actally connected to a device.
    :param method: The method used.
    """

    @functools.wraps(method)
    def _impl(self, *method_args, **method_kwargs):
        if param.port_str:
            # print('Connected')
            return method(self, *method_args, **method_kwargs)
        else:
            print("ERROR: No port defined")
            return False

    return _impl


# -----------------------------------------------------------------------------
def available_binfiles(folder) -> list:
    """Get a list of available micropython bin files.

    :param folder: Folder to look into
    :returns: List with avaialble bin files
    """

    if not folder.is_dir():
        print(f"Error: Could not find folder {folder}")
        return []

    available_files = folder.glob("*.bin")
    return list(available_files)


# -----------------------------------------------------------------------------
def put(local_filename, remote_filename=""):
    """Copy the given local file to the connected device.

    :param local_filename: File on the PC
    :param remote_filename: Destination file on the device

    If no remote_filename is given, the same name of the sourcefile will
    be used.
    """

    if not pathlib.Path(local_filename).is_absolute():
        sourcefolder = esp32common.get_sourcefolder()
        local_filename = str(sourcefolder / local_filename)

    if not remote_filename:
        # If no destination filename was given, use the same name as the source, but only the basic filename.
        # This also implies it will be written to the root.
        remote_filename = pathlib.Path(local_filename).name

    ret = mpremote.main(
        ["connect", param.port_str, "cp", local_filename, ":" + remote_filename]
    )
    return ret


# -----------------------------------------------------------------------------
def get(remote_filename, local_filename=""):
    """Get file from device to local PC."""

    if local_filename:
        localfile = local_filename
        # If this is not an absolute path, then make sure the file is stored
        # in the current sourecefolder.
        if not pathlib.Path(localfile).is_absolute():
            sourcefolder = esp32common.get_sourcefolder()
            localfile = str(sourcefolder / localfile)
    else:
        # If no PC filename was given, use the same name as the remote file,
        # and make sure the file will be stored in the current source folder.
        sourcefolder = esp32common.get_sourcefolder()
        localfile = str(sourcefolder / remote_filename)

    ret = mpremote.main(
        ["connect", param.port_str, "cp", ":" + remote_filename, localfile]
    )
    return ret


# -----------------------------------------------------------------------------
def repl(reboot=False, ctrlc=False) -> None:
    """Start the Micropython REPL.

    :param reboot: soft reboot the device after the REPL is started with CTRL+D
    :param ctrlc: Interrupt the running program with CTRL+C
    """

    def do_reboot():
        """Press CTRL+D twice.
        """
        debug("Sending CTRL+D twice")
        keyboard.press_and_release("ctrl+d")
        time.sleep(0.1)
        keyboard.press_and_release("ctrl+d")
        time.sleep(0.1)

    def do_ctrlc():
        """Press CTRL+D and then CTRL+C twice.
        """
        debug("Sending CTRL+D and then CTRL+C twice")
        keyboard.press_and_release("ctrl+d")  # First soft reboot
        time.sleep(0.1)
        keyboard.press_and_release("ctrl+c")  # Then interrupt the boot process
        time.sleep(0.1)
        keyboard.press_and_release("ctrl+c")  # Twice
        time.sleep(0.1)

    # If required, perform a soft reboot of the connected device by sending CTRL+D
    if reboot:
        keyboard.call_later(do_reboot, args=(), delay=0.2)

    # If required, interrupt the running program with CTRL+C
    if ctrlc:
        keyboard.call_later(do_ctrlc, args=(), delay=0.2)

    mpremote.main(["connect", param.port_str, "repl"])


# -------------------------------------------------------------------------
def softreset() -> None:
    """Soft reset the device, should be equivalent with CTRL+D in repl."""

    command = """
         import machine
         machine.soft_reset()
    """

    command = textwrap.dedent(command)
    ret = mpremote.main(["connect", param.port_str, "exec", command])
    print(ret)


# -------------------------------------------------------------------------
def get_ip() -> str:
    """Get wlan ip address of connected device.

    :returns: The IP address
    """

    command = """
         from network import WLAN
         wlan=WLAN()
         print(wlan.ifconfig()[0])
    """

    command = textwrap.dedent(command)
    ret = mpremote.main(["connect", param.port_str, "exec", command])
    debug(f"{ret=}")
    return ret.strip()

# # -----------------------------------------------------------------------------
# def write_flash_with_binfile(comport="COM5", binfile=None) -> bool:
#     """Write flash of connected device with given binfile.
#
#     :param comport: port to use
#     :param binfile: file to write
#     :returns: True on success, False in case of an error
#     """
#
#     # Check if we can find the esptool executable
#     esptool = pathlib.Path("../bin/esptool.exe")
#     if not esptool.is_file():
#         print(f"Error: Could not find {str(esptool)}")
#         return False
#
#     print(f"Trying to write flash with {binfile}")
#     cmdstr = f'"{esptool}" --chip esp32 --port {comport}: --baud 460800 write_flash -z 0x1000 "{binfile}"'
#     debug(f"{cmdstr=}")
#
#     if param.is_gui:
#         param.worker.run_command(cmdstr)
#         while param.worker.active:
#             # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
#             loop = QEventLoop()
#             QTimer.singleShot(250, loop.quit)
#             loop.exec_()
#         return True
#
#     # If we are here, then this was not the gui version, and have to run
#     # this external command in a different way
#     ret = esp32common.local_run(cmdstr)
#     return ret


# =============================================================================
class ESPShell(cmd2.Cmd):
    """ESP32 Shell class."""

    # Define the help categories
    CMD_CAT_CONNECTING = "Connections"
    CMD_CAT_FILES = "Files and folders"
    CMD_CAT_EDIT = "Edit settings"
    CMD_CAT_WLAN = "WLAN related functions"
    CMD_CAT_DEBUG = "Debug and test"
    CMD_CAT_REBOOT = "Reboot related commands"
    CMD_CAT_RUN = "Execution commands"
    CMD_CAT_REPL = "REPL related functions"

    def __init__(
        self, color=False, caching=False, reset=False, autoconnect=True, port=""
    ):
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

        debug(f"In ESPShell.__init__() {autoconnect=}")

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
        self.foreground_color = "yellow"

        # # Make echo_fg settable at runtime
        # self.add_settable(
        #     cmd2.Settable(
        #         "foreground_color",
        #         str,
        #         "Foreground color to use with echo command",
        #         self,
        #         choices=fg.colors(),
        #     )
        # )

        # if self.port and autoconnect:
        #     debug(f"Automatic trying to use {port=}")
        #     ret = self.__connect(f"ser:{self.port}")
        #     print(f"{ret=}")

    # -------------------------------------------------------------------------
    def __intro(self) -> None:
        """Show the cmd intro."""

        if self.color:
            self.intro = (
                "\n"
                # + colorama.Fore.GREEN
                # + "** Micropython File Shell v%s, sw@kaltpost.de ** " % version.FULL
                + colorama.Fore.RESET
                + "\n"
            )
        else:
            self.intro = (
                # "\n** Micropython File Shell v%s, sw@kaltpost.de **\n" % version.FULL
                ""
            )

        # self.intro += "-- Running on Python %d.%d using PySerial %s --\n" % (
        #     sys.version_info[0],
        #     sys.version_info[1],
        #     serial.VERSION,
        # )

    # -------------------------------------------------------------------------
    def __set_prompt_path(self) -> None:
        """Set the shell prompt."""

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
    def __error(self, msg) -> None:
        """Show the error message."""

        if self.color:
            print("\n" + colorama.Fore.LIGHTRED_EX + msg + colorama.Fore.RESET + "\n")
        else:
            print("\n" + msg + "\n")

    # -------------------------------------------------------------------------
    @staticmethod
    def do_version(_args) -> None:
        """Print the micropython version, running on the connected device."""

        command = "print(uos.uname().release)"
        ret = mpremote.main(["connect", param.port_str, "exec", command])
        version = ret.decode("utf-8")
        print(f"Micropython version {version}")

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_exit(self, _args):
        """Exit this shell."""
        return True

    do_EOF = do_exit

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    @dumpArgs
    def do_ls(self, statement):
        """List remote files."""

        cmds = ["connect", param.port_str, statement.raw]
        debug(f"do_ls() {cmds=}")
        mpremote.main(["connect", param.port_str, statement.raw])

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
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

        mpremote.main(["connect", param.port_str, "mkdir", statement.arg_list[0]])

    do_mkdir = do_md  # Create an alisas

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rd(self, statement):
        """rd <TARGET DIR> or rmdir <TARGET DIR>.

        Remove the given folder/directory
        """

        debug(f"do_rd {statement=}")

        if not statement.arg_list:
            self.__error("Missing argument: <REMOTE DIR>")
            return

        if len(statement.arg_list) != 1:
            self.__error("Only one argument allowed: <REMOTE DIR>")
            return

        mpremote.main(["connect", param.port_str, "rmdir", statement.arg_list[0]])

    do_rmdir = do_rd  # Create an alisas

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

    do_ldir = do_lls  # Create an alias

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
            self.__error(str(e).rsplit("] ", maxsplit=1)[-1])

    # @staticmethod
    # def complete_lcd(*args):
    #     dirs = [o for o in os.listdir(".") if os.path.isdir(os.path.join(".", o))]
    #     return [i for i in dirs if i.startswith(args[0])]

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_lpwd(self, _args):
        """Print current local source directory."""

        sourcefolder = esp32common.get_sourcefolder()
        print(sourcefolder)

    # -------------------------------------------------------------------------
    put_parser = argparse.ArgumentParser()
    put_parser.add_argument("srcfile", help="Source file on the computer")
    put_parser.add_argument(
        "dstfile", nargs="?", default="", help="Optional destination name"
    )

    @with_argparser(put_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_put(self, statement):
        """put <srcfile> [<dstfile>].

        Upload local file.
        If the second parameter is given, its value is used for the remote file name.
        Else, the remote file will be named the same as the local file.
        """

        debug(f"do_put {statement=}")
        put(statement.srcfile, statement.dstfile)

    # # -------------------------------------------------------------------------
    # mput_parser = argparse.ArgumentParser()
    # mput_parser.add_argument(
    #     "filemask", help="filemask, like *.py or even * for all files"
    # )
    #
    # @with_argparser(mput_parser)
    # @cmd2.with_category(CMD_CAT_FILES)
    # def do_mput(self, statement):
    #     """Upload all local files that match the given filemask.
    #
    #     The remote files will be named the same as the local files.
    #     Note "mput" does not upload folders, and it is not recursive.
    #     """
    #
    #     sourcefolder = esp32common.get_sourcefolder()
    #     debug(f"mput() {sourcefolder=}")
    #     debug(f"{statement.filemask=}")
    #
    #     try:
    #         self.fe.mput(sourcefolder, statement.filemask, True)
    #     except IOError as e:
    #         self.__error(str(e))

    # -------------------------------------------------------------------------
    get_parser = argparse.ArgumentParser()
    get_parser.add_argument("remotefile", help="File on connected device")
    get_parser.add_argument(
        "localfile", nargs="?", default="", help="Optional local destination name"
    )

    @with_argparser(get_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_get(self, statement):
        """get <REMOTE FILE> [<LOCAL FILE>].

        Download the given remote file.
        If the PC destination is given, its value is used for the local file name.
        If it is not an absolute path, it will be placed in the current source folder.
        Else, the locale file will be named the same as the remote file.
        """

        debug(f"do_get() {statement=}")
        get(statement.remotefile, statement.localfile)

        # remotefile = statement.remotefile
        #
        # if statement.localfile:
        #     localfile = statement.localfile
        #     # If this is not an absolute path, then make sure the file is stored
        #     # in the current sourecefolder.
        #     if not pathlib.Path(localfile).is_absolute():
        #         sourcefolder = esp32common.get_sourcefolder()
        #         localfile = str(sourcefolder / localfile)
        # else:
        #     # If no PC filename was given, use the same name as the remote file,
        #     # and make sure the file will be stored in the current source folder.
        #     sourcefolder = esp32common.get_sourcefolder()
        #     localfile = str(sourcefolder / remotefile)
        #
        # # # Now, get and store the remote file.
        #
        # mpremote.main(["connect", param.port_str, "cp", ':'+remotefile, localfile])

    # # -------------------------------------------------------------------------
    # mget_parser = argparse.ArgumentParser()
    # mget_parser.add_argument(
    #     "filemask", help="filemask, like *.py or even * for all files"
    # )
    #
    # @with_argparser(mget_parser)
    # @cmd2.with_category(CMD_CAT_FILES)
    # def do_mget(self, statement):
    #     """Download all remote files that match the filemask.
    #
    #     The local files will be named the same as the remote files.
    #
    #     The targetfolder will be the current sourcefolder (use 'lcd' to verify or change it)
    #
    #     .. note:: :py:func:`mget` does not get directories, and it is not recursive.
    #
    #     Makes use of :py:func:`get`
    #     """
    #     local_sourcefolder = esp32common.get_sourcefolder()
    #     debug(f"mget() {local_sourcefolder=}")
    #
    #     try:
    #         self.fe.mget(local_sourcefolder, statement.filemask, True)
    #     except IOError as e:
    #         self.__error(str(e))

    # -------------------------------------------------------------------------
    rm_parser = argparse.ArgumentParser()
    rm_parser.add_argument(
        "filename", help="name of the file to remove from the connected device"
    )

    @with_argparser(rm_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_rm(self, statement):
        """rm <REMOTE FILE>.

        Remove a remote file.
        """

        mpremote.main(["connect", param.port_str, "rm", statement.filename])

    # # -------------------------------------------------------------------------
    # mrm_parser = argparse.ArgumentParser()
    # mrm_parser.add_argument(
    #     "filemask", help="filemask, like *.py or even * for all files"
    # )
    #
    # @with_argparser(mrm_parser)
    # @cmd2.with_category(CMD_CAT_FILES)
    # def do_mrm(self, statement):
    #     """Delete all remote files that match the given fnmatch mask.
    #
    #     Note: "mrm" does not delete directories, and it is not recursive.
    #     """
    #
    #     try:
    #         self.fe.mrm(statement.filemask, True)
    #     except IOError as e:
    #         self.__error(str(e))

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_cleanfs(self, _statement):
        """Clean the filesystem of the connected device.

        Will delete all files and folders on the device.
        """

        directory = "/"

        # Build a script to walk an entire directory structure and delete every
        # file and subfolder.  This is tricky because MicroPython has no os.walk
        # or similar function to walk folders, so this code does it manually
        # with recursion and changing directories.  For each directory it lists
        # the files and deletes everything it can, i.e. all the files.  Then
        # it lists the files again and assumes they are directories (since they
        # couldn't be deleted in the first pass) and recursively clears those
        # subdirectories.  Finally when finished clearing all the children the
        # parent directory is deleted.

        command = """
             try:
                 import os
             except ImportError:
                 import uos as os
             def rmdir(directory):
                 os.chdir(directory)
                 for f in os.listdir():
                     try:
                         os.remove(f)
                     except OSError:
                         pass
                 for f in os.listdir():
                     rmdir(f)
                 os.chdir('..')
                 os.rmdir(directory)
             rmdir('{0}')
         """.format(
            directory
        )

        command = textwrap.dedent(command)
        mpremote.main(["connect", param.port_str, "exec", command])

    # -------------------------------------------------------------------------
    cat_parser = argparse.ArgumentParser()
    cat_parser.add_argument("filename", help="name of the file to show")

    @with_argparser(cat_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_cat(self, statement):
        """Print the contents of a remote file."""

        mpremote.main(["connect", param.port_str, "cat", statement.filename])

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_RUN)
    def do_exec(self, statement):
        """Execute a single Python statement on the remote device.

        Examples::

            exec blinky.blink()
            exec print(uos.listdir())
            exec print(uos.getcwd())
            exec print(uos.uname())
        """

        # print(f"{statement=}")
        mpremote.main(["connect", param.port_str, "exec", statement.args])

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_RUN)
    def do_getname(self, _statement):
        """Get name and os version from connected device.

        :returns: tuple with 5 fields
        for example
        (sysname='esp32', nodename='esp32', release='1.18.0', version='v1.18 on 2022-01-17', machine='ESP32 module with ESP32')
        """

        command = """
             import os
             print(os.uname())
        """
        command = textwrap.dedent(command)

        ret = mpremote.main(["connect", param.port_str, "exec", command])
        ret = ret.strip()
        if ret.startswith(b"(") and ret.endswith(b")"):
            ret = ret[1:-1]
        t = ret.split(b",")
        print(40*'-')
        for s in t:
            print(s.strip().decode("utf-8"))
        print(40 * '-')

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_RUN)
    def do_eval(self, statement):
        """Execute a single Python expression on the remote device.

        Simple example: eval 1+2
        """

        mpremote.main(["connect", param.port_str, "eval", statement.args])

    # -------------------------------------------------------------------------
    execfile_parser = argparse.ArgumentParser()
    execfile_parser.add_argument("srcfile", help="Source file on the computer to run on the device")

    @with_argparser(execfile_parser)
    @cmd2.with_category(CMD_CAT_RUN)
    def do_execfile(self, statement):
        """Execute a local python file on the remote device."""

        debug(f"{statement=}")
        put(statement.srcfile)

        filename = statement.srcfile
        if filename.endswith(".py"):
            filename = filename[:-3]

        command = f"""
             import {filename}
        """
        command = textwrap.dedent(command)

        _ret = mpremote.main(["connect", param.port_str, "exec", command])

    # -------------------------------------------------------------------------
    run_parser = argparse.ArgumentParser()
    run_parser.add_argument("srcfile", help="Source file on the computer")

    @with_argparser(run_parser)
    @cmd2.with_category(CMD_CAT_RUN)
    def do_run(self, statement):
        """Run the given local file on the connected device."""

        debug(f"{statement=}")

        filename = statement.srcfile
        if filename.endswith(".py"):
            filename = filename[:-3]

        command = f"""
             import {filename}
             # {filename}.main()
        """
        command = textwrap.dedent(command)

        _ret = mpremote.main(["connect", param.port_str, "exec", command])

    do_start = do_run  # Create an alias

    # -------------------------------------------------------------------------
    repl_parser = argparse.ArgumentParser()
    repl_parser.add_argument(
        "-r",
        "--reboot",
        action="store_true",
        help="Soft-reboot the device after the REPL connection is made.",
    )
    repl_parser.add_argument(
        "-c",
        "--ctrlc",
        action="store_true",
        help="First soft reboot, and then interrupt the boot process.",
    )

    @with_argparser(repl_parser)
    @cmd2.with_category(CMD_CAT_REPL)
    def do_repl(self, statement):
        """Enter Micropython REPL over serial connection."""

        debug(f"{statement=}")
        # self.start_repl(with_softreboot=statement.reboot, with_ctrlc=statement.ctrlc)

        repl(statement.reboot, statement.ctrlc)

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
            debug(f"Retrieving {filename=} as {local_filename=}")
            print(f"Retrieving {filename}")
            mpremote.main(
                ["connect", param.port_str, "cp", ":" + filename, local_filename]
            )
            if not os.path.isfile(local_filename):
                print(f"Error: Could not find {local_filename}")

            # Determine the current state, so we can see if the file has
            # been changed later. If so, we know to write it back.
            oldstat = os.stat(local_filename)

            # Determine the editor, and edit the file in the tempoarary folder
            # editor = pathlib.Path("C:/Program Files/Notepad++/notepad++.exe")
            # editor = pathlib.Path(r"C:\Users\HenkA\AppData\Local\Programs\Microsoft VS Code\Code.exe")
            editor = param.config["editor"]["exe"]
            cmdstr = f'"{editor}" "{local_filename}"'
            esp32common.run_program(cmdstr)

            # What is the new state?
            newstat = os.stat(local_filename)

            # If the state has been changed, the file contents might be modified, and
            # it has to be written back to the connected device.
            if oldstat != newstat:
                print(f"Updating {filename}")
                mpremote.main(
                    ["connect", param.port_str, "cp", local_filename, ":" + filename]
                )
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
        esp32common.run_program(cmdstr)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_DEBUG)
    def do_echo(self, statement):
        """Just print the given text back.

        Can be used for debugging purposes
        """

        # print(statement)
        # self.poutput(style(statement, fg=Fg.foreground_color))
        self.poutput(style(statement))

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
        "-s",
        "--start",
        action="store_true",
        help="Start REPL and softreboot the device after all files are synced.",
    )

    @with_argparser(sync_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_sync(self, statement):
        """Copy all python files (Sync) from the source folder to the connected device.

        Examples:
            * sync
            * sync -s or sync --start

        If no foldername is given, then implicitly the internal source folder will be used.
        Does not support subfolders (yet).

        """

        debug(f"do_sync {statement=}")
        debug_indent("sync progress")

        sourcefolder = esp32common.get_sourcefolder()

        if not sourcefolder.is_dir():
            print(f"Could not find folder {sourcefolder}")
            return

        print(f'Syncing all files from sourcefolder "{sourcefolder}" to device')
        for filename in sourcefolder.glob("*"):
            debug(f"{filename=}")
            print(f" *  {filename}")
            # self.stdout.flush()
            if filename.is_file():
                try:
                    rfile_name = pathlib.Path(filename).name
                    mpremote.main(
                        [
                            "connect",
                            param.port_str,
                            "cp",
                            str(filename),
                            ":" + rfile_name,
                        ]
                    )
                except IOError as e:
                    self.__error(str(e))
            else:
                print(f"cannot sync subolder {filename} (yet)")
        print("\nSync completed")
        debug_unindent()

        if statement.start:
            print("Restarting device.")
            # All files are synced. Go to REPL mode and restart the device.
            if param.is_gui:
                # First change to repl mode.
                param.gui_mainwindow.change_to_repl_mode(None)
                # Then send a CTRL+D to softreset the device
                keyboard.press_and_release("ctrl+d")
            else:
                repl(reboot=True)

    # -------------------------------------------------------------------------
    flash_parser = argparse.ArgumentParser()

    flash_parser.add_argument(
        "-f",
        "--binfile",
        # "binfile",
        default="",
        help="Micropython binfile to flash on the device",
    )

    flash_parser.add_argument(
        "-n",
        "--filenumber",
        # "filenumber",
        default="",
        help="Filenumber of the Micropython binfile to flash on the device",
    )

    @with_argparser(flash_parser)
    @cmd2.with_category(CMD_CAT_FILES)
    def do_flash(self, statement):
        """flash the connected device with the given binfile.

        If no file is given, a list of avaialble binfiles in the binfile folder will be shown.
        """

        debug(f"{statement=}")

        # Check if we can find the esptool executable
        esptool = pathlib.Path("../bin/esptool.exe").resolve()
        if not esptool.is_file():
            print(f"Error1: Could not find {str(esptool)}")
            return

        # Try if this is a full path
        binfile = None
        if statement.binfile:
            binfile = pathlib.Path(statement.binfile)
            if not binfile.is_file():
                print(f"Error2: Could not find {str(binfile)}")
                return

        # Try to find the binfile in the binfile path
        folder = pathlib.Path(param.config["src"]["binpath"])
        available_files = available_binfiles(folder)
        for n, available_file in enumerate(available_files):
            print(f" {n} = {available_file}")

        if statement.filenumber:
            filenumber = int(statement.filenumber)
            print(f"{filenumber=}")
            if filenumber in range(len(available_files)):
                filename = available_files[filenumber]
                print(f"{filename=}")
                binfile = pathlib.Path(filename)
            else:
                print(f"Invalid {filenumber=} has been given")
                return

        if not binfile:
            print("No binfile determined")
            return

        if not binfile.is_file():
            print(f"Could not find {str(binfile)}")
            return

        # Erase the flash
        ret = esp32flash.erase_flash(self.port)
        if not ret:
            return

        # Program the binfile
        ret = esp32flash.write_flash_with_binfile(param.port_str, binfile)
        if not ret:
            return

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_FILES)
    def do_eraseflash(self, _statement) -> None:
        """Erase the flash memory of the connected device. This will also remove MicroPython itself !!!"""

        esp32flash.erase_flash(comport=param.port_str)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_REPL)
    def do_putty(self, _statement) -> None:
        """Start putty to connect to the device in REPL mode."""

        esp32common.putty(self.port)

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_WLAN)
    @cmd2.with_category(CMD_CAT_REPL)
    def do_webrepl(self, statement) -> None:
        """Start webrepl client.

        The IP address and portnumber can be given like::

            '192.168.178.149'   (which will use the default port 8266)
            '192.168.178.149:1111' (which will use portnumber 1111)

        The second argument should be the password to use.

        E.g.

            webrepl 192.168.192.169 henkiepenkie
        """

        if statement.arg_list:
            ip = statement.arg_list[0]
            if len(statement.arg_list) > 1:
                password = statement.arg_list[1]
            else:
                password = "abc123"
            # self.__disconnect() # Close the current connection over USB. @todo: figure out if this is neccessary.
            # webrepl.start_webrepl_html(ip)    # Open webrepl link over network/wifi
            url = webrepl.ip_to_url(ip)
            debug(f"{url=}")
            webrepl.start_webrepl_with_selenium(
                url, password=password
            )  # Open webrepl link over network/wifi
        else:
            print("No IP address for webrepl connection was given")
            return

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_WLAN)
    def do_getip(self, _statement) -> None:
        """Get IP address of the connected device."""

        ip = get_ip().strip()
        print(f"WLAN IP address: {ip}")

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_REBOOT)
    def do_softreset(self, _statement) -> None:
        """Soft reset the device, should be equivalent with CTRL+D in repl."""

        print("Performing a soft reset")
        softreset()

    # Create an alias
    do_softreboot = do_softreset

    # -------------------------------------------------------------------------
    @cmd2.with_category(CMD_CAT_REBOOT)
    def do_hardreset(self, _statement) -> None:
        """Hard reset the device, equivalent with pressing the external RESET button."""

        print("Performing a hard reset")

        command = """
             import machine
             machine.reset()
        """

        command = textwrap.dedent(command)
        ret = mpremote.main(["connect", param.port_str, "exec", command])
        debug(f"{ret=}")


# =============================================================================
def main():
    """main function of this module."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--command",
        help='execute given commands (between "" and separeted by ;)',
        default=None,
        # nargs="*",
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

    parser.add_argument(
        "-p",
        "--port",
        help="COM port",
        default="",
    )

    parser.add_argument(
        "--noautoconnect",
        help="Do not autoconnect to any COM port",
        action="store_true",
        default=False,
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

    args = parser.parse_args()
    debug(f"{args=}")

    logformat = "%(asctime)s\t%(levelname)s\t%(message)s"

    if args.logfile is not None:
        logging.basicConfig(
            format=logformat, filename=args.logfile, level=args.loglevel
        )
    else:
        logging.basicConfig(format=logformat, level=logging.CRITICAL)

    logging.info("Micropython HvA Shell")
    logging.info(
        "Running on Python %d.%d using PySerial %s"
        % (sys.version_info[0], sys.version_info[1], serial.VERSION)
    )

    if not args.port:
        port, description = esp32common.get_active_comport()
        if port:
            print(f"Detected {port=} {description=}")
            param.port_str = port
        else:
            print("No active port detected")
    else:
        param.port_str = args.port

    # In order to not confuse ESPshell, and performing commands mulitple times,
    # We will have to remove the commandline options here.
    if args.command:
        debug(f"Resetting remaining {sys.argv=}")
        sys.argv = sys.argv[:1]
        debug(f"It is now {sys.argv=}")

    espshell = ESPShell(
        not args.nocolor, not args.nocache, args.reset, args.noautoconnect
    )

    # if port:
    #     if not args.noautoconnect:
    #         print(f"Automatic trying to use {port=}")
    #         mpfs.do_open(port)

    if args.command is not None:
        debug("Script commands are given")
        debug(f"{args.command=}")
        cmd_list = args.command.split(";")
        for cmd in cmd_list:
            debug(f"{cmd=}")
            cmd = cmd.strip()
            if len(cmd) > 0 and not cmd.startswith("#"):
                espshell.onecmd(cmd)
                # alternatively:
                # mpfs.onecmd_plus_hooks("{} {}".format(args.command, " ".join(args.command_args)))
                # sys.exit(0)

    if args.script:
        debug(f"{args.script=}")

        if platform.system() == "Windows":
            espshell.use_rawinput = True

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

        espshell.intro = ""
        espshell.prompt = ""

    if not args.noninteractive:
        debug("Entering interactive mode.")
        try:
            espshell.cmdloop()
        except KeyboardInterrupt:
            print("keyboard interrupt")
    else:
        debug("Do not enter interactive loop and exit here")
        sys.exit(0)


# =============================================================================
if __name__ == "__main__":

    from lib import helper

    helper.clear_debug_window()

    sys.exit(main())
