"""Page declaration errors that must not become the runtime error screen."""

from ..protocol import codec


class PageDeclarationError(ValueError):
    """A page or page-context contract error."""


class PageDeclarationTypeError(TypeError):
    """A page or page-context type-contract error."""


class PageDeclarationKeyError(KeyError):
    """A page or page-context missing-declaration error."""


PAGE_DECLARATION_ERRORS = (
    PageDeclarationError,
    PageDeclarationTypeError,
    PageDeclarationKeyError,
)


def check_field_placement(row, col, width):
    if not all(isinstance(value, int) for value in (row, col, width)):
        raise PageDeclarationTypeError(
            "field row, col, and width must be integers"
        )
    if width < 1:
        raise PageDeclarationError("field width must be at least 1")
    if not 0 <= row < codec.ROWS:
        raise PageDeclarationError(
            f"field row must be between 0 and {codec.ROWS - 1}"
        )
    if not 0 <= col < codec.COLS:
        raise PageDeclarationError(
            f"field col must be between 0 and {codec.COLS - 1}"
        )
    if col + width > codec.COLS:
        raise PageDeclarationError(
            f"field width {width} at col {col} exceeds {codec.COLS} columns"
        )
