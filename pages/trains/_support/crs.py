"""UK CRS station-code validation and route-token parsing."""

import re

_CRS = re.compile(r"^[A-Z]{3}$")


def valid_crs(value):
    return bool(_CRS.fullmatch(value))


def parse_route(token):
    if not token:
        return None
    token = token.strip().upper()
    if len(token) == 3 and valid_crs(token):
        return token, ""
    if (
        len(token) == 6
        and valid_crs(token[:3])
        and valid_crs(token[3:])
    ):
        return token[:3], token[3:]
    return None
