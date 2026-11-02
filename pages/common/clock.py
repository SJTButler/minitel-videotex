"""Shared clock and date formatting."""

import time


def local_now():
    return time.localtime()


def _now(now):
    return time.localtime() if now is None else now


def clock_text(now=None):
    return time.strftime("%H:%M:%S", _now(now))


def clock_hm(now=None):
    return time.strftime("%H:%M", _now(now))


def clock_seconds(now=None):
    return time.strftime("%S", _now(now))


def date_text(now=None):
    return time.strftime("%d/%m/%Y", _now(now))
