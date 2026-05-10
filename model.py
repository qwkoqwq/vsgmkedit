"""Data models for chart, notes, timing, and gimmicks."""

from dataclasses import dataclass, field


@dataclass
class TimingPoint:
    """A BPM change point."""
    time_ms: float
    bpm: float
    num: int = 4
    den: int = 4


@dataclass
class Note:
    """A single note object in the chart."""
    lane: int           # 0-3
    time_ms: float      # start time in milliseconds
    width: int = 1      # 1 or 2
    snm: int = 0        # 0=normal, 1=mine, 2=treat as normal
    length_ms: float = 0.0  # hold length, 0 = normal tap


@dataclass
class DifficultyMeta:
    """Metadata for one difficulty."""
    diff_name: str = ""
    diff1: str = ""     # difficulty display name
    diff2: str = ""     # difficulty rating
    charter: str = ""


@dataclass
class Difficulty:
    """One difficulty level: notes + timing + metadata."""
    meta: DifficultyMeta = field(default_factory=DifficultyMeta)
    notes: list[Note] = field(default_factory=list)
    timing_points: list[TimingPoint] = field(default_factory=list)


@dataclass
class ChartInfo:
    """Song-level chart information."""
    name: str = ""
    composer: str = ""
    display_bpm: str = ""


@dataclass
class Chart:
    """Complete chart with all difficulties."""
    info: ChartInfo = field(default_factory=ChartInfo)
    difficulties: list[Difficulty] = field(default_factory=list)
    song_file: str = ""  # path to the song file (ogg/mp3)


@dataclass
class Gimmick:
    """One gimmick (visual effect) entry."""
    beat: float         # starting beat
    duration: float     # duration in beats
    easing: str         # easing function name
    value1: str         # parameter 1 (number or "_")
    value2: str         # parameter 2 (number or "_")
    modname: str        # effect name
    proxy: str = "-1"   # track proxy


class BeatConverter:
    """Converts between beat numbers and milliseconds using timing points."""

    def __init__(self, timing_points: list[TimingPoint]):
        self.timing = sorted(timing_points, key=lambda t: t.time_ms)
        if not self.timing:
            self.timing = [TimingPoint(time_ms=0.0, bpm=120.0)]

        # Precompute cumulative beat positions at each timing point
        # self._cum_beats[i] = total beats from time 0 to timing[i].time_ms
        self._cum_beats: list[float] = []
        self._cum_time: list[float] = []
        total_beats = 0.0
        total_time = 0.0
        prev_time = 0.0
        prev_bpm = self.timing[0].bpm if self.timing else 120.0

        for i, tp in enumerate(self.timing):
            if i == 0:
                total_time = tp.time_ms
                total_beats = 0.0
            else:
                dt = tp.time_ms - prev_time
                db = dt / (60000.0 / prev_bpm)
                total_beats += db
                total_time = tp.time_ms
            self._cum_beats.append(total_beats)
            self._cum_time.append(total_time)
            prev_time = tp.time_ms
            prev_bpm = tp.bpm

    def beat_to_ms(self, beat: float) -> float:
        """Convert a beat number to milliseconds."""
        if beat <= 0:
            return 0.0

        for i in range(len(self.timing)):
            if beat <= self._cum_beats[i]:
                if i == 0:
                    return beat * (60000.0 / self.timing[0].bpm)
                prev_beat = self._cum_beats[i - 1]
                prev_time = self._cum_time[i - 1]
                bpm = self.timing[i - 1].bpm
                return prev_time + (beat - prev_beat) * (60000.0 / bpm)

        # Beyond last timing point
        last_beat = self._cum_beats[-1]
        last_time = self._cum_time[-1]
        last_bpm = self.timing[-1].bpm
        return last_time + (beat - last_beat) * (60000.0 / last_bpm)

    def ms_to_beat(self, ms: float) -> float:
        """Convert milliseconds to a beat number."""
        if ms <= 0:
            return 0.0

        for i in range(len(self.timing)):
            if ms <= self._cum_time[i]:
                if i == 0:
                    return ms / (60000.0 / self.timing[0].bpm)
                prev_beat = self._cum_beats[i - 1]
                prev_time = self._cum_time[i - 1]
                bpm = self.timing[i - 1].bpm
                return prev_beat + (ms - prev_time) / (60000.0 / bpm)

        # Beyond last timing point
        last_beat = self._cum_beats[-1]
        last_time = self._cum_time[-1]
        last_bpm = self.timing[-1].bpm
        return last_beat + (ms - last_time) / (60000.0 / last_bpm)
