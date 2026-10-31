"""Content declarations for the example service."""

SELECTABLE_SCREENSAVERS = ("clock", "mire", "carousel", "ball")

SCREENSAVER_MODES = {
    "clock": ("900",),
    "mire": ("901",),
    "carousel": ("910", "911", "912"),
    "ball": ("903",),
}
SCREENSAVER_MODES["all"] = tuple(
    key for name in SELECTABLE_SCREENSAVERS for key in SCREENSAVER_MODES[name]
)

SCREENSAVER_LABELS = {
    "clock": "CLOCK",
    "mire": "TEST CARD",
    "carousel": "CAROUSEL",
    "ball": "BOUNCING BALL",
}

DEFAULT_SCREENSAVER = "clock"
