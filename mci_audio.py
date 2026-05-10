"""Audio player using miniaudio — supports OGG, MP3, FLAC, WAV.

Uses miniaudio's streaming playback with time-based position tracking.
"""

import time
import miniaudio


class MCIAudio:
    """Audio player (keeps original class name for compatibility).

    Uses miniaudio internally for broad format support including OGG Vorbis.
    """

    def __init__(self):
        self._path: str = ""
        self._info: miniaudio.SoundFileInfo | None = None
        self._device: miniaudio.PlaybackDevice | None = None
        self._sample_rate: int = 0
        self._nchannels: int = 0
        self._start_ms: float = 0.0      # seek position when play() called
        self._start_time: float = 0.0     # perf_counter when play() called
        self._paused_pos_ms: float = 0.0  # position when paused
        self._playing: bool = False

    def load(self, filepath: str) -> bool:
        """Load an audio file. Returns True on success."""
        self.unload()
        try:
            self._info = miniaudio.get_file_info(filepath)
            self._path = filepath
            self._sample_rate = self._info.sample_rate
            self._nchannels = self._info.nchannels
            return self._info.duration > 0
        except (miniaudio.DecodeError, FileNotFoundError, OSError):
            return False

    def unload(self):
        """Stop playback and release resources."""
        self.stop()
        self._path = ""
        self._info = None
        self._paused_pos_ms = 0.0

    def play(self, start_ms: float = 0.0):
        """Start or resume playback from a position in milliseconds."""
        self.stop()
        if not self._info or not self._path:
            return

        seek_frame = max(0, int(start_ms / 1000.0 * self._sample_rate))
        self._start_ms = seek_frame / self._sample_rate * 1000.0

        try:
            stream_gen = miniaudio.stream_file(
                self._path, seek_frame=seek_frame
            )
            self._device = miniaudio.PlaybackDevice(
                nchannels=self._nchannels,
                sample_rate=self._sample_rate,
            )
            self._device.start(stream_gen)
            self._start_time = time.perf_counter()
            self._playing = True
        except Exception:
            self._playing = False

    def pause(self):
        """Pause playback, remembering position for resume."""
        if not self._playing:
            return
        # Save current position
        self._paused_pos_ms = self.get_position_ms()
        if self._device:
            try:
                self._device.stop()
            except Exception:
                pass
        self._device = None
        self._playing = False

    def stop(self):
        """Stop playback completely."""
        if self._device:
            try:
                self._device.stop()
            except Exception:
                pass
        self._device = None
        self._playing = False

    def seek(self, pos_ms: float):
        """Set playback position (in milliseconds). Restart if playing."""
        self._paused_pos_ms = pos_ms
        if self._playing:
            self.play(pos_ms)

    def get_position_ms(self) -> float:
        """Current playback position in milliseconds."""
        if self._playing:
            elapsed = (time.perf_counter() - self._start_time) * 1000.0
            return self._start_ms + elapsed
        return self._paused_pos_ms

    def is_busy(self) -> bool:
        """Check if audio is currently playing."""
        return self._playing

    @property
    def length_ms(self) -> float:
        """Total duration in milliseconds."""
        if self._info:
            return self._info.duration * 1000.0
        return 0.0

    @property
    def playing(self) -> bool:
        return self._playing
