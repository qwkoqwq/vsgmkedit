"""UI panels for the gimmick editor."""

import tkinter as tk
from tkinter import ttk

from config import (
    EFFECTS, EASINGS,
    COLOR_NOTE_SINGLE, COLOR_NOTE_WIDE_01, COLOR_NOTE_WIDE_23, COLOR_NOTE_MINE,
    COLOR_BG, COLOR_LANE_LINE, COLOR_JUDGMENT_LINE,
    COLOR_GIMMICK_BAR, COLOR_GIMMICK_SELECTED,
    COLOR_GIMMICK_NORMAL, COLOR_GIMMICK_GRID,
    COLOR_BEAT_MAJOR, COLOR_BEAT_MINOR, COLOR_BEAT_LABEL,
    COLOR_TEXT, COLOR_PANEL_BG,
    DEFAULT_MS_PER_PIXEL, MIN_MS_PER_PIXEL, MAX_MS_PER_PIXEL,
    ZOOM_FACTOR, NOTE_HEIGHT_RATIO,
    NOTE_CANVAS_WIDTH, GIMMICK_COLUMNS,
    DEFAULT_SUBDIVISION, SUBDIVISION_OPTIONS,
)
from model import Note, Gimmick, BeatConverter


# ---------------------------------------------------------------------------
# InfoPanel — left sidebar showing chart metadata
# ---------------------------------------------------------------------------

