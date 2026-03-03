"""
Central coordinate registry — all tap/swipe positions defined in 1920×1080 baseline.

sc(x, y) returns coordinates scaled to the active resolution, reading
settings.emulator_width / settings.emulator_height at call time.

1440×720 mapping
----------------
CoC is always 16:9.  On a 1440×720 (2:1) screen the game letterboxes to
1280×720 and is centred, leaving 80 px bars on the left and right sides:

    new_x = round(base_x × 1280/1920) + 80
    new_y = round(base_y × 720/1080)

If this does not match what you see, run /showinputs in Discord to watch
where taps land and adjust the formula / individual values as needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from cocbot.config import settings


def sc(x: int, y: int) -> tuple[int, int]:
    """Scale a 1920×1080 baseline coordinate to the active resolution."""
    w, h = settings.emulator_width, settings.emulator_height
    if w == 1920 and h == 1080:
        return (x, y)
    if w == 1440 and h == 720:
        # Game renders 1280×720 (16:9) centred; 80 px letterbox bars each side
        return (round(x * 1280 / 1920) + 80, round(y * 720 / 1080))
    # Generic linear scale for any other resolution
    return (round(x * w / 1920), round(y * h / 1080))


# ── Shared ────────────────────────────────────────────────────────────────────
PROFILE_BUTTON = sc(76,   62)
BACK_ARROW     = sc(266,  80)
CANCEL_BUTTON  = sc(754, 698)   # main-menu confirmation Cancel

# ── notice_board.py ───────────────────────────────────────────────────────────
NB_CLANS_BUTTON   = sc(1136,  90)
NB_REFRESH_BUTTON = sc(980,  940)
NB_VIEW_CLAN      = sc(800,  868)
NB_BACK_ARROW     = sc(268,   78)

NB_CLAN_CHORDS: list[tuple[int, int]] = [
    sc(554,  310),   # Clan 1
    sc(1322, 306),   # Clan 2
    sc(584,  572),   # Clan 3
    sc(1328, 560),   # Clan 4
    sc(578,  906),   # Clan 5
    sc(1318, 888),   # Clan 6
]
NB_CLAN7_10_CHORDS: list[tuple[int, int]] = [
    sc(606,  356),   # Clan 7
    sc(1316, 342),   # Clan 8
    sc(594,  686),   # Clan 9
    sc(1336, 670),   # Clan 10
]

# Scroll bar constants
NB_SCROLL_X      = sc(960,    0)[0]
NB_SCROLL_FROM_Y = sc(0,   1600)[1]
NB_SCROLL_TO_Y   = sc(0,    400)[1]

# Drag endpoints
NB_DRAG_MENU_DOWN_FROM = sc(960, 1016)
NB_DRAG_MENU_DOWN_TO   = sc(962,  724)
NB_DRAG_TO_TOP_FROM    = sc(960, 1016)
NB_DRAG_TO_TOP_TO      = sc(960,    0)

# ── invite_players.py ─────────────────────────────────────────────────────────
INV_SOCIAL_TAB     = sc(1464,  82)
INV_SEARCH_PLAYERS = sc(1478, 200)
INV_SEARCH_INPUT   = sc(612,  306)
INV_SEARCH_BUTTON  = sc(1318, 302)
INV_INVITE_BUTTON  = sc(696,  564)
INV_BACK_ARROW     = sc(266,   78)

# ── find_players.py ───────────────────────────────────────────────────────────
FP_TAP_TAG_COORD  = sc(998,  306)
FP_TAP_COPY_COORD = sc(1176, 314)

# ── moderation.py ─────────────────────────────────────────────────────────────
MOD_MY_CLAN_BUTTON  = sc(814,  92)
MOD_SORT_FILTER_BTN = sc(1000, 842)
MOD_SHARE_ICON      = sc(766,  294)
MOD_COPY_TAG_BTN    = sc(938,  310)
MOD_BACK_ARROW      = sc(266,   80)
MOD_CONFIRM_KICK    = sc(1188, 508)
MOD_CANCEL_KICK     = sc(734,  506)

# Bottom-of-list rows (scroll all the way down first).
# Index 0 = last player, 1 = 2nd-to-last, … up to 5.
# Each entry: (player_tap, profile_btn, kick_btn)
MOD_BOTTOM_ROWS: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = [
    (sc(968, 962),  sc(1172, 666),  sc(1174, 994)),   # 0 – last
    (sc(912, 832),  sc(1164, 648),  sc(1166, 992)),   # 1 – 2nd
    (sc(928, 710),  sc(1170, 550),  sc(1166, 874)),   # 2 – 3rd
    (sc(890, 584),  sc(1170, 416),  sc(1170, 758)),   # 3 – 4th
    (sc(906, 454),  sc(1172, 292),  sc(1172, 636)),   # 4 – 5th
    (sc(870, 330),  sc(1182, 158),  sc(1156, 500)),   # 5 – 6th
]

# Scroll swipe Y positions used in _scroll_to_bottom
MOD_SCROLL_Y_START  = sc(0, 800)[1]
MOD_SCROLL_Y_END    = sc(0, 200)[1]
MOD_SCROLL_Y_START2 = sc(0, 900)[1]
