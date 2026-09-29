# Window -- enlarged for comfortable tactical command center layout
# Now supports fullscreen and dynamic resizing
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
DEFAULT_WINDOW_WIDTH = 1440
DEFAULT_WINDOW_HEIGHT = 900
FPS = 60

# Background & Chrome (Modern Deep Obsidian / Slate-950)
BG_COLOR = (12, 16, 24)
BG_DARK = (8, 11, 17)
PANEL_BG = (19, 25, 38)
PANEL_BG_RAISED = (27, 35, 52)
PANEL_BG_LIGHT = (36, 46, 68)
PANEL_BORDER = (42, 53, 76)
PANEL_BORDER_BRIGHT = (70, 88, 124)

# Vibrant Modern Accents
ACCENT = (14, 185, 230)            # Vivid Cyber Cyan / Fact-checker
ACCENT_DIM = (12, 100, 130)
ACCENT_BRIGHT = (56, 222, 255)       # Hover Cyan
ACCENT_GLOW = (20, 140, 180)

# Semantic Colors
COLOR_BELIEF = (244, 63, 94)        # Neon Crimson / Rumor Viral Spread
COLOR_BELIEF_DIM = (140, 30, 50)
COLOR_BELIEF_BRIGHT = (255, 90, 120)

COLOR_CURE = (16, 185, 129)         # Emerald Green / Fact-checking correction
COLOR_CURE_DIM = (10, 100, 70)
COLOR_CURE_BRIGHT = (52, 211, 153)

COLOR_EXPOSED = (168, 85, 247)      # Amethyst Purple / Latent SEIR
COLOR_EXPOSED_DIM = (90, 45, 140)

COLOR_WARNING = (245, 158, 11)      # Amber / Moderate Alert
COLOR_DANGER = (239, 68, 68)        # Ruby Red / Critical Threat

# Text Colors
TEXT_PRIMARY = (248, 250, 252)     # Crisp white
TEXT_SECONDARY = (156, 172, 196)   # Cool silver slate
TEXT_MUTED = (100, 116, 140)       # Dim footnote
TEXT_HIGHLIGHT = (255, 255, 255)
TEXT_WARNING = COLOR_WARNING
TEXT_DANGER = COLOR_BELIEF

# Region Heatmap Colors (Susceptible Blue -> Contagion Amber -> Viral Crimson)
REGION_UNINVOLVED = (30, 38, 54)
REGION_UNINVOLVED_BORDER = (45, 56, 78)

REGION_LOW = (37, 99, 235)         # Vibrant Susceptible Blue
REGION_MID = (217, 119, 6)         # Amber Spread
REGION_HIGH = (225, 29, 72)        # Deep Viral Rose

REGION_SKEPTICAL_OVERLAY = COLOR_CURE
REGION_EXPOSED_OVERLAY = COLOR_EXPOSED
REGION_SELECTED_OUTLINE = (255, 255, 255)
REGION_HOVER_OUTLINE = (125, 211, 252)      # Sky blue glow

EDGE_COLOR = (42, 53, 76)
EDGE_HIGHLIGHT = (56, 222, 255)

# Race Bar (Belief Contagion vs Fact-Checking Defence)
RACE_BAR_BELIEF = COLOR_BELIEF
RACE_BAR_COUNTER = ACCENT
RACE_BAR_TRACK = (22, 28, 42)

# Telegraphed Strike Alert
STRIKE_ALERT = (249, 115, 22)       # Alert Tangerine
STRIKE_ALERT_DIM = (80, 36, 12)
STRIKE_ALERT_BG = (40, 20, 16)

# Action Buttons
ADVANCE_BUTTON_BG = (14, 116, 144)
ADVANCE_BUTTON_BG_HOVER = (6, 182, 212)
ADVANCE_BUTTON_TEXT = (255, 255, 255)

# Typography
FONT_NAME = "Segoe UI, Arial, sans-serif"
FONT_SIZE_TITLE = 32
FONT_SIZE_HEADER = 20
FONT_SIZE_BODY = 15
FONT_SIZE_SMALL = 12

NODE_RADIUS_MIN = 16
NODE_RADIUS_MAX = 38
