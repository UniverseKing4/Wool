import sys
import tty
import termios

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
try:
    tty.setcbreak(fd)
    sys.stdout.write("Line 1")
    sys.stdout.write("\n")
    sys.stdout.write("Line 2")
    sys.stdout.write("\n")
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
