"""Gimmick Editor — main entry point and application window."""

import ctypes
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from model import Chart, Gimmick, BeatConverter
from io_handler import load_chart, load_vsm, save_vsm
from mci_audio import MCIAudio
from widgets import (
    InfoPanel, NoteCanvas, GimmickCanvas, ParamPanel, AudioBar,
)
from config import (
    COLOR_BG, COLOR_PANEL_BG, COLOR_TEXT,
    DEFAULT_MS_PER_PIXEL, NOTE_CANVAS_WIDTH,
    DEFAULT_SUBDIVISION, SUBDIVISION_OPTIONS,
)


def _get_refresh_interval_ms() -> int:
    """Detect the primary monitor refresh rate and return frame interval in ms.

    Uses GetDeviceCaps(VREFRESH). Clamped to 4–33ms (30–240 fps).
    """
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if hdc:
            rate = gdi32.GetDeviceCaps(hdc, 116)  # VREFRESH = 116
            user32.ReleaseDC(0, hdc)
            if rate >= 30:
                interval = int(1000.0 / rate)
                return max(4, min(33, interval))
    except Exception:
        pass
    return 16  # fallback: ~60 fps


class GimmickEditor(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Gimmick Editor — 谱面特效编辑器")
        self.geometry("1280x800")
        self.configure(bg=COLOR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.chart: Chart | None = None
        self._chart_folder: str = ""
        self._diff_index: int = 0
        self._gimmicks: list[Gimmick] = []
        self._converter: BeatConverter | None = None
        self._dirty: bool = False
        self._subdivision: int = DEFAULT_SUBDIVISION
        self._frame_ms: int = _get_refresh_interval_ms()

        # Audio
        self._audio = MCIAudio()
        self._audio_loaded: bool = False
        self._update_job: str | None = None

        self._build_menu()
        self._build_layout()
        self._wire_callbacks()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        self.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开谱面文件夹...", command=self._open_folder)
        file_menu.add_command(label="保存特效", command=self._save)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        # Subdivision menu — beat grid density
        self._sub_var = tk.IntVar(value=DEFAULT_SUBDIVISION)
        sub_menu = tk.Menu(menubar, tearoff=0)
        for opt in SUBDIVISION_OPTIONS:
            sub_menu.add_radiobutton(
                label=str(opt),
                variable=self._sub_var,
                value=opt,
                command=self._on_subdivision_changed,
            )
        menubar.add_cascade(label="拍数", menu=sub_menu)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self):
        # Difficulty selector row
        diff_frame = tk.Frame(self, bg=COLOR_PANEL_BG)
        diff_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Label(
            diff_frame, text="当前难度:", bg=COLOR_PANEL_BG, fg=COLOR_TEXT,
            font=("Microsoft YaHei", 10),
        ).pack(side=tk.LEFT, padx=8, pady=4)
        self.diff_var = tk.StringVar(value="未打开谱面")
        self.diff_cb = ttk.Combobox(
            diff_frame, textvariable=self.diff_var,
            state="disabled", width=30, font=("Microsoft YaHei", 10),
        )
        self.diff_cb.pack(side=tk.LEFT, padx=4, pady=4)
        self.diff_cb.bind("<<ComboboxSelected>>", self._on_diff_changed)

        self.status_label = tk.Label(
            diff_frame, text="  请打开谱面文件夹开始编辑",
            bg=COLOR_PANEL_BG, fg="#888",
            font=("Microsoft YaHei", 9),
        )
        self.status_label.pack(side=tk.LEFT, padx=12, pady=4)

        # Param panel (top)
        self.param_panel = ParamPanel(self)
        self.param_panel.pack(side=tk.TOP, fill=tk.X)

        # Main content area
        main_frame = tk.Frame(self, bg=COLOR_BG)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Info panel (left)
        self.info_panel = InfoPanel(main_frame, width=200)
        self.info_panel.pack(side=tk.LEFT, fill=tk.Y)

        # Note canvas (center) — fixed width
        self.note_canvas = NoteCanvas(main_frame, width=NOTE_CANVAS_WIDTH)
        self.note_canvas.pack(side=tk.LEFT, fill=tk.Y)

        # Gimmick canvas (right) — fills remaining space
        self.gimmick_canvas = GimmickCanvas(main_frame)
        self.gimmick_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Audio bar (bottom)
        self.audio_bar = AudioBar(self)
        self.audio_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def _wire_callbacks(self):
        # Sync scroll between note and gimmick canvases
        self.note_canvas.set_on_change(self._sync_to_gimmick)
        self.gimmick_canvas.set_on_change(self._sync_to_notes)

        # Click on note view → seek
        self.note_canvas.set_on_seek(self._on_note_view_seek)

        # Right-click on time-position line → add/delete gimmick
        self.note_canvas.set_on_line_right_click(self._on_line_right_click)

        # Gimmick click → param panel
        self.gimmick_canvas.set_on_gimmick_click(self._on_gimmick_selected)

        # Param panel actions
        self.param_panel.set_callbacks(
            on_add=self._on_add_gimmick,
            on_update=self._on_update_gimmick,
            on_delete=self._on_delete_gimmick,
        )

        # Audio controls
        self.audio_bar.on_play = self._audio_play
        self.audio_bar.on_pause = self._audio_pause
        self.audio_bar.on_seek = self._audio_seek
        self.audio_bar.on_seek_live = self._on_seek_live

        # Keyboard shortcuts
        self.bind("<space>", lambda e: self.audio_bar._toggle_play())

    def _sync_to_gimmick(self):
        self.gimmick_canvas.judgment_time_ms = self.note_canvas.judgment_time_ms
        self.gimmick_canvas.ms_per_pixel = self.note_canvas.ms_per_pixel
        self.gimmick_canvas.redraw()
        self.audio_bar.set_position(self.note_canvas.judgment_time_ms)
        self._update_param_beat(self.note_canvas.judgment_time_ms)

    def _sync_to_notes(self):
        self.note_canvas.judgment_time_ms = self.gimmick_canvas.judgment_time_ms
        self.note_canvas.ms_per_pixel = self.gimmick_canvas.ms_per_pixel
        self.note_canvas.redraw()
        self.audio_bar.set_position(self.gimmick_canvas.judgment_time_ms)
        self._update_param_beat(self.gimmick_canvas.judgment_time_ms)

    def _update_param_beat(self, time_ms: float):
        """Update the beat field in the param panel to reflect view position."""
        if self._converter:
            beat = self._converter.ms_to_beat(time_ms)
            self.param_panel.set_beat_only(beat)

    def _on_subdivision_changed(self):
        sub = self._sub_var.get()
        self._subdivision = sub
        self.note_canvas.set_subdivision(sub)
        self.gimmick_canvas.set_subdivision(sub)

    def _on_note_view_seek(self, time_ms: float):
        """Called when user clicks on note view to seek to a time."""
        self.audio_bar.set_position(time_ms)
        if self._audio_loaded:
            self._audio.seek(time_ms)
            if self.audio_bar.is_playing():
                self._audio.play(time_ms)
        self._sync_to_gimmick()

    def _on_line_right_click(self, time_ms: float):
        """Right-click on a time-position line: add or delete gimmick."""
        if not self._converter:
            return
        beat = self._converter.ms_to_beat(time_ms)

        # Check if a gimmick already exists near this beat
        tol = 0.05
        existing_idx = None
        for i, g in enumerate(self._gimmicks):
            if abs(g.beat - beat) < tol:
                existing_idx = i
                break

        if existing_idx is not None:
            # Delete existing gimmick
            g = self._gimmicks[existing_idx]
            del self._gimmicks[existing_idx]
            self._dirty = True
            self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
            self.param_panel.set_editing(-1, beat)
            self._update_title()
            self.status_label.configure(
                text=f"  已删除特效: {g.modname} @ beat {g.beat:.3f}"
            )
        else:
            # Add new gimmick with defaults
            g = Gimmick(
                beat=round(beat, 6),
                duration=0,
                easing="linear",
                value1="0",
                value2="0",
                modname="scrollspeed",
                proxy="-1",
            )
            self._gimmicks.append(g)
            self._gimmicks.sort(key=lambda x: x.beat)
            self._dirty = True
            self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
            self.param_panel.set_editing(-1, beat)
            self._update_title()
            self.status_label.configure(
                text=f"  已添加特效: {g.modname} @ beat {g.beat:.4f}"
            )

    # ------------------------------------------------------------------
    # Folder / chart loading
    # ------------------------------------------------------------------
    def _open_folder(self):
        folder = filedialog.askdirectory(title="选择谱面文件夹")
        if not folder:
            return

        try:
            self.chart = load_chart(folder)
        except ValueError as e:
            messagebox.showerror("打开失败", str(e))
            return

        self._chart_folder = folder

        if not self.chart.difficulties:
            messagebox.showerror("打开失败", "谱面文件中没有找到任何难度")
            self.chart = None
            return

        # Populate difficulty dropdown
        diff_names = []
        for d in self.chart.difficulties:
            name = d.meta.diff1 or d.meta.diff_name or "未命名"
            rating = d.meta.diff2 or ""
            diff_names.append(f"{name} ({rating})" if rating else name)

        self.diff_cb.configure(state="readonly", values=diff_names)
        self.diff_cb.current(0)
        self._diff_index = 0
        self._load_difficulty(0)

        self.status_label.configure(
            text=f"  已打开: {os.path.basename(folder)}  |  "
                 f"{len(self.chart.difficulties)} 个难度"
        )

        self._load_audio()

    def _load_difficulty(self, index: int):
        if not self.chart:
            return
        diff = self.chart.difficulties[index]
        self._diff_index = index
        self._converter = BeatConverter(diff.timing_points)

        # Reset view
        self.note_canvas.judgment_time_ms = 0.0
        self.note_canvas.ms_per_pixel = DEFAULT_MS_PER_PIXEL
        self.note_canvas.set_converter(self._converter)
        self.note_canvas.set_subdivision(self._subdivision)
        self.note_canvas.set_notes(diff.notes)

        # Load VSM
        vsm_path = self._vsm_path(diff)
        self._gimmicks = load_vsm(vsm_path)
        self._dirty = False

        self.gimmick_canvas.judgment_time_ms = 0.0
        self.gimmick_canvas.ms_per_pixel = DEFAULT_MS_PER_PIXEL
        self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
        self.gimmick_canvas.set_subdivision(self._subdivision)
        self.gimmick_canvas.set_selected(-1)

        self.param_panel.set_editing(-1, 0.0)

        self.info_panel.set_info(self.chart, index)

        # Reset audio position to 0 for the new difficulty
        self.audio_bar.set_position(0.0)
        if self._audio_loaded:
            self._audio.seek(0.0)

        self._update_title()

    def _vsm_path(self, diff) -> str:
        """Get the .vsm file path for a difficulty."""
        name = diff.meta.diff1 or diff.meta.diff_name or "unnamed"
        return os.path.join(self._chart_folder, f"{name}.vsm")

    def _on_diff_changed(self, event=None):
        idx = self.diff_cb.current()
        if idx >= 0 and self.chart and idx < len(self.chart.difficulties):
            if self._dirty:
                ok = messagebox.askyesno(
                    "未保存更改",
                    "当前难度的特效尚未保存，是否切换难度（未保存的更改将丢失）？",
                )
                if not ok:
                    self.diff_cb.current(self._diff_index)
                    return
            self._audio.pause()
            self.audio_bar.set_playing(False)
            if self._update_job:
                self.after_cancel(self._update_job)
                self._update_job = None
            self._load_difficulty(idx)

    # ------------------------------------------------------------------
    # Gimmick editing
    # ------------------------------------------------------------------
    def _on_gimmick_selected(self, index: int, beat: float, col: int = 0):
        if index >= 0 and index < len(self._gimmicks):
            g = self._gimmicks[index]
            self.param_panel.show_gimmick(g, index)
        else:
            self.param_panel.set_editing(-1, beat)

    def _on_add_gimmick(self, g: Gimmick):
        self._gimmicks.append(g)
        self._gimmicks.sort(key=lambda x: x.beat)
        self._dirty = True
        self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
        self.param_panel.set_editing(-1, g.beat)
        self._update_title()

    def _on_update_gimmick(self, index: int, g: Gimmick):
        if 0 <= index < len(self._gimmicks):
            self._gimmicks[index] = g
            self._gimmicks.sort(key=lambda x: x.beat)
            self._dirty = True
            self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
            self.param_panel.set_editing(-1, g.beat)
            self._update_title()

    def _on_delete_gimmick(self, index: int):
        if 0 <= index < len(self._gimmicks):
            del self._gimmicks[index]
            self._dirty = True
            self.gimmick_canvas.set_gimmicks(self._gimmicks, self._converter)
            self.param_panel.set_editing(-1, 0.0)
            self._update_title()

    def _update_title(self):
        title = "Gimmick Editor — 谱面特效编辑器"
        if self.chart and self._diff_index < len(self.chart.difficulties):
            dname = self.chart.difficulties[self._diff_index].meta.diff1 or "?"
            title = f"Gimmick Editor — {dname}"
        if self._dirty:
            title = "* " + title
        self.title(title)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save(self):
        if not self.chart or not self._converter:
            messagebox.showwarning("提示", "请先打开谱面文件夹")
            return
        diff = self.chart.difficulties[self._diff_index]
        vsm_path = self._vsm_path(diff)
        save_vsm(vsm_path, self._gimmicks)
        self._dirty = False
        self._update_title()
        self.status_label.configure(
            text=f"  已保存: {os.path.basename(vsm_path)}  ({len(self._gimmicks)} 个特效)"
        )

    # ------------------------------------------------------------------
    # Audio (MCI-backed, no external dependencies)
    # ------------------------------------------------------------------
    def _load_audio(self):
        self._audio_loaded = False
        self.audio_bar.set_position(0.0)
        if not self.chart or not self.chart.song_file:
            self.audio_bar.set_duration(0.0)
            return

        ok = self._audio.load(self.chart.song_file)
        if ok:
            self._audio_loaded = True
            dur = self._audio.length_ms
            self.audio_bar.set_duration(dur)
            self.audio_bar.set_position(0.0)
            ext = os.path.splitext(self.chart.song_file)[1].lower()
            self.status_label.configure(text=f"  音频已加载 ({ext}, {dur/1000:.1f}s)")
        else:
            self.status_label.configure(
                text="  音频加载失败 — MCI 不支持此格式，请使用 mp3 文件"
            )

    def _audio_play(self):
        if not self._audio_loaded:
            return
        pos_ms = self.audio_bar.get_position()
        self._audio.play(pos_ms)
        self.audio_bar.set_playing(True)
        self._start_audio_update()

    def _audio_pause(self):
        self._audio.pause()
        # Record current position
        pos = self._audio.get_position_ms()
        if pos > 0:
            self.audio_bar.set_position(pos)
        self.audio_bar.set_playing(False)
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None
        self.note_canvas.set_needs_snap()
        self.gimmick_canvas.set_needs_snap()

    def _on_seek_live(self, pos_ms: float):
        """Called continuously while dragging the progress bar."""
        self.note_canvas.judgment_time_ms = pos_ms
        self._sync_to_gimmick()
        self.note_canvas.redraw()
        self._update_param_beat(pos_ms)
        self.note_canvas.set_needs_snap()
        self.gimmick_canvas.set_needs_snap()

    def _audio_seek(self, pos_ms: float):
        """Seek to position (called when user releases progress bar)."""
        self.audio_bar.set_position(pos_ms)
        if self._audio.playing:
            self._audio.play(pos_ms)
        self.note_canvas.judgment_time_ms = pos_ms
        self._sync_to_gimmick()
        self.note_canvas.redraw()
        self.note_canvas.set_needs_snap()
        self.gimmick_canvas.set_needs_snap()

    def _start_audio_update(self):
        """Periodic update during playback (~30fps)."""
        if not self._audio_loaded:
            self._update_job = None
            return

        busy = self._audio.is_busy()
        pos = self._audio.get_position_ms()

        if not busy and pos <= 0:
            # Playback ended or not actually playing
            self.audio_bar.set_playing(False)
            self._update_job = None
            return

        dur = self._audio.length_ms
        if dur > 0 and pos >= dur - 50:
            pos = dur
            self.audio_bar.set_playing(False)
            self._update_job = None

        self.audio_bar.set_position(pos)
        self.note_canvas.judgment_time_ms = pos
        self.note_canvas.redraw()
        self._sync_to_gimmick()

        if self.audio_bar.is_playing():
            self._update_job = self.after(self._frame_ms, self._start_audio_update)
        else:
            self._update_job = None

    def _stop_audio(self):
        self._audio.stop()
        self._audio.unload()
        self._audio_loaded = False
        self.audio_bar.set_playing(False)
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None

    def _on_close(self):
        if self._dirty:
            ok = messagebox.askyesno("未保存更改", "特效尚未保存，是否退出？")
            if not ok:
                return
        self._stop_audio()
        self.destroy()


def main():
    app = GimmickEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
