"""Page 180: a desk to-do list."""

from minitel import PAGE_BACK, Region, Screen, codec, page

from ..common.layout import SECONDARY, WARNING, footer
from ..common.messages import MessageLatch
from ..common.widgets import line_field
from ._support import store as notes_store

PAGE = "180"
PAGE_SIZE = 12
TEXT_WIDTH = notes_store.MAX_TEXT
FIELD = "note"
EDIT = "notes_edit"
FOCUS_ID = "notes_focus_id"


def _store(ctx):
    store = ctx.state.get("notes_store")
    if store is None:
        store = notes_store.NoteStore()
        ctx.add_resource(store)
        ctx.state["notes_store"] = store
    return store


def _position(notes, choice):
    if not notes:
        return "EMPTY"
    done = sum(1 for note in notes if note.done)
    start = choice.offset + 1
    end = min(choice.offset + choice.page_size, len(notes))
    position = f"{start}-{end}/{len(notes)}"
    return f"{position}  {done} DONE" if done else position


def _selected_note(ctx, notes):
    cursor = ctx.region("items").cursor
    selected = getattr(cursor, "selected", None)
    if selected is None or not 0 <= selected < len(notes):
        return None
    return notes[selected]


def _move(store, state, note, delta):
    store.move(note, delta)
    state[FOCUS_ID] = note.id


def _render(ctx):
    store = _store(ctx)
    notes = store.all()
    focus = ctx.focused_region

    edit_id = ctx.state.get(EDIT)
    if edit_id is not None and all(note.id != edit_id for note in notes):
        ctx.state.pop(EDIT, None)
        edit_id = None

    focus_id = ctx.state.pop(FOCUS_ID, None)
    selected = None
    if focus_id is not None:
        selected = next(
            (
                index for index, note in enumerate(notes)
                if note.id == focus_id
            ),
            None,
        )
    choice = ctx.set_choice(
        notes,
        region="items",
        key="notes",
        selected=selected,
        commit=store.toggle,
        remove=store.delete,
        commands={
            "*": lambda note: _move(store, ctx.state, note, -1),
            "#": lambda note: _move(store, ctx.state, note, 1),
        },
    )

    s = Screen()
    ctx.set_status(f"PAGE {PAGE}")
    s.text(2, 0, "NOTES", inverse=True, size=codec.DOUBLE_WIDTH)
    position = _position(notes, choice)
    s.text(2, codec.COLS - len(position), position, fg=SECONDARY)

    if not notes:
        s.text(4, 0, "NO NOTES YET. TYPE ONE BELOW.", fg=SECONDARY)
    for row, index, note, selected_row in choice.rows(notes):
        box = "X" if note.done else " "
        s.text(
            3 + row,
            0,
            (
                f"{index + 1:>2}. {note.text[:TEXT_WIDTH]:<{TEXT_WIDTH}} "
                f"[{box}]"
            ),
            inverse=selected_row and focus == "items",
        )

    s.rule(15, 0, codec.COLS, "-")
    s.text(
        16, 0,
        "EDIT NOTE" if edit_id is not None else "NEW NOTE",
        inverse=True,
    )
    s.text(17, 0, "> ")
    line_field(s, ctx, FIELD, 17, 2, TEXT_WIDTH, region="entry")

    message = MessageLatch(ctx).text()
    if message:
        s.text(18, 0, message[:codec.COLS], fg=WARNING)
    if focus == "items":
        s.text(19, 0, "ENVOI: DONE  CORRECTION: EDIT", fg=SECONDARY)
        s.text(
            20, 0, "ANNULATION: DELETE  *: UP  #: DOWN",
            fg=SECONDARY,
        )
    elif edit_id is not None:
        s.text(19, 0, "ENVOI: SAVE   SUITE: LIST", fg=SECONDARY)
        s.text(20, 0, "ANNULATION: CLEAR", fg=SECONDARY)
    else:
        s.text(19, 0, "ENVOI: ADD   SUITE: LIST", fg=SECONDARY)
        s.text(20, 0, "ANNULATION: CLEAR", fg=SECONDARY)
    footer(s)
    return s


def _add(ctx, values):
    text = values.get(FIELD, "")
    edit_id = ctx.state.get(EDIT)
    latch = MessageLatch(ctx)
    if not text.strip():
        if edit_id is not None:
            ctx.state.pop(EDIT, None)
            ctx.values.clear()
            ctx.focus_region("items")
            return PAGE
        latch.set("TYPE A NOTE")
        ctx.focus(FIELD)
        return PAGE
    store = _store(ctx)
    if edit_id is not None:
        store.update(edit_id, text)
        ctx.state.pop(EDIT, None)
        latch.clear()
        ctx.values.clear()
        ctx.focus_region("items")
        return PAGE
    try:
        store.add(text)
    except ValueError:
        latch.set("LIST FULL - DELETE DONE ITEMS")
        ctx.focus(FIELD)
        return PAGE
    latch.clear()
    ctx.values.clear()
    ctx.focus(FIELD)
    return PAGE


def _key(ctx, name):
    if name != "CORRECTION" or ctx.focused_region != "items":
        return None
    note = _selected_note(ctx, _store(ctx).all())
    if note is None:
        return None
    ctx.state[EDIT] = note.id
    ctx.values[FIELD] = note.text
    ctx.focus_region("entry")
    return None


@page(
    PAGE,
    title="NOTES",
    form=True,
    on_form=_add,
    on_key=_key,
    default_focus="entry",
    regions=(
        Region(
            "items", kind="choice", next="entry", prev=PAGE_BACK,
            activate="stay", page_size=PAGE_SIZE,
        ),
        Region("entry", kind="form", next="items", prev=PAGE_BACK),
    ),
)
def notes(ctx):
    return _render(ctx)
