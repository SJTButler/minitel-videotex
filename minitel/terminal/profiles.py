"""Terminal capability profiles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalProfile:
    name: str
    type_codes: tuple[int, ...]
    columns: int
    colour: bool
    drcs: bool
    max_speed: int
    mixed_80: bool = False


M1 = TerminalProfile(
    name="Minitel 1",
    type_codes=(0x62, 0x63, 0x72),
    columns=40,
    colour=False,
    drcs=False,
    max_speed=1200,
)

M1C = TerminalProfile(
    name="Minitel 1 couleur",
    type_codes=(0x73,),
    columns=40,
    colour=True,
    drcs=False,
    max_speed=1200,
)

M2_MONO = TerminalProfile(
    name="Minitel 2 (mono)",
    type_codes=(0x76,),
    columns=40,
    colour=False,
    drcs=True,
    max_speed=9600,
    mixed_80=True,
)

M2_COLOUR = TerminalProfile(
    name="Minitel 2 couleur",
    type_codes=(0x76,),
    columns=40,
    colour=True,
    drcs=True,
    max_speed=9600,
    mixed_80=True,
)

UNKNOWN = M1


def by_type(type_code, colour=False):
    if type_code == 0x73:
        return M1C
    if type_code in M1.type_codes:
        return M1
    if type_code == 0x76:
        return M2_COLOUR if colour else M2_MONO
    return UNKNOWN


def cps(speed):
    return speed / 9.0
