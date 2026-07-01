# Window
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700
FPS = 60

# Background / chrome
BG_COLOR = (18, 21, 26)            # near-black, slightly blue
PANEL_BG = (28, 32, 40)
PANEL_BORDER = (52, 58, 70)
ACCENT = (64, 196, 180)             # teal accent for buttons/highlights
ACCENT_DIM = (40, 120, 110)

# Text
TEXT_PRIMARY = (235, 238, 240)
TEXT_SECONDARY = (150, 158, 168)
TEXT_WARNING = (235, 150, 90)

# Region heat-gradient (low belief -> high belief)
REGION_LOW = (70, 130, 200)         # cool blue  = mostly susceptible
REGION_MID = (220, 180, 70)         # amber      = partially believing
REGION_HIGH = (220, 70, 70)         # red        = heavily believing
REGION_SKEPTICAL_OVERLAY = (110, 200, 140)  # green ring = corrected/skeptical present
REGION_EXPOSED_OVERLAY = (160, 140, 220)      # purple ring = exposed-but-not-yet-believing (SEIR only)

EDGE_COLOR = (60, 66, 78)
EDGE_HIGHLIGHT = (90, 160, 150)

# Fonts (loaded once in main.py, names referenced here for consistency)
FONT_NAME = None   # None = Pygame default font; swap for a .ttf path for a custom look
FONT_SIZE_TITLE = 28
FONT_SIZE_HEADER = 20
FONT_SIZE_BODY = 16
FONT_SIZE_SMALL = 13

NODE_RADIUS_MIN = 18
NODE_RADIUS_MAX = 34