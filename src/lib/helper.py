##
# @file: helper.py
# @brief: Small bluetooth helper functions

"""Small bluetooth helper functions
"""

# global imports
import os
import inspect

# local imports
from lib.tracetool import ttrace


# -----------------------------------------------------------------------------
def decrease_path_depth(path, maxdepth=2):
    r"""Decrease the path to the last folders(s) / filename

    >>> decrease_path_depth(r'C:\data\LXE\AndroidConfig\src\pyadb.py', 2)
    'src\\\\pyadb.py'

    >>> decrease_path_depth(r'C:\data\LXE\AndroidConfig\src\pyadb.py', 1)
    'pyadb.py'

    """

    path = os.path.normpath(path)
    seperator = os.path.sep
    path_depth = path.count(seperator)
    if path_depth > 1:
        paths = path.split(seperator)
        newpath = seperator.join(paths[-maxdepth:])
        return newpath
    else:
        return path


# ------------------------------------------------------------------------------
def get_caller(i=2):
    """Get the calling function filename and linenumber

    :param i: The index to retreive from the frame info listctrl. Default is 2
    :return: tuple of filename and linenumber
    """

    frame_info_list = inspect.stack()
    caller = frame_info_list[i]  # This is the frameinfo for the calling module
    frame, filename, lineno, function_name, code_context, index = caller
    return filename, lineno


# -----------------------------------------------------------------------------
def debug(s):
    """Send message s to logging.debug and print it (if not commented out)

    :param s: message to print
    :return: Nothing

    """

    filename, lineno = get_caller()

    filename = decrease_path_depth(filename, 2)

    ttrace.debug.send(f"{filename} line:{lineno}", s)
    # if param.logger:
    #     param.logger.debug(f"{filename} line:{lineno} : {s}")
    # else:
    #     logging.debug(f"{filename} line:{lineno} : {s}")

    return


# ===============================================================================
def clear_debug_window():
    """Make the ttrace debug window empty"""

    ttrace.clearAll()
    return


# =============================================================================
class PushBackDenied(Exception):
    pass


# -----------------------------------------------------------------------------
class IteratorWithPushback():
    """Class whose constructor takes an iterator as its only parameter, and
    returns an iterator that behaves in the same way, with added push back
    functionality.

    Once the iterator's next() method raises StopIteration, subsequent calls to
    push_back() will raise StopPushingBack.
    """

    def __init__(self, iterator):
        self.iterator = iter(iterator)
        self.pushed_back = []
        self._ok_to_push_back = True

    def __iter__(self):
        return self.iterator

    def __next__(self):
        if self.pushed_back:
            return self.pushed_back.pop()
        else:
            try:
                return next(self.iterator)
            except StopIteration:
                self._ok_to_push_back = False
                raise

    def push_back(self, element):
        if not self._ok_to_push_back:
            raise PushBackDenied
        else:
            self.pushed_back.append(element)


# -----------------------------------------------------------------------------
def print_header(header):
    """Print an underlined header
    """
    print(f"\n{header}")
    print(f"{len(header)*'-'}")


# -----------------------------------------------------------------------------
def str_bytes(s):
    """Convert a string to bytes.
    """
    return s.encode('latin-1')


# -----------------------------------------------------------------------------
def bytes_str(d):
    """ Convert bytes to string
    """
    return d if type(d) is str else "".join([chr(b) for b in d])


# -----------------------------------------------------------------------------
def hexdump(data):
    """Return hexadecimal values of data.

    :param data: Hexadecimal values
    :return: String of hexadecimal representation
    """
    return " ".join(["%02X" % ord(b) for b in data])


# -----------------------------------------------------------------------------
def textdump(data):
    """Return a string with high-bit chars replaced by hex values.

    :param data:
    :return:
    """
    return "".join(["[%02X]" % ord(b) if b > '\x7e' else b for b in data])


# =============================================================================
if __name__ == "__main__":
    # pass

    test_list = ['a', 'bb', 'c', 'ddd', 'ee']
    test_iter = IteratorWithPushback(test_list)

    for x in test_iter:
        print(x)
        if x == 'c':
            test_iter.push_back(x)


