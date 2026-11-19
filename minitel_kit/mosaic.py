"""Sub-cell mosaic drawing for ``minitel.Screen``."""

import math


class MosaicCanvas:
    """A 2x3 sub-pixel canvas packed into ordinary mosaic cells.

    Pixel coordinates span ``2 * width_cells`` by ``3 * height_cells``.
    Drawing primitives clip to the canvas; ``draw`` clips to the screen.
    """

    def __init__(self, width_cells, height_cells):
        if not isinstance(width_cells, int) or isinstance(width_cells, bool):
            raise TypeError("canvas width must be an int")
        if not isinstance(height_cells, int) or isinstance(height_cells, bool):
            raise TypeError("canvas height must be an int")
        if width_cells < 1 or height_cells < 1:
            raise ValueError("canvas width and height must be positive")
        self.width = width_cells
        self.height = height_cells
        self.pixels = set()

    @property
    def pixel_width(self):
        return self.width * 2

    @property
    def pixel_height(self):
        return self.height * 3

    def clear(self):
        self.pixels.clear()

    def set(self, x, y, on=True):
        x = int(x)
        y = int(y)
        if not (0 <= x < self.pixel_width and 0 <= y < self.pixel_height):
            return
        if on:
            self.pixels.add((x, y))
        else:
            self.pixels.discard((x, y))

    def get(self, x, y):
        return (int(x), int(y)) in self.pixels

    def fill(self, x0, y0, x1, y1, on=True):
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.pixel_width - 1, x1)
        y1 = min(self.pixel_height - 1, y1)
        if x0 > x1 or y0 > y1:
            return
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if on:
                    self.pixels.add((x, y))
                else:
                    self.pixels.discard((x, y))

    def line(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.set(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    def rect(self, x0, y0, x1, y1, filled=False):
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        if filled:
            self.fill(x0, y0, x1, y1)
            return
        self.line(x0, y0, x1, y0)
        self.line(x0, y1, x1, y1)
        self.line(x0, y0, x0, y1)
        self.line(x1, y0, x1, y1)

    def ellipse(self, x0, y0, x1, y1, filled=False):
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        if x0 == x1 or y0 == y1:
            if filled:
                self.fill(x0, y0, x1, y1)
            else:
                self.line(x0, y0, x1, y1)
            return
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        rx = (x1 - x0) / 2
        ry = (y1 - y0) / 2
        if filled:
            for y in range(y0, y1 + 1):
                offset = (y - cy) / ry
                if offset < -1 or offset > 1:
                    continue
                span = rx * math.sqrt(max(0.0, 1 - offset * offset))
                self.fill(
                    math.ceil(cx - span), y, math.floor(cx + span), y
                )
            return
        steps = max(24, 2 * ((x1 - x0) + (y1 - y0)))
        points = []
        for step in range(steps):
            angle = 2 * math.pi * step / steps
            points.append((
                cx + rx * math.cos(angle),
                cy + ry * math.sin(angle),
            ))
        for index, point in enumerate(points):
            start = point
            end = points[(index + 1) % len(points)]
            self.line(start[0], start[1], end[0], end[1])

    def pattern(self, row, col):
        if not 0 <= row < self.height:
            raise ValueError(f"row {row} outside 0..{self.height - 1}")
        if not 0 <= col < self.width:
            raise ValueError(f"column {col} outside 0..{self.width - 1}")
        pattern = 0
        base_x = col * 2
        base_y = row * 3
        for dy in range(3):
            for dx in range(2):
                if (base_x + dx, base_y + dy) in self.pixels:
                    pattern |= 1 << (5 - (dy * 2 + dx))
        return pattern

    def draw(self, screen, row, col, *, include_blank=False, **attrs):
        for canvas_row in range(self.height):
            target_row = row + canvas_row
            if target_row < 0:
                continue
            if target_row >= len(screen.rows):
                break
            for canvas_col in range(self.width):
                target_col = col + canvas_col
                if target_col < 0:
                    continue
                if target_col >= len(screen.rows[0]):
                    break
                pattern = self.pattern(canvas_row, canvas_col)
                if pattern == 0 and not include_blank:
                    continue
                screen.put_mosaic(target_row, target_col, pattern, **attrs)
