# Window -- enlarged from the original 1100x700 so the map has real room
# to breathe and the UI doesn't read as mostly empty space.
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
FPS = 60

# Background / chrome
BG_COLOR = (16, 18, 23)            # near-black, slightly blue
PANEL_BG = (26, 30, 38)
PANEL_BG_RAISED = (32, 37, 46)        # slightly lighter panel, used for the Advance button / detail panel
PANEL_BORDER = (52, 58, 70)
ACCENT = (64, 196, 180)             # teal accent for buttons/highlights -- also "countermeasure" color
ACCENT_DIM = (40, 120, 110)
ACCENT_BRIGHT = (90, 226, 208)         # hover/active state for the teal accent

# Text
TEXT_PRIMARY = (235, 238, 240)
TEXT_SECONDARY = (150, 158, 168)
TEXT_WARNING = (235, 150, 90)
TEXT_DANGER = (230, 90, 90)             # also "belief" color, paired with ACCENT as its rival

# Region heat-gradient (low belief -> high belief)
REGION_LOW = (70, 130, 200)         # cool blue  = mostly susceptible
REGION_MID = (220, 180, 70)         # amber      = partially believing
REGION_HIGH = (220, 70, 70)         # red        = heavily believing
REGION_SKEPTICAL_OVERLAY = (110, 200, 140)  # green ring = corrected/skeptical present
REGION_EXPOSED_OVERLAY = (160, 140, 220)      # purple ring = exposed-but-not-yet-believing (SEIR only)
REGION_SELECTED_OUTLINE = (255, 255, 255)       # bright white outline = currently selected/inspected node
REGION_HOVER_OUTLINE = (200, 205, 212)            # dim white outline = mouse is hovering, not yet clicked

EDGE_COLOR = (60, 66, 78)
EDGE_HIGHLIGHT = (90, 160, 150)

# Race bar (belief % vs countermeasure % -- the single most important
# at-a-glance widget, modeled after Plague Inc's infection/cure race)
RACE_BAR_BELIEF = TEXT_DANGER
RACE_BAR_COUNTER = ACCENT
RACE_BAR_TRACK = (40, 45, 55)

# Telegraphed strike alert -- deliberately a different, more urgent color
# than the AI-focus highlight (TEXT_WARNING) so a SCHEDULED strike reads as
# more serious than the AI merely "watching" a region.
STRIKE_ALERT = (235, 100, 60)
STRIKE_ALERT_DIM = (90, 50, 40)

# Advance / pause control
ADVANCE_BUTTON_BG = ACCENT_DIM
ADVANCE_BUTTON_BG_HOVER = ACCENT
ADVANCE_BUTTON_TEXT = TEXT_PRIMARY

# Fonts (loaded once in main.py, names referenced here for consistency)
FONT_NAME = None   # None = Pygame default font; swap for a .ttf path for a custom look
FONT_SIZE_TITLE = 30
FONT_SIZE_HEADER = 20
FONT_SIZE_BODY = 16
FONT_SIZE_SMALL = 13

NODE_RADIUS_MIN = 16
NODE_RADIUS_MAX = 38