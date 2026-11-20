"""Freeze "now" during replay.

SignalStaleness, position persistence and the position lifecycle call
datetime.now(). Replaying 2022 with the real clock would make every signal
look years old (SIGNAL_EXPIRED). time-machine moves the clock to the bar's
decision time without changing any strategy file.
"""
from contextlib import contextmanager
from datetime import datetime

import time_machine


@contextmanager
def frozen_at(moment: datetime):
    with time_machine.travel(moment, tick=False):
        yield