class InfoPanel(tk.Frame):
    """Displays chart metadata and difficulty list."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLOR_PANEL_BG, **kw)
        self._text = tk.Text(
            self, bg=COLOR_PANEL_BG, fg=COLOR_TEXT,
            wrap=tk.WORD, state=tk.DISABLED,
            font=("Microsoft YaHei", 10), width=22,
            relief=tk.FLAT, border=0,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def set_info(self, chart, diff_index: int):
        """Populate panel with chart information."""
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)

        info = chart.info
        lines = [
            f"歌曲: {info.name}",
            f"谱师: {info.composer}",
            f"BPM: {info.display_bpm}",
            f"音频: {'已加载' if chart.song_file else '未找到'}",
            "",
            "——— 难度列表 ———",
        ]
        for i, diff in enumerate(chart.difficulties):
            marker = " ▶" if i == diff_index else "  "
            name = diff.meta.diff1 or f"难度{i+1}"
            rating = diff.meta.diff2 or "?"
            lines.append(f"{marker}{name} (定数 {rating})")
            if i == diff_index:
                lines.append(f"    谱师: {diff.meta.charter}")
                lines.append(f"    物量: {len(diff.notes)}")

        self._text.insert("1.0", "\n".join(lines))
        self._text.configure(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# NoteCanvas — center panel showing 4-lane note chart
# ---------------------------------------------------------------------------

class NoteCanvas(tk.Canvas):
    """Scrollable 4-lane note display with judgment line."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLOR_BG, highlightthickness=0, **kw)
        self.notes: list[Note] = []
        self.judgment_time_ms: float = 0.0
        self.ms_per_pixel: float = DEFAULT_MS_PER_PIXEL
        self.converter: BeatConverter | None = None
        self.subdivision: int = DEFAULT_SUBDIVISION
        self.on_change = None  # callback when scroll/zoom changes
        self.on_seek = None    # callback when user clicks to seek
        self.on_line_right_click = None  # callback(time_ms) for gimmick add/delete
        self._needs_snap: bool = False

        self.bind("<MouseWheel>", self._on_scroll)
        self.bind("<Control-MouseWheel>", self._on_zoom)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Configure>", lambda e: self.redraw())

    def set_on_change(self, cb):
        self.on_change = cb

    def set_on_seek(self, cb):
        self.on_seek = cb

    def set_on_line_right_click(self, cb):
        self.on_line_right_click = cb

    def set_converter(self, converter: BeatConverter):
        self.converter = converter

    def set_subdivision(self, sub: int):
        self.subdivision = sub
        self.redraw()

    def set_notes(self, notes: list[Note]):
        self.notes = sorted(notes, key=lambda n: n.time_ms)
        self.redraw()

    def _beat_interval(self) -> float:
        """Beats between grid lines based on subdivision."""
        return 4.0 / self.subdivision

    def _scroll_amount_ms(self) -> float:
        """Milliseconds per scroll tick = one grid unit at current BPM."""
        if not self.converter:
            return 200.0
        beat_interval = self._beat_interval()
        # Approximate ms per beat at the current judgment time
        bpm_now = self._bpm_at(self.judgment_time_ms)
        return beat_interval * (60000.0 / bpm_now)

    def _bpm_at(self, time_ms: float) -> float:
        """Get the BPM active at a given time."""
        if not self.converter or not self.converter.timing:
            return 120.0
        bpm = self.converter.timing[0].bpm
        for tp in self.converter.timing:
            if tp.time_ms <= time_ms:
                bpm = tp.bpm
        return bpm

    def _on_scroll(self, event):
        delta = -event.delta / 120.0
        scroll_ms = delta * self._scroll_amount_ms()
        self.judgment_time_ms = max(0.0, self.judgment_time_ms + scroll_ms)
        if self._needs_snap:
            self._snap_to_beat()
            self._needs_snap = False
        self.redraw()
        if self.on_change:
            self.on_change()

    def set_needs_snap(self):
        """Next scroll will snap to the nearest beat."""
        self._needs_snap = True

    def _snap_to_beat(self):
        """Snap judgment_time_ms to the nearest integer beat."""
        if not self.converter:
            return
        beat = self.converter.ms_to_beat(self.judgment_time_ms)
        snapped = self.converter.beat_to_ms(round(beat))
        self.judgment_time_ms = max(0.0, snapped)

    def _on_zoom(self, event):
        delta = -event.delta / 120.0
        if delta > 0:
            self.ms_per_pixel = max(MIN_MS_PER_PIXEL, self.ms_per_pixel / ZOOM_FACTOR)
        else:
            self.ms_per_pixel = min(MAX_MS_PER_PIXEL, self.ms_per_pixel * ZOOM_FACTOR)
        self.redraw()
        if self.on_change:
            self.on_change()

    def _on_click(self, event):
        """Click to seek: move judgment line to clicked time position."""
        h = self.winfo_height()
        judgment_y = h - 50
        px_per_ms = 1.0 / self.ms_per_pixel
        time_ms = self.judgment_time_ms + (judgment_y - event.y) / px_per_ms
        if time_ms >= 0:
            self.judgment_time_ms = time_ms
            self.redraw()
            if self.on_seek:
                self.on_seek(time_ms)

    def _on_right_click(self, event):
        """Right-click on a time-position line: add/delete gimmick."""
        closest = self.find_closest(event.x, event.y)
        if not closest:
            return
        items = self.find_overlapping(event.x - 2, event.y - 2,
                                      event.x + 2, event.y + 2)
        for item_id in items:
            tags = self.gettags(item_id)
            for tag in tags:
                if tag.startswith("timeline_"):
                    time_ms = float(tag.split("_", 1)[1])
                    if self.on_line_right_click:
                        self.on_line_right_click(time_ms)
                    return

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        lane_w = w / 4.0
        judgment_y = h - 50
        px_per_ms = 1.0 / self.ms_per_pixel

        # Lane separator lines
        for i in range(1, 4):
            x = i * lane_w
            self.create_line(x, 0, x, h, fill=COLOR_LANE_LINE, width=1)

        # Judgment line
        self.create_line(
            0, judgment_y, w, judgment_y,
            fill=COLOR_JUDGMENT_LINE, width=3,
        )
        self.create_text(
            5, judgment_y - 5, anchor="sw",
            text="判定线", fill=COLOR_JUDGMENT_LINE,
            font=("Microsoft YaHei", 8),
        )

        # Visible time range
        # Top of canvas (y=0): time = judgment_time + judgment_y * ms_per_pixel (furthest future)
        # Bottom of canvas (y=h): time = judgment_time - (h-judgment_y) * ms_per_pixel (slightly past)
        max_time = self.judgment_time_ms + judgment_y * self.ms_per_pixel
        min_time = self.judgment_time_ms - (h - judgment_y) * self.ms_per_pixel

        # Draw beat markers
        self._draw_beat_markers(w, judgment_y, px_per_ms, min_time, max_time)

        # Draw notes in visible range
        for note in self.notes:
            if note.time_ms + (note.length_ms or 0) < min_time:
                continue
            if note.time_ms > max_time:
                break

            y = judgment_y - (note.time_ms - self.judgment_time_ms) * px_per_ms

            # Color
            if note.snm == 1:
                color = COLOR_NOTE_MINE
            elif note.width == 2 and note.lane == 0:
                color = COLOR_NOTE_WIDE_01
            elif note.width == 2 and note.lane == 2:
                color = COLOR_NOTE_WIDE_23
            else:
                color = COLOR_NOTE_SINGLE

            # Position — height uses single-lane width for uniform look
            nx = note.lane * lane_w + 2
            nw = max(4, note.width * lane_w - 4)
            nh = max(2, lane_w / NOTE_HEIGHT_RATIO)

            # Head
            self.create_rectangle(
                nx, y, nx + nw, y + nh,
                fill=color, outline="",
            )

            # Hold body — extends upward from head (tail is later time, higher on screen)
            if note.length_ms > 0:
                hold_h = note.length_ms * px_per_ms
                hold_top = y - hold_h
                hold_bot = y + nh
                if hold_bot - hold_top < 2:
                    hold_top = hold_bot - 2
                self.create_rectangle(
                    nx, hold_top, nx + nw, hold_bot,
                    fill=color, outline="", stipple="gray25",
                )

        # Draw time-position lines extending right
        self._draw_time_lines(w, lane_w, judgment_y, px_per_ms, min_time, max_time)

    def _draw_time_lines(self, w, lane_w, judgment_y, px_per_ms,
                         min_time, max_time):
        """Draw horizontal dashed lines from notes to the right edge.

        Lines are drawn at each unique note time. Multiple notes at the same
        time share one line extending from the rightmost note.
        """
        # Group notes by rounded time (ms) to handle floating point
        time_groups: dict[int, list[Note]] = {}
        for note in self.notes:
            t = round(note.time_ms)
            if t < min_time or t > max_time:
                continue
            time_groups.setdefault(t, []).append(note)

        base_nh = max(2, lane_w / NOTE_HEIGHT_RATIO)

        for t, notes in time_groups.items():
            first = notes[0]
            y = judgment_y - (first.time_ms - self.judgment_time_ms) * px_per_ms
            if y < 0 or y > self.winfo_height():
                continue

            # Rightmost x among notes at this time
            max_x = 0.0
            for n in notes:
                nx = n.lane * lane_w + 2
                nw = max(4, n.width * lane_w - 4)
                max_x = max(max_x, nx + nw)

            line_y = y + base_nh / 2.0
            tag = f"timeline_{t}"
            self.create_line(
                max_x + 4, line_y, w - 4, line_y,
                fill="#888888", width=1, dash=(2, 4),
                tags=(tag,),
            )

    def _draw_beat_markers(self, w, judgment_y, px_per_ms, min_time, max_time):
        """Draw beat-based grid lines with beat number labels."""
        if not self.converter:
            return

        beat_interval = self._beat_interval()  # beats between grid lines

        # Find the beat range visible on screen
        min_beat = self.converter.ms_to_beat(max(0, min_time))
        max_beat = self.converter.ms_to_beat(max(0, max_time))

        # Start from the first grid line beat
        start_beat = int(min_beat / beat_interval) * beat_interval
        if start_beat < 0:
            start_beat = 0.0

        b = start_beat
        while b <= max_beat + beat_interval:
            ms = self.converter.beat_to_ms(b)
            y = judgment_y - (ms - self.judgment_time_ms) * px_per_ms

            if 0 <= y <= self.winfo_height():
                # Is this a whole beat?
                is_whole = abs(b - round(b)) < 0.001

                if is_whole:
                    # Solid line for whole beats
                    self.create_line(
                        0, y, w, y,
                        fill=COLOR_BEAT_MAJOR, width=1,
                    )
                    # Beat number label on the left
                    self.create_text(
                        6, y - 3, anchor="w",
                        text=str(int(round(b))),
                        fill=COLOR_BEAT_LABEL,
                        font=("Consolas", 8),
                    )
                else:
                    # Dashed line for sub-beats
                    self.create_line(
                        0, y, w, y,
                        fill=COLOR_BEAT_MINOR, width=1, dash=(2, 4),
                    )

            b += beat_interval


