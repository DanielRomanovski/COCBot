"""
Central coordinate registry.

Every constant is defined as _xy(base_1920x1080, override_1440x720).
Add more resolution tuples here and extend _xy() as needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from cocbot.config import settings


def _xy(
    base: tuple[int, int],
    r1440: tuple[int, int],
) -> tuple[int, int]:
    """Return the coordinate pair for the active resolution."""
    if settings.emulator_width == 1440 and settings.emulator_height == 720:
        return r1440
    return base


# sc() kept for backward-compat (discord_bot.py imports it)
def sc(x: int, y: int) -> tuple[int, int]:
    return (x, y)


# ── Shared ────────────────────────────────────────────────────────────────────
PROFILE_BUTTON = _xy((76,   62),  (52,  38))
BACK_ARROW     = _xy((266,  80),  (260, 56))
CANCEL_BUTTON  = _xy((754, 698),  (572, 464))

# ── notice_board.py ───────────────────────────────────────────────────────────
NB_CLANS_BUTTON   = _xy((1136,  90),  (838,  54))
NB_REFRESH_BUTTON = _xy((980,  940),  (738, 630))
NB_VIEW_CLAN      = _xy((800,  868),  (628, 570))
NB_BACK_ARROW     = _xy((268,   78),  (250,  62))

NB_CLAN_CHORDS: list[tuple[int, int]] = [
    _xy((554,  310),  (474, 214)),   # Clan 1
    _xy((1322, 306),  (970, 210)),   # Clan 2
    _xy((584,  572),  (440, 396)),   # Clan 3
    _xy((1328, 560),  (966, 386)),   # Clan 4
    _xy((578,  906),  (434, 612)),   # Clan 5
    _xy((1318, 888),  (976, 614)),   # Clan 6
]
NB_CLAN7_10_CHORDS: list[tuple[int, int]] = [
    _xy((606,  356),  (466, 220)),   # Clan 7
    _xy((1316, 342),  (972, 236)),   # Clan 8
    _xy((594,  686),  (482, 444)),   # Clan 9
    _xy((1336, 670),  (992, 448)),   # Clan 10
]

# Drag endpoints
NB_DRAG_MENU_DOWN_FROM = _xy((960, 1016),  (724, 668))
NB_DRAG_MENU_DOWN_TO   = _xy((962,  724),  (722, 426))
NB_DRAG_TO_TOP_FROM    = _xy((960, 1016),  (724, 668))
NB_DRAG_TO_TOP_TO      = _xy((960,    0),  (722, 426))
# At 1440x720 drag_to_top needs multiple passes — checked in notice_board.py
NB_DRAG_TO_TOP_REPEAT  = 1 if (settings.emulator_width == 1920) else 3

# fast_scroll_to_bottom swipe positions
NB_SCROLL_X      = _xy((960,    0), (723,   0))[0]
NB_SCROLL_FROM_Y = _xy((0,   1600), (0,   668))[1]
NB_SCROLL_TO_Y   = _xy((0,    400), (0,   426))[1]

# ── invite_players.py ─────────────────────────────────────────────────────────
INV_SOCIAL_TAB     = _xy((1464,  82),  (1058,  62))
INV_SEARCH_PLAYERS = _xy((1478, 200),  (1048, 138))
INV_SEARCH_INPUT   = _xy((612,  306),  (634,  208))
INV_SEARCH_BUTTON  = _xy((1318, 302),  (970,  200))
INV_INVITE_BUTTON  = _xy((696,  564),  (536,  374))
INV_BACK_ARROW     = _xy((266,   78),  (260,   56))

# ── find_players.py ───────────────────────────────────────────────────────────
FP_TAP_TAG_COORD  = _xy((998,  306),  (748, 204))
FP_TAP_COPY_COORD = _xy((1176, 314),  (864, 210))

# ── moderation.py ─────────────────────────────────────────────────────────────
MOD_MY_CLAN_BUTTON  = _xy((814,  92),  (622,  58))
MOD_SORT_FILTER_BTN = _xy((1000, 842), (750, 564))
MOD_SHARE_ICON      = _xy((766,  294), (598, 202))
MOD_COPY_TAG_BTN    = _xy((938,  310), (716, 210))
MOD_BACK_ARROW      = _xy((266,   80), (260,  56))
MOD_CONFIRM_KICK    = _xy((1188, 508), (888, 332))
MOD_CANCEL_KICK     = _xy((734,  506), (586, 338))

# Bottom-of-list rows (scroll all the way down first).
# Index 0 = very last player, 1 = 2nd-to-last, … up to 5.
# Each entry: (player_tap, profile_btn, kick_btn)
MOD_BOTTOM_ROWS: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = [
    (_xy((968, 962),  (626, 640)),  _xy((1172, 666), (862, 440)),  _xy((1174, 994), (850, 662))),
    (_xy((912, 832),  (640, 556)),  _xy((1164, 648), (860, 446)),  _xy((1166, 992), (856, 662))),
    (_xy((928, 710),  (616, 476)),  _xy((1170, 550), (846, 364)),  _xy((1166, 874), (864, 594))),
    (_xy((890, 584),  (616, 384)),  _xy((1170, 416), (864, 280)),  _xy((1170, 758), (854, 510))),
    (_xy((906, 454),  (632, 298)),  _xy((1172, 292), (864, 190)),  _xy((1172, 636), (846, 424))),
    (_xy((870, 330),  (634, 218)),  _xy((1182, 158), (864, 102)),  _xy((1156, 500), (856, 332))),
]

# Scroll swipe Y positions used in _scroll_to_bottom (moderation)
MOD_SCROLL_Y_START  = _xy((0, 800), (0, 668))[1]
MOD_SCROLL_Y_END    = _xy((0, 200), (0, 200))[1]
MOD_SCROLL_Y_START2 = _xy((0, 900), (0, 668))[1]
