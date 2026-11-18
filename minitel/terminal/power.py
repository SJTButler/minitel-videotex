"""Terminal power signals: pause on power-off, repaint on power-on."""

from dataclasses import dataclass

POWER_OFF = b"\x00"
POWER_ON = b"\x7c\x13\x59\x13\x53\x13\x54"


@dataclass(frozen=True)
class Power:
    """A terminal power transition found in the input stream."""

    on: bool


@dataclass(frozen=True)
class PowerSignals:
    """Raw byte sequences the terminal sends on power-off and power-on.

    An empty sequence disables that side of the mechanism.
    """

    off: bytes = POWER_OFF
    on: bytes = POWER_ON


class PowerWatcher:
    """Split-safe matcher that removes power sequences from a byte stream.

    ``feed`` returns ``bytes`` chunks and ``Power`` events in arrival order.
    Bytes that are not part of a sequence pass through unchanged. A trailing
    partial match is held until the next chunk; if the next bytes do not
    complete it, the held bytes are released before the new data.
    """

    def __init__(self, signals=None):
        signals = signals or PowerSignals()
        self._patterns = tuple(
            sorted(
                (
                    (pattern, Power(on))
                    for pattern, on in ((signals.off, False), (signals.on, True))
                    if pattern
                ),
                key=lambda item: len(item[0]),
                reverse=True,
            )
        )
        self._pending = b""

    def reset(self):
        self._pending = b""

    def feed(self, data):
        if not self._patterns:
            return [bytes(data)] if data else []
        pending = self._pending + data
        self._pending = b""
        tokens = []
        passthrough = bytearray()

        def flush():
            if passthrough:
                tokens.append(bytes(passthrough))
                passthrough.clear()

        index = 0
        length = len(pending)
        while index < length:
            match = self._match_at(pending, index)
            if match is not None:
                pattern, event = match
                flush()
                tokens.append(event)
                index += len(pattern)
                continue
            if self._is_prefix_at(pending, index):
                break
            passthrough.append(pending[index])
            index += 1
        flush()
        self._pending = pending[index:]
        return tokens

    def _match_at(self, data, index):
        for pattern, event in self._patterns:
            if data.startswith(pattern, index):
                return pattern, event
        return None

    def _is_prefix_at(self, data, index):
        remaining = len(data) - index
        for pattern, _event in self._patterns:
            if remaining <= len(pattern) and data.startswith(
                pattern[:remaining], index
            ):
                return True
        return False
