"""Session field editing and shadow-screen updates."""

from dataclasses import replace

from ..protocol import codec
from .action import Action


class EditingMixin:
    @property
    def active_field(self):
        if not self.fields:
            return None
        index = max(0, min(self.active, len(self.fields) - 1))
        return self.fields[index]

    @property
    def input(self):
        return self.active_field

    @property
    def line(self):
        field = self.active_field
        return self.values.get(field.name, "") if field else ""

    @line.setter
    def line(self, value):
        field = self.active_field
        if field is not None:
            self.values[field.name] = value

    def _has_input_text(self):
        return any(self.values.get(field.name, "") for field in self.fields)

    def _clear_active_field(self):
        field = self.active_field
        if field is not None:
            self.values[field.name] = ""

    def _cursor_visible(self):
        field = self.active_field
        if field is None:
            return False
        if field.cursor == "auto":
            return bool(self.values.get(field.name, ""))
        return field.cursor == "visible"

    def _focus_frame(self):
        field = self.active_field
        if field is None:
            return b""
        value = self.values.get(field.name, "")
        col = field.col + min(len(value), field.width)
        raw = bytearray(codec.pos(field.row, col))
        raw += codec.cursor(self._cursor_visible())
        if self.screen is not None:
            cell = self.screen.rows[field.row][field.col]
            raw += codec.inverse(cell.inverse)
        return bytes(raw)

    def _shadow_put(self, field, index, char):
        if self.screen is None:
            return
        row = field.row
        col = field.col + index
        if not (0 <= row < codec.ROWS and 0 <= col < codec.COLS):
            return
        base = self.screen.rows[row][field.col]
        self.screen.rows[row][col] = replace(base, ch=char)

    def _sync_shadow_cursor(self):
        field = self.active_field
        if field is None or self.screen is None:
            return
        value = self.values.get(field.name, "")
        col = field.col + min(len(value), field.width)
        self.screen.set_cursor(field.row, col, self._cursor_visible())

    def text_event(self, event):
        field = self.active_field
        if field is None:
            return Action(raw=bytes([codec.BEL]))
        value = self.values.get(field.name, "")
        if len(value) >= field.width:
            return Action(raw=bytes([codec.BEL]))
        prefix = b""
        if field.cursor == "auto" and not value:
            prefix = codec.cursor(True)
        echo = b""
        if self.echo:
            if self.screen is not None:
                base = self.screen.rows[field.row][field.col]
                prefix += codec.inverse(base.inverse)
            echo = codec.text(event.char)
        self._shadow_put(field, len(value), event.char)
        self.values[field.name] = value + event.char
        self._sync_shadow_cursor()
        return Action(raw=prefix + echo)

    def correction(self):
        field = self.active_field
        value = self.values.get(field.name, "") if field else ""
        if field and value:
            value = value[:-1]
            self.values[field.name] = value
            self._shadow_put(field, len(value), " ")
            self._sync_shadow_cursor()
            raw = bytes([codec.BS, 0x20, codec.BS])
            if field.cursor == "auto" and not value:
                raw += codec.cursor(False)
            return Action(raw=raw)
        return Action()

    def annulation(self):
        field = self.active_field
        if field:
            self.values[field.name] = ""
        return self.refresh()
