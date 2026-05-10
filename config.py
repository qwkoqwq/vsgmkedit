"""Constants for the gimmick editor."""

EFFECTS = [
    "scrollspeed", "noterot", "velocity", "driven", "beat", "wave",
    "yoffset", "notealp",
    "scrollind0", "scrollind1", "scrollind2", "scrollind3",
    "scrollind4", "scrollind5", "scrollind6", "scrollind7",
    "drawdist", "pburstleft", "pburstright",
    "particlexpower", "particleypower", "uialpha",
    "fx_contrast", "fx_glow", "fx_particleglow", "pburstspeed",
    "freeze", "fx_chroma_distort", "fx_film",
    "boost_distance", "boost_time", "hom", "enable_hue",
]

EASINGS = [
    "linear",
    "easeInSine", "easeOutSine", "easeInOutSine",
    "easeInQuad", "easeOutQuad", "easeInOutQuad",
    "easeInCubic", "easeOutCubic", "easeInOutCubic",
    "easeInQuart", "easeOutQuart", "easeInOutQuart",
    "easeInQuint", "easeOutQuint", "easeInOutQuint",
    "easeInExpo", "easeOutExpo", "easeInOutExpo",
    "easeInCirc", "easeOutCirc", "easeInOutCirc",
    "easeInBack", "easeOutBack", "easeInOutBack",
    "easeInElastic", "easeOutElastic", "easeInOutElastic",
    "easeInBounce", "easeOutBounce", "easeInOutBounce",
]

# Note colors
COLOR_NOTE_SINGLE = "#7EC8E3"    # light blue: 1-lane normal note
COLOR_NOTE_WIDE_01 = "#1A3A6B"   # dark blue: lanes 0-1 wide note
COLOR_NOTE_WIDE_23 = "#8B1A1A"   # dark red: lanes 2-3 wide note
COLOR_NOTE_MINE = "#1A1A1A"      # black: mine note

# UI colors
COLOR_BG = "#1E1E2E"
COLOR_LANE_BG = "#252540"
COLOR_LANE_LINE = "#3A3A55"
COLOR_JUDGMENT_LINE = "#FF4444"
COLOR_GIMMICK_BAR = "#4EC9B0"
COLOR_GIMMICK_SELECTED = "#FFD700"
COLOR_GIMMICK_NORMAL = "#3D8B6E"   # green for gimmick rectangles
COLOR_GIMMICK_GRID = "#2A2A40"     # grid line color
COLOR_BEAT_MAJOR = "#4A4A65"       # whole beat grid line
COLOR_BEAT_MINOR = "#2E2E45"       # sub-beat grid line
COLOR_BEAT_LABEL = "#6A6A8A"       # beat number label
COLOR_TEXT = "#CDD6F4"
COLOR_PANEL_BG = "#181825"

# Default view settings
DEFAULT_MS_PER_PIXEL = 2.0       # initial zoom: 2ms per pixel
MIN_MS_PER_PIXEL = 0.2
MAX_MS_PER_PIXEL = 20.0
ZOOM_FACTOR = 1.2                # zoom multiplier per Ctrl+wheel tick

# Beat grid subdivision — how many lines per measure in 4/4
# 4 = 1 line/beat, 8 = 2 lines/beat, 16 = 4 lines/beat, etc.
SUBDIVISION_OPTIONS = [4, 6, 8, 12, 16, 24, 32, 48, 64]
DEFAULT_SUBDIVISION = 4

# Note dimensions
NOTE_HEIGHT_RATIO = 8.0          # width:height ratio = 8:1
NOTE_CANVAS_WIDTH = 480          # fixed width for note display area

# Gimmick grid
GIMMICK_COLUMNS = 10              # number of columns in gimmick editing grid
