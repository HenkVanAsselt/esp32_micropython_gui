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
import serial

# see if we could use the new Miniterm implementation
from serial.tools.miniterm import Miniterm, ConsoleBase, unichr
import os

from lib.helper import debug, dumpArgs, dumpFuncname

if os.name == "nt":  # noqa
    import codecs
    import sys
    import msvcrt
    import ctypes

    class Out(object):
        """file-like wrapper that uses os.write"""

        def __init__(self, fd):
            self.fd = fd

        def flush(self):
            pass

        def write(self, s):
            debug(f"Out.write {s=}")
            os.write(self.fd, s)

    class Console(ConsoleBase):
        fncodes = {
            ";": "\1bOP",  # F1
            "<": "\1bOQ",  # F2
            "=": "\1bOR",  # F3
            ">": "\1bOS",  # F4
            "?": "\1b[15~",  # F5
            "@": "\1b[17~",  # F6
            "A": "\1b[18~",  # F7
            "B": "\1b[19~",  # F8
            "C": "\1b[20~",  # F9
            "D": "\1b[21~",  # F10
        }
        navcodes = {
            "H": "\x1b[A",  # UP
            "P": "\x1b[B",  # DOWN
            "K": "\x1b[D",  # LEFT
            "M": "\x1b[C",  # RIGHT
            "G": "\x1b[H",  # HOME
            "O": "\x1b[F",  # END
            "R": "\x1b[2~",  # INSERT
            "S": "\x1b[3~",  # DELETE
            "I": "\x1b[5~",  # PGUP
            "Q": "\x1b[6~",  # PGDN
        }

        def __init__(self):
            super(Console, self).__init__()
            self._saved_ocp = ctypes.windll.kernel32.GetConsoleOutputCP()
            self._saved_icp = ctypes.windll.kernel32.GetConsoleCP()
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
            # ANSI handling available through SetConsoleMode since Windows 10 v1511
            # https://en.wikipedia.org/wiki/ANSI_escape_code#cite_note-win10th2-1
            # if platform.release() == '10' and int(platform.version().split('.')[2]) > 10586:
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            import ctypes.wintypes as wintypes

            if not hasattr(wintypes, "LPDWORD"):  # PY2
                wintypes.LPDWORD = ctypes.POINTER(wintypes.DWORD)
            SetConsoleMode = ctypes.windll.kernel32.SetConsoleMode
            GetConsoleMode = ctypes.windll.kernel32.GetConsoleMode
            GetStdHandle = ctypes.windll.kernel32.GetStdHandle
            mode = wintypes.DWORD()
            GetConsoleMode(GetStdHandle(-11), ctypes.byref(mode))
            if (mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING) == 0:
                SetConsoleMode(
                    GetStdHandle(-11),
                    mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
                )
                self._saved_cm = mode
            self.output = codecs.getwriter("UTF-8")(
                Out(sys.stdout.fileno()), "replace"
            )
            # the change of the code page is not propagated to Python, manually fix it
            sys.stderr = codecs.getwriter("UTF-8")(
                Out(sys.stderr.fileno()), "replace"
            )
            sys.stdout = self.output
            self.output.encoding = "UTF-8"  # needed for input

        def __del__(self):
            try:
                ctypes.windll.kernel32.SetConsoleOutputCP(self._saved_ocp)
            except AttributeError:
                pass
            try:
                ctypes.windll.kernel32.SetConsoleCP(self._saved_icp)
            except AttributeError:
                pass
            try:
                ctypes.windll.kernel32.SetConsoleMode(
                    ctypes.windll.kernel32.GetStdHandle(-11), self._saved_cm
                )
            except AttributeError:  # in case no _saved_cm
                pass

        @dumpFuncname
        def getkey(self):
            while True:
                z = msvcrt.getwch()
                debug(f"getkey() {z=}")
                if z == unichr(13):
                    debug(f"returning {unichr(10)}")
                    return unichr(10)
                elif z is unichr(0) or z is unichr(0xE0):
                    try:
                        code = msvcrt.getwch()
                        if z is unichr(0):
                            debug(f"returning {self.fncodes[code]=}")
                            return self.fncodes[code]
                        else:
                            debug(f"returning {self.navcodes[code]=}")
                            return self.navcodes[code]
                    except KeyError:
                        pass
                else:
                    debug(f"else, returning {z=}")
                    return z

        @dumpFuncname
        def cancel(self):
            # CancelIo, CancelSynchronousIo do not seem to work when using
            # getwch, so instead, send a key to the window with the console
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            ctypes.windll.user32.PostMessageA(hwnd, 0x100, 0x0D, 0)

    class Term(Miniterm):
        def __init__(self, serial_instance, echo=False, eol="crlf", filters=()):
            debug("Intializing Term()")
            self.console = Console()
            self.serial = serial_instance
            self.echo = echo
            self.raw = False
            self.input_encoding = "UTF-8"
            self.output_encoding = "UTF-8"
            self.eol = eol
            self.filters = filters
            self.update_transformations()
            self.exit_character = unichr(0x1D)  # GS/CTRL+]
            self.menu_character = unichr(0x14)  # Menu: CTRL+T
            self.alive = None
            self._reader_alive = None
            self.receiver_thread = None
            self.rx_decoder = None
            self.tx_decoder = None

else:
    Term = Miniterm
