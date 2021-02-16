import ampy.files as files
import ampy.pyboard as pyboard


# -----------------------------------------------------------------------
def test1():

    _board = pyboard.Pyboard("COM4:", baudrate=115200, rawdelay=0.1)

    board_files = files.Files(_board)
    for f in board_files.ls('/', long_format=False, recursive=False):
        print(f)


# -----------------------------------------------------------------------
def test2():

    pyb = pyboard.Pyboard('COM4:')
    pyb.enter_raw_repl()
    pyb.exec('pyb.LED(1).on()')
    pyb.exit_raw_repl()


# -----------------------------------------------------------------------
def test3():
    pyboard.execfile('c:\\temp\\blinky.py', device='COM4:')


# -----------------------------------------------------------------------
def test5():

    pyb = pyboard.Pyboard('COM4:', 115200)
    pyb.enter_raw_repl()
    ret = pyb.exec('print(5+3)')
    print(ret)
    pyb.exit_raw_repl()


# ===============================================================================
if __name__ == "__main__":

    # test1()
    # test3()
    test5()