# ---------------------------------------------------------------------------
# GimmickCanvas — right panel showing gimmick bars aligned with notes
# ---------------------------------------------------------------------------

class GimmickCanvas(tk.Canvas):
    """Multi-column grid for editing gimmicks, aligned with the note chart."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLOR_BG, highlightthickness=0, **kw)
        self.gimmicks: list[Gimmick] = []
        self.judgment_time_ms: float = 0.0
        self.ms_per_pixel: float = DEFAULT_MS_PER_PIXEL
        self.converter: BeatConverter | None = None
        self.selected_index: int = -1
        self.num_cols: int = GIMMICK_COLUMNS
        self.subdivision: int = DEFAULT_SUBDIVISION
        self._col_assign: dict[int, int] = {}  # gimmick index → column

        self.on_gimmick_click = None  # callback(index, beat, column)
        self.on_change = None
        self._needs_snap: bool = False

        self.bind("<MouseWheel>", self._on_scroll)
        self.bind("<Control-MouseWheel>", self._on_zoom)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.redraw())

    def set_on_change(self, cb):
        self.on_change = cb

    def set_on_gimmick_click(self, cb):
        self.on_gimmick_click = cb

    def set_gimmicks(self, gimmicks: list[Gimmick], converter: BeatConverter):
        self.gimmicks = gimmicks
        self.converter = converter
        self.selected_index = -1
        self._assign_columns()
        self.redraw()

    def set_selected(self, index: int):
        self.selected_index = index
        self.redraw()

    def set_subdivision(self, sub: int):
        self.subdivision = sub
        self.redraw()

    def _beat_interval(self) -> float:
        return 4.0 / self.subdivision

    def _scroll_amount_ms(self) -> float:
        if not self.converter:
            return 200.0
        beat_interval = self._beat_interval()
        bpm_now = self._bpm_at(self.judgment_time_ms)
        return beat_interval * (60000.0 / bpm_now)

    def _bpm_at(self, time_ms: float) -> float:
        if not self.converter or not self.converter.timing:
            return 120.0
        bpm = self.converter.timing[0].bpm
        for tp in self.converter.timing:
            if tp.time_ms <= time_ms:
                bpm = tp.bpm
        return bpm

    def _assign_columns(self):
        """Assign each gimmick to a column, avoiding overlap within columns.

        Gimmicks at the same beat are spread across different columns.
        Gimmicks with duration=0 still occupy a minimum slot so they don't
        all land in column 0.
        """
        self._col_assign.clear()
        col_free_at = [0.0] * self.num_cols  # beat when each column becomes free

        indexed = sorted(enumerate(self.gimmicks), key=lambda x: x[1].beat)
        for orig_idx, g in indexed:
            # Minimum occupancy of 0.01 beats so same-beat gimmicks spread out
            g_end = g.beat + max(g.duration, 0.01)
            best_col = 0
            for c in range(self.num_cols):
                if col_free_at[c] <= g.beat + 0.0005:
                    best_col = c
                    break
            else:
                best_col = min(range(self.num_cols),
                               key=lambda c: col_free_at[c])
            col_free_at[best_col] = max(col_free_at[best_col], g_end)
            self._col_assign[orig_idx] = best_col

    def _on_scroll(self, event):
        delta = -event.delta / 120.0
        scroll_ms = delta * self._scroll_amount_ms()
        self.judgment_time_ms = max(0.0, self.judgment_time_ms + scroll_ms)
        if self._needs_snap:
            self._snap_to_beat()
            self._needs_snap = False
        self.redraw()
        if self.on_change:
            self.on_change()

    def set_needs_snap(self):
        """Next scroll will snap to the nearest beat."""
        self._needs_snap = True

    def _snap_to_beat(self):
        """Snap judgment_time_ms to the nearest integer beat."""
        if not self.converter:
            return
        beat = self.converter.ms_to_beat(self.judgment_time_ms)
        snapped = self.converter.beat_to_ms(round(beat))
        self.judgment_time_ms = max(0.0, snapped)

    def _on_zoom(self, event):
        delta = -event.delta / 120.0
        if delta > 0:
            self.ms_per_pixel = max(MIN_MS_PER_PIXEL, self.ms_per_pixel / ZOOM_FACTOR)
        else:
            self.ms_per_pixel = min(MAX_MS_PER_PIXEL, self.ms_per_pixel * ZOOM_FACTOR)
        self.redraw()
        if self.on_change:
            self.on_change()

    def _on_click(self, event):
        """Click on gimmick grid: select existing or prepare new at beat+col."""
        if not self.converter:
            return

        h = self.winfo_height()
        w = self.winfo_width()
        judgment_y = h - 50
        px_per_ms = 1.0 / self.ms_per_pixel

        # Determine column from x position
        col_w = w / self.num_cols
        col = min(int(event.x / col_w), self.num_cols - 1)

        # Convert y to time, then to beat
        time_ms = self.judgment_time_ms + (judgment_y - event.y) / px_per_ms
        beat = self.converter.ms_to_beat(time_ms)

        # Check if click hits an existing gimmick in this column
        clicked_index = -1
        min_gh = max(8, col_w / NOTE_HEIGHT_RATIO)
        for i, g in enumerate(self.gimmicks):
            c = self._col_assign.get(i, 0)
            if c != col:
                continue
            g_start_ms = self.converter.beat_to_ms(g.beat)
            g_start_y = judgment_y - (g_start_ms - self.judgment_time_ms) * px_per_ms
            # Head: y in [g_start_y, g_start_y + min_gh]
            head_bot = g_start_y + min_gh
            # Body: y in [g_start_y - dur_px, g_start_y]
            g_dur_ms = (
                self.converter.beat_to_ms(g.beat + max(g.duration, 0.0))
                - g_start_ms
            )
            dur_px = g_dur_ms * px_per_ms
            body_top = g_start_y - dur_px
            # Click must be within head or body
            if (g_start_y <= event.y <= head_bot) or (
                dur_px > 1 and body_top <= event.y <= g_start_y
            ):
                clicked_index = i
                break

        if clicked_index >= 0:
            self.selected_index = clicked_index
        else:
            self.selected_index = -1

        self.redraw()
        if self.on_gimmick_click:
            self.on_gimmick_click(self.selected_index, beat, col)

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10 or not self.converter:
            return

        judgment_y = h - 50
        px_per_ms = 1.0 / self.ms_per_pixel
        col_w = w / self.num_cols

        # Header
        self.create_rectangle(0, 0, w, 24, fill=COLOR_PANEL_BG, outline="")
        self.create_text(
            w / 2, 12, text="特效编辑区", fill=COLOR_TEXT,
            font=("Microsoft YaHei", 9, "bold"),
        )

        # Column grid lines
        for c in range(1, self.num_cols):
            x = c * col_w
            self.create_line(
                x, 24, x, h,
                fill=COLOR_GIMMICK_GRID, width=1, dash=(1, 3),
            )

        # Horizontal beat-based grid lines (match note canvas)
        if self.converter:
            beat_interval = self._beat_interval()
            min_beat = self.converter.ms_to_beat(
                max(0, self.judgment_time_ms - (h - judgment_y) * self.ms_per_pixel)
            )
            max_beat = self.converter.ms_to_beat(
                max(0, self.judgment_time_ms + judgment_y * self.ms_per_pixel)
            )
            start_beat = int(min_beat / beat_interval) * beat_interval
            if start_beat < 0:
                start_beat = 0.0
            bb = start_beat
            while bb <= max_beat + beat_interval:
                bms = self.converter.beat_to_ms(bb)
                gy = judgment_y - (bms - self.judgment_time_ms) * px_per_ms
                if 24 <= gy <= h:
                    is_whole = abs(bb - round(bb)) < 0.001
                    if is_whole:
                        self.create_line(
                            0, gy, w, gy,
                            fill=COLOR_BEAT_MAJOR, width=1,
                        )
                    else:
                        self.create_line(
                            0, gy, w, gy,
                            fill=COLOR_BEAT_MINOR, width=1, dash=(1, 3),
                        )
                bb += beat_interval

        # Judgment line
        self.create_line(
            0, judgment_y, w, judgment_y,
            fill=COLOR_JUDGMENT_LINE, width=2, dash=(4, 4),
        )

        # Minimum clickable height for gimmick rectangles
        min_gimmick_h = max(8, col_w / NOTE_HEIGHT_RATIO)

        # Draw gimmicks as green rectangles
        for i, g in enumerate(self.gimmicks):
            try:
                g_start_ms = self.converter.beat_to_ms(g.beat)
                g_dur_ms = (
                    self.converter.beat_to_ms(g.beat + max(g.duration, 0.0))
                    - g_start_ms
                )
            except Exception:
                continue

            y1 = judgment_y - (g_start_ms - self.judgment_time_ms) * px_per_ms
            dur_h = g_dur_ms * px_per_ms

            if y1 + min_gimmick_h < 0 or y1 - dur_h > h:
                continue

            col = self._col_assign.get(i, 0)
            gx1 = col * col_w + 2
            gx2 = gx1 + col_w - 4

            is_sel = (i == self.selected_index)
            fill_color = COLOR_GIMMICK_SELECTED if is_sel else COLOR_GIMMICK_NORMAL
            outline_color = COLOR_GIMMICK_SELECTED if is_sel else ""
            outline_w = 2 if is_sel else 0

            # Head rectangle (like a note) — always at least min_gimmick_h tall
            head_bot = y1 + min_gimmick_h
            self.create_rectangle(
                gx1, y1, gx2, head_bot,
                fill=fill_color, outline=outline_color, width=outline_w,
            )
            # Duration body — extends upward from head (like hold notes)
            if dur_h > 1:
                body_top = y1 - dur_h
                body_bot = y1
                if body_bot - body_top < 1:
                    body_top = body_bot - 1
                self.create_rectangle(
                    gx1, body_top, gx2, body_bot,
                    fill=fill_color, outline="", stipple="gray25",
                )

            # Label inside the head
            if col_w > 40:
                short = g.modname if len(g.modname) <= 10 else g.modname[:9] + "…"
                self.create_text(
                    (gx1 + gx2) / 2, y1 + min_gimmick_h / 2,
                    text=short, fill="#FFF" if not is_sel else "#000",
                    font=("Microsoft YaHei", 7),
                )


# ---------------------------------------------------------------------------
# ParamPanel — top bar for editing gimmick parameters
# ---------------------------------------------------------------------------

class ParamPanel(tk.Frame):
    """Horizontal parameter editor for the selected gimmick."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLOR_PANEL_BG, **kw)
        self.on_add = None
        self.on_update = None
        self.on_delete = None
        self._editing_index: int = -1
        self._pending_beat: float = 0.0

        self._build()

    def _build(self):
        bg = COLOR_PANEL_BG
        fg = COLOR_TEXT

        # --- Row 0: Labels ---
        labels = [
            ("起始拍数", 12), ("持续时间(拍)", 12), ("缓动函数", 16),
            ("参数1", 10), ("_", 3), ("参数2", 10), ("_", 3),
            ("特效名", 14), ("轨道代理", 10),
        ]
        col = 0
        for text, width in labels:
            tk.Label(
                self, text=text, bg=bg, fg=fg,
                font=("Microsoft YaHei", 8),
            ).grid(row=0, column=col, padx=2, pady=2, sticky="w")
            col += 1

        # --- Row 1: Inputs ---
        self.beat_var = tk.StringVar(value="0")
        self.beat_entry = tk.Entry(
            self, textvariable=self.beat_var, width=10,
            font=("Consolas", 10),
        )
        self.beat_entry.grid(row=1, column=0, padx=2, pady=2)

        self.dur_var = tk.StringVar(value="0")
        self.dur_entry = tk.Entry(
            self, textvariable=self.dur_var, width=10,
            font=("Consolas", 10),
        )
        self.dur_entry.grid(row=1, column=1, padx=2, pady=2)

        self.easing_var = tk.StringVar(value=EASINGS[0])
        self.easing_cb = ttk.Combobox(
            self, textvariable=self.easing_var, values=EASINGS,
            state="readonly", width=18, font=("Consolas", 9),
        )
        self.easing_cb.grid(row=1, column=2, padx=2, pady=2)

        self.v1_var = tk.StringVar(value="0")
        self.v1_entry = tk.Entry(
            self, textvariable=self.v1_var, width=8,
            font=("Consolas", 10),
        )
        self.v1_entry.grid(row=1, column=3, padx=2, pady=2)

        self.v1_blank = tk.BooleanVar(value=False)
        self.v1_cb = tk.Checkbutton(
            self, variable=self.v1_blank, bg=bg,
            command=self._on_v1_blank,
        )
        self.v1_cb.grid(row=1, column=4, padx=0, pady=2)

        self.v2_var = tk.StringVar(value="0")
        self.v2_entry = tk.Entry(
            self, textvariable=self.v2_var, width=8,
            font=("Consolas", 10),
        )
        self.v2_entry.grid(row=1, column=5, padx=2, pady=2)

        self.v2_blank = tk.BooleanVar(value=False)
        self.v2_cb = tk.Checkbutton(
            self, variable=self.v2_blank, bg=bg,
            command=self._on_v2_blank,
        )
        self.v2_cb.grid(row=1, column=6, padx=0, pady=2)

        self.modname_var = tk.StringVar(value=EFFECTS[0])
        self.modname_cb = ttk.Combobox(
            self, textvariable=self.modname_var, values=EFFECTS,
            state="readonly", width=16, font=("Consolas", 9),
        )
        self.modname_cb.grid(row=1, column=7, padx=2, pady=2)

        self.proxy_var = tk.StringVar(value="-1")
        self.proxy_entry = tk.Entry(
            self, textvariable=self.proxy_var, width=6,
            font=("Consolas", 10),
        )
        self.proxy_entry.grid(row=1, column=8, padx=2, pady=2)

        # Buttons
        btn_frame = tk.Frame(self, bg=bg)
        btn_frame.grid(row=1, column=9, padx=4, pady=2)

        self.add_btn = tk.Button(
            btn_frame, text="添加", command=self._do_add,
            bg="#2A6B3F", fg=fg, font=("Microsoft YaHei", 9),
            relief=tk.FLAT, padx=10,
        )
        self.add_btn.pack(side=tk.LEFT, padx=2)

        self.update_btn = tk.Button(
            btn_frame, text="更新", command=self._do_update,
            bg="#2A4A6B", fg=fg, font=("Microsoft YaHei", 9),
            relief=tk.FLAT, padx=10,
        )
        self.update_btn.pack(side=tk.LEFT, padx=2)

        self.delete_btn = tk.Button(
            btn_frame, text="删除", command=self._do_delete,
            bg="#6B2A2A", fg=fg, font=("Microsoft YaHei", 9),
            relief=tk.FLAT, padx=10,
        )
        self.delete_btn.pack(side=tk.LEFT, padx=2)

    def set_callbacks(self, on_add, on_update, on_delete):
        self.on_add = on_add
        self.on_update = on_update
        self.on_delete = on_delete

    def set_beat_only(self, beat: float):
        """Update only the beat field without resetting other fields."""
        self.beat_var.set(f"{beat:.4f}")

    def set_editing(self, index: int, beat: float):
        """Called when a gimmick is selected or a new position is clicked."""
        self._editing_index = index
        self._pending_beat = beat
        if index >= 0:
            self.add_btn.configure(state=tk.DISABLED)
            self.update_btn.configure(state=tk.NORMAL)
            self.delete_btn.configure(state=tk.NORMAL)
        else:
            self.add_btn.configure(state=tk.NORMAL)
            self.update_btn.configure(state=tk.DISABLED)
            self.delete_btn.configure(state=tk.DISABLED)
            # Pre-fill beat for new gimmick
            self.beat_var.set(f"{beat:.4f}")
            self.dur_var.set("0")
            self.easing_var.set(EASINGS[0])
            self.v1_var.set("0")
            self.v1_blank.set(False)
            self._on_v1_blank()
            self.v2_var.set("0")
            self.v2_blank.set(False)
            self._on_v2_blank()
            self.modname_var.set(EFFECTS[0])
            self.proxy_var.set("-1")

    def show_gimmick(self, g: Gimmick, index: int):
        """Populate fields from a Gimmick object."""
        self._editing_index = index
        self.beat_var.set(str(g.beat))
        self.dur_var.set(str(g.duration))
        self.easing_var.set(g.easing)

        if g.value1 == "_":
            self.v1_blank.set(True)
            self._on_v1_blank()
        else:
            self.v1_blank.set(False)
            self.v1_var.set(g.value1)
            self._on_v1_blank()

        if g.value2 == "_":
            self.v2_blank.set(True)
            self._on_v2_blank()
        else:
            self.v2_blank.set(False)
            self.v2_var.set(g.value2)
            self._on_v2_blank()

        if g.modname in EFFECTS:
            self.modname_var.set(g.modname)
        self.proxy_var.set(g.proxy)

        self.add_btn.configure(state=tk.DISABLED)
        self.update_btn.configure(state=tk.NORMAL)
        self.delete_btn.configure(state=tk.NORMAL)

    def _on_v1_blank(self):
        if self.v1_blank.get():
            self.v1_entry.configure(state=tk.DISABLED)
        else:
            self.v1_entry.configure(state=tk.NORMAL)

    def _on_v2_blank(self):
        if self.v2_blank.get():
            self.v2_entry.configure(state=tk.DISABLED)
        else:
            self.v2_entry.configure(state=tk.NORMAL)

    def _collect(self) -> Gimmick:
        v1 = "_" if self.v1_blank.get() else self.v1_var.get().strip()
        v2 = "_" if self.v2_blank.get() else self.v2_var.get().strip()
        return Gimmick(
            beat=float(self.beat_var.get().strip()),
            duration=float(self.dur_var.get().strip()),
            easing=self.easing_var.get(),
            value1=v1,
            value2=v2,
            modname=self.modname_var.get(),
            proxy=self.proxy_var.get().strip(),
        )

    def _do_add(self):
        if self.on_add:
            self.on_add(self._collect())

    def _do_update(self):
        if self.on_update and self._editing_index >= 0:
            self.on_update(self._editing_index, self._collect())

    def _do_delete(self):
        if self.on_delete and self._editing_index >= 0:
            self.on_delete(self._editing_index)


