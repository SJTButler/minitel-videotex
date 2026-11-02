"""Shared presentation for cached service snapshots."""

import time


def updated_label(snapshot):
    age = snapshot.age()
    if age is None:
        return ""
    try:
        return time.strftime("%H:%M", time.localtime(time.time() - age))
    except (OSError, OverflowError, ValueError):
        return "--:--"
