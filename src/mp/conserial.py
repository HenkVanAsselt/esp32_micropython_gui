"""conserial.py
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
import time

from serial import Serial

from mp.conbase import ConBase
from mp.conbase import ConError


class ConSerial(ConBase):
    """Serial Connection Class
    """

    def __init__(self, port, baudrate=115200, reset=False) -> None:
        """Initialize ConSerial instance.
        """
        ConBase.__init__(self)

        try:
            self.serial = Serial(port, baudrate=baudrate, interCharTimeout=1)

            if reset:
                logging.info("Hard resetting device at port: %s" % port)

                self.serial.setDTR(True)
                time.sleep(0.25)
                self.serial.setDTR(False)

                self.serial.close()
                self.serial = Serial(port, baudrate=baudrate, interCharTimeout=1)

                while True:
                    time.sleep(2.0)
                    if not self.inWaiting():
                        break
                    self.serial.read(self.inWaiting())

        except Exception as e:
            logging.error(e)
            raise ConError(e)

    def close(self):
        """Close serial connection."""
        return self.serial.close()

    def read(self, size) -> bytes:
        """Read 'size' bytes from the serial port."""
        data = self.serial.read(size)
        logging.debug("conserial read < %s" % str(data))
        return data

    def write(self, data) -> int:
        """Write 'data' to the serial port."""
        logging.debug("conserial write > %s" % str(data))
        return self.serial.write(data)

    def inWaiting(self) -> int:
        """Are characters waiting on the serial port"""
        return self.serial.inWaiting()

    def survives_soft_reset(self) -> bool:
        """No, a serial port does not survive a soft reset.
        :returns: False
        """
        return False
