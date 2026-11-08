"""Reader page fixtures used by the public page tests."""

from services.common.reader import (
    Block,
    Document,
    Link,
    SearchResult,
    Span,
)

FIXTURE_CREDIT = "FIXTURE PAGES. REAL WIKIPEDIA NEXT."

ALPHA_LINKS = (
    Link("BETA", "BETA PAGE", ("BETA", "THE BETA PAGE", "RETURN TO BETA")),
    Link("GAMMA", "GAMMA PAGE", ("GAMMA", "THE GAMMA PAGE", "LINK TO GAMMA")),
)

BETA_LINKS = (
    Link("ALPHA", "ALPHA PAGE", ("ALPHA", "THE ALPHA PAGE")),
    Link("GAMMA", "GAMMA PAGE", ("GAMMA", "THE GAMMA PAGE", "HERE")),
)

GAMMA_LINKS = (
    Link("ALPHA", "ALPHA PAGE", ("ALPHA", "THE ALPHA PAGE")),
    Link("BETA", "BETA PAGE", ("BETA", "THE BETA PAGE")),
)

ALPHA = Document(
    token="ALPHA",
    title="ALPHA PAGE",
    revision="1",
    credit=FIXTURE_CREDIT,
    links=ALPHA_LINKS,
    blocks=(
        Block("heading", (Span("WELCOME TO ALPHA"),), 2),
        Block(
            "paragraph",
            (
                Span("THIS IS THE ALPHA FIXTURE PAGE. "),
                Span("BETA", 0),
                Span(" AND "),
                Span("GAMMA", 1),
                Span(" ARE ITS NEIGHBOURS."),
            ),
        ),
        Block(
            "paragraph",
            (
                Span("THE READER HIGHLIGHTS LINKS AS YOU TYPE. TYPE A WORD "
                     "SUCH AS "),
                Span("BETA", 0),
                Span(" TO NARROW THE TARGETS."),
            ),
        ),
        Block("heading", (Span("DETAILS"),), 2),
        Block(
            "paragraph",
            (
                Span("ALPHA HAS SEVERAL PARAGRAPHS SO THE VIEWPORT CAN "
                     "SCROLL. THE HIDDEN FIND FIELD DOES NOT TAKE SPACE IN "
                     "THE ARTICLE."),
            ),
        ),
        Block(
            "bullet",
            (
                Span("FIRST BULLET WITH A "),
                Span("LINK TO GAMMA", 1),
                Span("."),
            ),
        ),
        Block("bullet", (Span("SECOND BULLET WITH PLAIN TEXT."),)),
        Block(
            "paragraph",
            (
                Span("THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG. " * 4),
            ),
        ),
        Block("heading", (Span("MORE TEXT"),), 2),
        Block(
            "paragraph",
            (
                Span("USE SUITE AND RETOUR TO CYCLE MATCHES. THE FIRST PRESS "
                     "SELECTS THE TOPMOST VISIBLE TARGET. TYPING CLEARS THE "
                     "SELECTION; ANNULATION CLEARS THE BUFFER."),
            ),
        ),
        Block(
            "paragraph",
            (
                Span("THIS PARAGRAPH IS LONG ENOUGH TO WRAP SEVERAL TIMES AT "
                     "FORTY COLUMNS. IT GIVES THE VIEWPORT SOMETHING TO "
                     "SCROLL AND THE LINK CYCLE SOMEWHERE TO TRAVEL. "),
                Span("RETURN TO BETA", 0),
                Span(" WHEN YOU ARE DONE."),
            ),
        ),
    ),
)

BETA = Document(
    token="BETA",
    title="BETA PAGE",
    revision="1",
    credit=FIXTURE_CREDIT,
    links=BETA_LINKS,
    blocks=(
        Block("heading", (Span("BETA"),), 2),
        Block(
            "paragraph",
            (
                Span("BETA IS THE SECOND FIXTURE PAGE. "),
                Span("ALPHA", 0),
                Span(" AND "),
                Span("GAMMA", 1),
                Span(" ARE ONE KEYSTROKE AWAY."),
            ),
        ),
        Block(
            "paragraph",
            (
                Span("THIS PAGE TESTS THE TARGET-TITLE MATCH: THE ANCHOR "),
                Span("HERE", 1),
                Span(" MATCHES THE TITLE GAMMA PAGE."),
            ),
        ),
        Block("heading", (Span("LIST"),), 2),
        Block("bullet", (Span("FIRST BETA BULLET."),)),
        Block("bullet", (Span("SECOND BETA BULLET."),)),
        Block(
            "paragraph",
            (
                Span("A LONGER BODY KEEPS THE VIEWPORT AND THE MATCH CYCLE "
                     "USEFUL. " * 3),
            ),
        ),
    ),
)

GAMMA = Document(
    token="GAMMA",
    title="GAMMA PAGE",
    revision="1",
    credit=FIXTURE_CREDIT,
    links=GAMMA_LINKS,
    blocks=(
        Block("heading", (Span("GAMMA"),), 2),
        Block(
            "paragraph",
            (
                Span("GAMMA IS THE THIRD FIXTURE PAGE. IT LINKS BACK TO "),
                Span("ALPHA", 0),
                Span(" AND "),
                Span("BETA", 1),
                Span("."),
            ),
        ),
        Block("quote", (Span("A SHORT QUOTED LINE."),)),
        Block(
            "paragraph",
            (
                Span("THE FIXTURE SET IS SMALL ON PURPOSE. THE REAL WIKIPEDIA "
                     "SERVICE REPLACES THIS SOURCE WITHOUT CHANGING THE PAGE "
                     "OR THE RENDERER."),
            ),
        ),
    ),
)

DOCUMENTS = {
    "ALPHA": ALPHA,
    "BETA": BETA,
    "GAMMA": GAMMA,
}

RESULTS = (
    SearchResult(
        "ALPHA",
        "ALPHA PAGE",
        "THE FIRST FIXTURE PAGE WITH LINKS TO BETA AND GAMMA.",
        "FIXTURE",
    ),
    SearchResult(
        "BETA",
        "BETA PAGE",
        "THE SECOND FIXTURE PAGE WITH A TARGET-TITLE MATCH.",
        "FIXTURE",
    ),
    SearchResult(
        "GAMMA",
        "GAMMA PAGE",
        "THE THIRD FIXTURE PAGE.",
        "FIXTURE",
    ),
)


