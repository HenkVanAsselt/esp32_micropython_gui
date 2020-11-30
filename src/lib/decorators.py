"""
Function/method decorators
"""

# Global imports
import inspect
from functools import wraps

# Local imports
from lib.helper import decrease_path_depth
from lib.tracetool import ttrace


# -----------------------------------------------------------------------------
def get_caller(i=2):
    """ Get the calling function filename and linenumber

    :param i: The index to retreive from the frame info listctrl. Default is 2
    :return: tuple of filename and linenumber
    """

    frame_info_list = inspect.stack()

    #    print('inspect.stack()')
    #    i = 0
    #    for l in frame_info_list:
    #        print('%d : %s' % (i,l))
    #        i += 1

    caller = frame_info_list[i]  # This is the frameinfo for the calling module
    frame, filename, lineno, function_name, code_context, index = caller
    return filename, lineno


# -----------------------------------------------------------------------------
def debug(filename, lineno, msg):
    """ Send message s to logging.debug and print it (if not commented out)

    :param filename: source filename to display
    :param lineno: sourcefile linenumber to display
    :param msg: message to display
    :return: Nothing

    """

    # header = "%s line:%s" % (filename, lineno)
    ttrace.debug.send(f"{filename} line:{lineno}", msg)
    # if param.logger:
    #     param.logger.debug(f"{filename} line:{lineno} : {msg}")
    # else:
    #     logging.debug(f"{filename} line:{lineno} : {msg}")

    return


# -----------------------------------------------------------------------------
def dumpFuncname(func):
    """Decorator to dump the function name of a function before calling it
    """

    filename, lineno = get_caller(i=2)
    funcname = func.__name__

    filename = decrease_path_depth(filename, 2)

    @wraps(func)
    def echoFunc(*args, **kwargs):
        """ Just return all arguments. No manipulation will be done
        """
        debug(filename, lineno, "DumpFuncName: " + funcname + "()")
        return func(*args, **kwargs)

    return echoFunc


# -----------------------------------------------------------------------------
def dumpArgs(func):
    """Decorator to dump the arguments passed to a function before calling it
    """

    filename, lineno = get_caller(i=2)

    # Prevent a full path like 'C:\data\LXE\AndroidConfig\src\pyadb.py'
    # Bring this down to just 'src\pyadb.py'

    filename = decrease_path_depth(filename, 2)

    funcname = func.__name__
    argnames = func.__code__.co_varnames[: func.__code__.co_argcount]

    # print('dumpArgsfuncname: filename=%s function=%s()' % (filename, funcname))

    @wraps(func)
    def echoFunc(*args, **kwargs):
        """ Docstring
        """
        arguments = ", ".join(
            "%s=%r" % entry
            for entry in list(zip(argnames, args)) + list(kwargs.items())
        )
        # print(filename, lineno, '%s(%s)' % (funcname, arguments))
        debug(filename, lineno, "DumpArgs: %s(%s)" % (funcname, arguments))
        return func(*args, **kwargs)

    return echoFunc


# -----------------------------------------------------------------------------
if __name__ == '__main__':
    pass
