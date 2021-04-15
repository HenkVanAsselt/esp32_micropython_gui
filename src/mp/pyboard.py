"""
Pyboard REPL interface.

Also see: D:\\hva\\projects\\micropython\\installers\\Thonny\\thonny-3.3.6 sourcecode\\misc\\pyboard.py

"""

import sys
import time

from lib.helper import debug, dumpFuncname

try:
    stdout = sys.stdout.buffer
except AttributeError:
    # Python2 doesn't have buffer attr
    stdout = sys.stdout


def stdout_write_bytes(b: bytes) -> None:
    """Write the given bytestring to stdout.

    :param b: bytestring to write
    """
    b = b.replace(b"\x04", b"")
    stdout.write(b)
    stdout.flush()


class PyboardError(BaseException):
    """Does nothing.    """

    ...  # Could also have written 'pass' here.


class Pyboard:
    """Class Pyboard."""

    def __init__(self, conbase):
        """Intialize class Pyboard.

        :param conbase:
        """
        debug(f"Pyboard __init__ {conbase=}")
        self.use_raw_paste = False
        self.con = conbase

    def close(self):
        """Close Pyboard connection.
        """
        debug("Pyboard close()")
        if self.con is not None:
            self.con.close()

    # @dumpArgs
    def read_until(
            self,
            min_num_bytes: int,
            ending: bytes,
            timeout: float = 10.0,
            data_consumer=None,
    ):
        """Read from the port until one of the conditions is met.

        :param min_num_bytes: minimum number of bytes to read
        :param ending: end of the datastream to test on
        :param timeout: timeout
        :param data_consumer: callback function
        """

        data = self.con.read(min_num_bytes)
        # debug(f'read {data=}')
        if data_consumer:
            data_consumer(data)
        timeout_count = 0
        while True:
            if data.endswith(ending):
                break
            if self.con.inWaiting() > 0:
                new_data = self.con.read(1)
                # debug(f'read {new_data=}')
                data = data + new_data
                if data_consumer:
                    data_consumer(new_data)
                timeout_count = 0
            else:
                timeout_count += 1
                if timeout is not None and timeout_count >= 100 * timeout:
                    break
                time.sleep(0.01)
        debug(f'read_until returns "{data}"')
        return data

    @dumpFuncname
    def enter_raw_repl(self):
        """Pyboard enter raw repl."""

        time.sleep(0.5)  # allow some time for board to reset
        debug(r'self.con.write "\r\x03\x03"  (Ctrl-C twice)')
        self.con.write(b"\r\x03\x03")  # ctrl-C twice: interrupt any running program

        # flush input (without relying on serial.flushInput())
        n = self.con.inWaiting()
        while n > 0:
            self.con.read(n)
            n = self.con.inWaiting()

        if self.con.survives_soft_reset():
            debug(r'self.con.write "\r\x01"  (enter raw REPL)')
            self.con.write(b"\r\x01")  # ctrl-A: enter raw REPL
            data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n>", timeout=10)

            if not data.endswith(b"raw REPL; CTRL-B to exit\r\n>"):
                print(data)
                raise PyboardError("could not enter raw repl 1")

            debug(r'self.con.write "\x04"  (soft reset)')
            self.con.write(b"\x04")  # ctrl-D: soft reset
            data = self.read_until(1, b"soft reboot\r\n", timeout=10)
            if not data.endswith(b"soft reboot\r\n"):
                print(data)
                raise PyboardError("could not enter raw repl 2")

            # By splitting this into 2 reads, it allows boot.py to print stuff,
            # which will show up after the soft reboot and before the raw REPL.
            data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n", timeout=10)
            if not data.endswith(b"raw REPL; CTRL-B to exit\r\n"):
                print(data)
                raise PyboardError("could not enter raw repl 3")

        else:

            debug(r'self.con.write "\r\x01"  (enter raw REPL)')
            self.con.write(b"\r\x01")  # ctrl-A: enter raw REPL
            data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n", timeout=10)

            if not data.endswith(b"raw REPL; CTRL-B to exit\r\n"):
                print(data)
                raise PyboardError("could not enter raw repl 4")

    @dumpFuncname
    def exit_raw_repl(self):
        """Pyboard exit raw repl."""
        debug(r'self.con.write "\r\x02"  (ctrl-B: enter friendly REPL)')
        self.con.write(b"\r\x02")  # ctrl-B: enter friendly REPL

    def follow(self, timeout, data_consumer=None) -> tuple:
        """Wait for normal ouput.

        :param timeout: timeout
        :param data_consumer: callback function
        :returns: tuple of data and error output
        """
        # wait for normal output
        data = self.read_until(1, b"\x04", timeout=timeout, data_consumer=data_consumer)
        if not data.endswith(b"\x04"):
            raise PyboardError("timeout waiting for first EOF reception")
        data = data[:-1]

        # wait for error output
        data_err = self.read_until(1, b"\x04", timeout=timeout)
        if not data_err.endswith(b"\x04"):
            raise PyboardError("timeout waiting for second EOF reception")
        data_err = data_err[:-1]

        # return normal and error output
        return data, data_err

    def exec_raw_no_follow(self, command) -> None:
        """Pyboard execute raw command, no follow.

        :param command: command to execute
        :returns: Nothing
        """

        if isinstance(command, bytes):
            command_bytes = command
        else:
            command_bytes = bytes(command.encode("utf-8"))

        # check we have a prompt
        data = self.read_until(1, b">")
        if not data.endswith(b">"):
            raise PyboardError("could not enter raw repl 5")

        if self.use_raw_paste:
            # Try to enter raw-paste mode.
            self.con.write(b"\x05A\x01")
            data = self.con.read(2)
            if data == b"R\x00":
                # Device understood raw-paste command but doesn't support it.
                pass
            elif data == b"R\x01":
                # Device supports raw-paste mode, write out the command using this mode.
                return self.raw_paste_write(command_bytes)
            else:
                # Device doesn't support raw-paste, fall back to normal raw REPL.
                data = self.read_until(1, b"w REPL; CTRL-B to exit\r\n>")
                if not data.endswith(b"w REPL; CTRL-B to exit\r\n>"):
                    print(data)
                    raise PyboardError("could not enter raw repl")
            # Don't try to use raw-paste mode again for this connection.
            self.use_raw_paste = False

        # write string
        debug(f'self.con.write "{command_bytes}"')
        self.con.write(command_bytes)

        # Alternative for write string above, do it in chuncks of max 256 bytes.
        # Write command using standard raw REPL, 256 bytes every 10ms.
        # for i in range(0, len(command_bytes), 256):
        #     self.serial.write(command_bytes[i: min(i + 256, len(command_bytes))])
        #     time.sleep(0.01)

        # Terminate command
        debug(r'self.con.write "\r\x04"')
        self.con.write(b"\x04")

        # check if we could exec command
        data = self.read_until(2, b"OK", timeout=0.5)
        if data != b"OK":
            raise PyboardError("could not exec command (response: %r)" % data)

    def exec_raw(self, command, timeout=10, data_consumer=None) -> tuple:
        """Execute the given command.

        :param command: command to execute
        :param timeout: maximum allowed time.
        :param data_consumer: callback function.
        :returns: tuple of data and error output
        """
        self.exec_raw_no_follow(command)
        return self.follow(timeout, data_consumer)

    def eval(self, expression: str) -> str:
        """Evaluate and run the expression on the connected device and print the result.

        :param expression: the expression to evaluate
        :returns: The result of the code which ran on the connected device.
        """
        ret = self.exec_("print({})".format(expression))
        ret = ret.strip()
        return ret

    def exec_(self, command, data_consumer=None) -> str:
        """Execute the given command.

        :param command: command to execute
        :param data_consumer:
        :returns: The output
        """
        ret, ret_err = self.exec_raw(command, data_consumer=data_consumer)
        if ret_err:
            raise PyboardError("exception", ret, ret_err)
        return ret

    def execfile(self, filename) -> str:
        """Open a local python file and execute the contents.

        :param filename: the file to open end execute
        :returns: the output
        """
        with open(filename, "rb") as f:
            pyfile = f.read()
        return self.exec_(pyfile)

    def raw_paste_write(self, command_bytes: bytes) -> None:
        """Write the given commands using the raw-paste method.

        :param command_bytes: The command to execute
        :returns: Nothing
        """
        # Read initial header, with window size.
        data = self.con.read(2)
        window_size = data[0] | data[1] << 8
        window_remain = window_size

        # Write out the command_bytes data.
        i = 0
        while i < len(command_bytes):
            while window_remain == 0 or self.con.inWaiting():
                data = self.con.read(1)
                if data == b"\x01":
                    # Device indicated that a new window of data can be sent.
                    window_remain += window_size
                elif data == b"\x04":
                    # Device indicated abrupt end.  Acknowledge it and finish.
                    self.con.write(b"\x04")
                    return
                else:
                    # Unexpected data from device.
                    raise PyboardError(
                        "unexpected read during raw paste: {}".format(data)
                    )
            # Send out as much data as possible that fits within the allowed window.
            b = command_bytes[i: min(i + window_remain, len(command_bytes))]
            self.con.write(b)
            window_remain -= len(b)
            i += len(b)

        # Indicate end of data.
        self.con.write(b"\x04")

        # Wait for device to acknowledge end of data.
        data = self.read_until(1, b"\x04")
        if not data.endswith(b"\x04"):
            raise PyboardError("could not complete raw paste: {}".format(data))

    def get_time(self) -> int:
        """Get the time of the connected board.

        :returns: integer with the time
        """
        t = str(self.eval("pyb.RTC().datetime()").encode("utf-8"))[1:-1].split(", ")
        return int(t[4]) * 3600 + int(t[5]) * 60 + int(t[6])

    def fs_ls(self, src):
        """ls function, to be run on the connected device.

        :param src: The source folder
        :returns: Nothing
        """
        cmd = (
                "import uos\nfor f in uos.ilistdir(%s):\n"
                " print('{:12} {}{}'.format(f[3]if len(f)>3 else 0,f[0],'/'if f[1]&0x4000 else ''))"
                % (("'%s'" % src) if src else "")
        )
        self.exec_(cmd, data_consumer=stdout_write_bytes)

    def fs_cat(self, src: str, chunk_size: int = 256) -> None:
        """Show the contents of the file on the connected device.

        :param src: The file to cat.
        :param chunk_size: Show per xxx bytes
        :returns: Nothing
        """
        cmd = (
                "with open('%s') as f:\n while 1:\n"
                "  b=f.read(%u)\n  if not b:break\n  print(b,end='')" % (src, chunk_size)
        )
        self.exec_(cmd, data_consumer=stdout_write_bytes)

    def fs_get(self, src, dest, chunk_size=256):
        """Get a file.

        :param src:
        :param dest:
        :param chunk_size:
        :return:
        """
        import ast

        self.exec_("f=open('%s','rb')\nr=f.read" % src)
        with open(dest, "wb") as f:
            while True:
                data = bytearray()
                self.exec_(
                    "print(r(%u))" % chunk_size, data_consumer=lambda d: data.extend(d)
                )
                assert data.endswith(b"\r\n\x04")
                try:
                    data = ast.literal_eval(str(data[:-3], "ascii"))
                    if not isinstance(data, bytes):
                        raise ValueError("Not bytes")
                except (UnicodeError, ValueError) as e:
                    raise PyboardError(
                        "fs_get: Could not interpret received data: %s" % str(e)
                    )
                if not data:
                    break
                f.write(data)
        self.exec_("f.close()")

    def fs_put(self, src, dest, chunk_size=256):
        """Put a file.

        :param src:
        :param dest:
        :param chunk_size:
        :return:
        """
        self.exec_("f=open('%s','wb')\nw=f.write" % dest)
        with open(src, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                if sys.version_info < (3,):
                    self.exec_("w(b" + repr(data) + ")")
                else:
                    self.exec_("w(" + repr(data) + ")")
        self.exec_("f.close()")

    def fs_mkdir(self, dirname: str) -> None:
        """Make the given folder on the device.

        :param dirname: Name of the folder to create"""
        self.exec_("import uos\nuos.mkdir('%s')" % dirname)

    def fs_rmdir(self, dirname: str) -> None:
        """Remove directory.

        :param dirname: Directory to remove
        """
        self.exec_("import uos\nuos.rmdir('%s')" % dirname)

    def fs_rm(self, src: str) -> None:
        """Remove file.

        :param src: File to remove
        """
        self.exec_("import uos\nuos.remove('%s')" % src)


# in Python2 exec is a keyword so one must use "exec_"
# but for Python3 we want to provide the nicer version "exec"
setattr(Pyboard, "exec", Pyboard.exec_)
