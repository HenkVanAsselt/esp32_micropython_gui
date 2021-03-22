"""Micropython REPL over websocket class and functions.
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

import logging
import threading
import time
from collections import deque

import websocket

from mp.conbase import ConBase
from mp.conbase import ConError

from lib.helper import debug


# =============================================================================
class ConWebsock(ConBase, threading.Thread):
    """micropython REPL Websocket connection class
    """

    # -------------------------------------------------------------------------
    def __init__(self, ip, password):
        """Initialize micropython REPL over Websocket instance.

        :param ip: IP address of the device
        :param password: Password to use
        """

        debug(f"initializing repl over websocket. {ip=} {password=}")

        ConBase.__init__(self)
        threading.Thread.__init__(self)

        self.daemon = True

        self.fifo = deque()
        self.fifo_lock = threading.Lock()

        # websocket.enableTrace(logging.root.getEffectiveLevel() < logging.INFO)
        self.ws = websocket.WebSocketApp(
            "ws://%s:8266" % ip,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        debug(f"{self.ws=}")

        self.start()

        self.timeout = 5.0

        if b"Password:" in self.read(10, blocking=False):
            self.ws.send(password + "\r")
            if b"WebREPL connected" not in self.read(25, blocking=False):
                raise ConError()
        else:
            raise ConError()

        self.timeout = 1.0

        logging.info("websocket connected to ws://%s:8266" % ip)

    # -------------------------------------------------------------------------
    def run(self):
        """Run the websocket connection forever.
        """
        self.ws.run_forever()

    # -------------------------------------------------------------------------
    def __del__(self):
        """Close the websocket connection.
        """
        self.close()

    # -------------------------------------------------------------------------
    def on_message(self, message):
        """Process an incoming message.
        Add it to the fifo buffer.
        """

        # debug(f"websocket on_message() {message=}")
        self.fifo.extend(message)
        try:
            self.fifo_lock.release()
        except RuntimeError as err:
            # print(f"1 Exception: {err=}")
            pass

    # -------------------------------------------------------------------------
    def on_error(self, error) -> None:
        """Handle a websocket error.
        :param error: The detected error
        """

        logging.error("websocket error: %s" % error)
        try:
            self.fifo_lock.release()
        except RuntimeError as err:
            # print(f"2 Exception: {err=}")
            pass

    # -------------------------------------------------------------------------
    def on_close(self, _ws) -> None:
        """Close the current open repl over websocket connection.
        :param _ws: websocket connection
        """

        logging.info("websocket closed")
        try:
            self.fifo_lock.release()
        except RuntimeError as err:
            # print(f"3 Exception: {err=}")
            pass

    # -------------------------------------------------------------------------
    def close(self):
        """Close the REPL over websocket connection.
        """
        try:
            self.ws.close()
            try:
                self.fifo_lock.release()
            except RuntimeError as err:
                # print(f"4 Exception: {err=}")
                pass
            self.join()
        except RuntimeError as err:
            try:
                self.fifo_lock.release()
            except RuntimeError as err:
                # print(f"5 Exception: {err=}")
                pass

    # -------------------------------------------------------------------------
    def read(self, size=1, blocking=True):
        """Read a number of bytes from the repl websocket connection.
        :param size:
        :param blocking:
        """

        data = ""

        tstart = time.time()

        while (len(data) < size) and (time.time() - tstart < self.timeout):

            if len(self.fifo) > 0:
                data += self.fifo.popleft()
            elif blocking:
                self.fifo_lock.acquire()

        return data.encode("utf-8")

    # -------------------------------------------------------------------------
    def write(self, data: bytes) -> int:
        """Write data to the open repl over websocket connection.
        :param data: The data to write
        :returns: The number of bytes written.
        """
        self.ws.send(data)
        return len(data)

    # -------------------------------------------------------------------------
    def inWaiting(self):
        """Return the number of data bytes waiting in the fifo buffer.
        :returns: number of bytes waiting
        """
        return len(self.fifo)

    # -------------------------------------------------------------------------
    def survives_soft_reset(self) -> bool:
        """Indicate that this connection does NOT survive a soft reset.
        """
        return False