# ---------------------------------------------------------------------------
# AudioBar — bottom bar with playback controls
# ---------------------------------------------------------------------------

class AudioBar(tk.Frame):
    """Play/pause button and seekable progress bar."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLOR_PANEL_BG, **kw)
        self.bg = COLOR_PANEL_BG
        self.fg = COLOR_TEXT

        self._duration_ms: float = 0.0
        self._position_ms: float = 0.0
        self._playing: bool = False
        self._seeking: bool = False

        self.on_play = None
        self.on_pause = None
        self.on_seek = None
        self.on_seek_live = None  # fired continuously during drag

        self._build()

    def _build(self):
        # Play/Pause button
        self.play_btn = tk.Button(
            self, text="▶ 播放", command=self._toggle_play,
            bg="#2A4A6B", fg=self.fg,
            font=("Microsoft YaHei", 10),
            relief=tk.FLAT, padx=14, pady=4,
        )
        self.play_btn.pack(side=tk.LEFT, padx=8, pady=6)

        # Time label
        self.time_label = tk.Label(
            self, text="00:00.0 / 00:00.0",
            bg=self.bg, fg=self.fg,
            font=("Consolas", 11),
        )
        self.time_label.pack(side=tk.LEFT, padx=6, pady=6)

        # Progress scale
        self.scale_var = tk.DoubleVar(value=0.0)
        self.scale = tk.Scale(
            self, variable=self.scale_var, from_=0, to=1000,
            orient=tk.HORIZONTAL, showvalue=False,
            bg=self.bg, fg=self.fg, troughcolor="#333",
            highlightthickness=0, relief=tk.FLAT,
            command=self._on_scale_drag,
        )
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)

        # Bind events for seeking
        self.scale.bind("<ButtonPress-1>", self._on_seek_start)
        self.scale.bind("<ButtonRelease-1>", self._on_seek_end)
        self.scale.bind("<B1-Motion>", self._on_seek_drag)

    def set_duration(self, ms: float):
        self._duration_ms = ms
        self._update_display()

    def set_position(self, ms: float):
        if not self._seeking:
            self._position_ms = ms
            if self._duration_ms > 0:
                self.scale_var.set(ms / self._duration_ms * 1000.0)
            self._update_display()

    def get_position(self) -> float:
        return self._position_ms

    def is_playing(self) -> bool:
        return self._playing

    def _update_display(self):
        pos = self._position_ms
        dur = self._duration_ms
        pm = int(pos / 60000)
        ps = (pos % 60000) / 1000.0
        dm = int(dur / 60000)
        ds = (dur % 60000) / 1000.0
        self.time_label.configure(
            text=f"{pm:02d}:{ps:04.1f} / {dm:02d}:{ds:04.1f}"
        )

    def set_playing(self, playing: bool):
        self._playing = playing
        if playing:
            self.play_btn.configure(text="⏸ 暂停")
        else:
            self.play_btn.configure(text="▶ 播放")

    def _toggle_play(self):
        if self._playing:
            if self.on_pause:
                self.on_pause()
        else:
            if self.on_play:
                self.on_play()

    def _on_seek_start(self, event):
        self._seeking = True

    def _on_seek_drag(self, event):
        if self._seeking and self._duration_ms > 0:
            frac = self.scale_var.get() / 1000.0
            self._position_ms = frac * self._duration_ms
            self._update_display()
            if self.on_seek_live:
                self.on_seek_live(self._position_ms)

    def _on_seek_end(self, event):
        self._seeking = False
        if self.on_seek and self._duration_ms > 0:
            frac = self.scale_var.get() / 1000.0
            pos = frac * self._duration_ms
            self.on_seek(pos)

    def _on_scale_drag(self, val):
        pass  # handled by seek events
