"""Shared page widgets: form footer and input fields."""

from .layout import FIELD_COL, FIELD_ROW, FIELD_WIDTH


def form_footer(screen, ctx, fields):
    names = [name for name, _ in fields]
    active = ctx.active_name if ctx.active_name in names else (names[0] if names else None)
    index = names.index(active) if active in names else 0
    next_label = fields[index + 1][1] if index + 1 < len(fields) else "(END)"
    prev_label = fields[index - 1][1] if index > 0 else "BACK"
    screen.text(
        22, 0, f"SUITE: {next_label}  RETOUR: {prev_label}"[:40]
    )
    screen.text(23, 0, "ENVOI: SUBMIT  SOMMAIRE: HOME")


def line_field(screen, ctx, name, row, col, width, *, label=None,
               label_col=0, value="", cursor="visible"):
    if label:
        screen.text(row, label_col, label)
    screen.field(row, col, width)
    current = ctx.values.get(name, value)
    if current:
        screen.text(row, col, current[:width], inverse=True)
    return ctx.add_field(
        name, row, col, width, value=value, cursor=cursor
    )


def page_input(screen, ctx, *, cursor="visible"):
    screen.text(FIELD_ROW, 0, "PAGE:")
    screen.field(FIELD_ROW, FIELD_COL, FIELD_WIDTH)
    ctx.set_input(FIELD_ROW, FIELD_COL, FIELD_WIDTH, cursor=cursor)
