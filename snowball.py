from string import ascii_lowercase as lowercase
from math import floor
from time import time, sleep
from random import random


def _b26_lowercase(x):
    # https://stackoverflow.com/a/28666223/9068081
    digits = []
    while x:
        digits.append(int(x % 26))
        x //= 26
    return ''.join(lowercase[digit] for digit in digits)


def snowball():  # Length 7.167 and increasing.
    ms = floor(time() * 1e3 - 1609459200000)
    # Since 2021. If you need to convert earlier dates, don't use this!
    ms_reversed = sum(int(e) * 10 ** i for i, e in enumerate(str(ms)))
    # Increment timer by at least 1ms to guarantee a unique snowball.
    sleep(1e-3)
    return _b26_lowercase(ms_reversed)  # .rjust(10, 'j')
    # Optional: pad arbitrary-length b26 outputs.
    # A signifigant (54.4% since UNIX Epoch) number will be padded.
