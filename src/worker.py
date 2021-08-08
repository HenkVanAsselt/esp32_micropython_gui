"""
worker.py
=========

Goal
====

These functions make it possible to call an external executable and show the
(stdout) output realtime in a pyqt5/pyside5 text window.

This module is based on https://stackoverflow.com/questions/60167832/run-command-with-pyqt5-and-getting-the-stdout-and-stderr
As an enhancment, it will also show it's state, so when it is not desired that 2 threads run at the same time, one can
wait till a thread is finished.

Usage example
=============

.. code-block:: python

    import param
    from worker import Worker

    class MainWindow(QMainWindow):

        text_update = QtCore.pyqtSignal(str)

        def __init__(self):

            super(MainWindow, self).__init__()
            self.ui = Ui_MainWindow()
            self.ui.setupUi(self)

            param.worker = Worker()
            param.worker.outSignal.connect(self.append_text)

        def somefunction():

            param.worker.run_command("ping 127.0.0.1")
            while param.worker.active:
                # The following 3 lines will do the same as time.sleep(1), but more PyQt5 friendly.
                loop = QEventLoop()
                QTimer.singleShot(250, loop.quit)
                loop.exec_()
            param.worker.run_command("ping 192.168.178.1")

        @pyqtSlot(str)
        def append_text(self, text: str) -> None:

            cur = self.ui.text_output.textCursor()
            cur.movePosition(QtGui.QTextCursor.End)  # Move cursor to end of text
            s = str(text)
            while s:
                head, sep, s = s.partition("\\n")  # Split line at LF
                head = head.replace("\\r", "")     # Remove the Carriage Returns to avoid double linespacing.
                cur.insertText(head)  # Insert text at cursor
                if sep:  # New line if LF
                    cur.insertBlock()
            self.ui.text_output.setTextCursor(cur)  # Update visible cursor
            self.ui.text_output.update()

"""

import subprocess
import threading

from PyQt5 import QtCore


# =============================================================================
class Worker(QtCore.QObject):
    """QT Worker"""

    outSignal = QtCore.pyqtSignal(str)
    active = False

    # def __init__(self):
    #     self.active = False

    # -------------------------------------------------------------------------
    def run_command(self, cmd, **kwargs):
        """Execute a command in a thread, calling _execute_command"""
        if self.active:
            return
        self.active = True
        threading.Thread(
            target=self._execute_command, args=(cmd,), kwargs=kwargs, daemon=True
        ).start()

    # -------------------------------------------------------------------------
    def _execute_command(self, cmd, **kwargs):
        """Actually execute the command"""
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs
        )
        for line in proc.stdout:
            self.outSignal.emit(line.decode())
        self.active = False


# =============================================================================
if __name__ == "__main__":
    pass
