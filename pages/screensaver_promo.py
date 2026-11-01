from minitel import codec
from minitel.pages import page
from minitel.screen import Screen


def _promo(title, lines, prompt):
    s = Screen()
    s.text(1, 0, title, inverse=True, size=codec.DOUBLE_WIDTH)
    for index, line in enumerate(lines):
        s.text(5 + index, 0, line)
    s.text(12, 0, prompt)
    s.text(23, 0, "PRESS ANY KEY")
    return s


@page("910", title="KILO", back_page="190", screensaver="carousel")
def kilo(ctx):
    return _promo(
        "3615 KILO",
        (
            "1  NEWS",
            "2  WEATHER",
            "3  ABOUT",
            "4  GUESTBOOK",
        ),
        "TYPE A NUMBER, THEN ENVOI",
    )


@page("911", title="NEWS", back_page="190", screensaver="carousel")
def news_promo(ctx):
    return _promo(
        "THE NEWS",
        (
            "HACKER NEWS",
            "FOUR HEADLINES PER PAGE",
            "ONE COMMENT PER STORY",
        ),
        "TYPE 1 FOR NEWS",
    )


@page("912", title="WEATHER", back_page="190", screensaver="carousel")
def weather_promo(ctx):
    return _promo(
        "THE WEATHER",
        (
            "PARIS   LYON   MARSEILLE",
            "TEMPERATURES AND SKY",
            "DEMO DATA",
        ),
        "TYPE 2 FOR WEATHER",
    )
