"""
Central coordinate registry — all values measured at 1440x720.
Both supported devices (phone + BlueStacks) run at 1440x720.
"""

# sc() kept for backward-compat (discord_bot.py imports it)
def sc(x: int, y: int) -> tuple[int, int]:
    return (x, y)


# ── Shared ────────────────────────────────────────────────────────────────────
PROFILE_BUTTON = (52,  38)   # top-left profile icon
BACK_ARROW     = (250, 62)   # universal back arrow
CANCEL_BUTTON  = (572, 464)  # dismiss exit/leave-game dialog

# ── notice_board.py ───────────────────────────────────────────────────────────
NB_CLANS_BUTTON   = (838,  54)
NB_REFRESH_BUTTON = (738, 630)
NB_VIEW_CLAN      = (628, 570)
NB_BACK_ARROW     = (250,  62)

NB_CLAN_CHORDS: list[tuple[int, int]] = [
    (474, 214),  # Clan 1
    (970, 210),  # Clan 2
    (440, 396),  # Clan 3
    (966, 386),  # Clan 4
    (434, 612),  # Clan 5
    (976, 614),  # Clan 6
]
NB_CLAN7_10_CHORDS: list[tuple[int, int]] = [
    (466, 220),  # Clan 7
    (972, 236),  # Clan 8
    (482, 444),  # Clan 9
    (992, 448),  # Clan 10
]

# drag_menu_down: single swipe to reveal clans 1-6
NB_DRAG_MENU_DOWN_FROM = (724, 668)
NB_DRAG_MENU_DOWN_TO   = (722, 426)
# drag_to_top (reach clans 7-10): same swipe repeated 3x
NB_DRAG_TO_TOP_FROM    = (724, 668)
NB_DRAG_TO_TOP_TO      = (722, 426)
NB_DRAG_TO_TOP_REPEAT  = 3

# ── invite_players.py ─────────────────────────────────────────────────────────
INV_SOCIAL_TAB     = (1058,  62)
INV_SEARCH_PLAYERS = (1048, 138)
INV_SEARCH_INPUT   = ( 634, 208)
INV_SEARCH_BUTTON  = ( 970, 200)
INV_INVITE_BUTTON  = ( 536, 374)
INV_BACK_ARROW     = ( 250,  62)

# ── find_players.py ───────────────────────────────────────────────────────────
FP_TAP_TAG_COORD  = (748, 204)  # tap clan tag text to select
FP_TAP_COPY_COORD = (864, 210)  # tap Copy button

# ── moderation.py ─────────────────────────────────────────────────────────────
MOD_MY_CLAN_BUTTON  = (622,  58)
MOD_SORT_FILTER_BTN = (750, 564)
MOD_SHARE_ICON      = (598, 202)
MOD_COPY_TAG_BTN    = (716, 210)
MOD_BACK_ARROW      = (250,  56)
MOD_CONFIRM_KICK    = (888, 332)
MOD_CANCEL_KICK     = (586, 338)

# Bottom-of-list rows (scroll all the way down first).
# Index 0 = very last player, 1 = 2nd-to-last, … up to 5.
# Each entry: (player_tap, profile_btn, kick_btn)
MOD_BOTTOM_ROWS: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = [
    ((626, 640), (862, 440), (850, 662)),  # 0 – last
    ((640, 556), (860, 446), (856, 662)),  # 1
    ((616, 476), (846, 364), (864, 594)),  # 2
    ((616, 384), (864, 280), (854, 510)),  # 3
    ((632, 298), (864, 190), (846, 424)),  # 4
    ((634, 218), (864, 102), (856, 332)),  # 5
]

# Scroll swipe Y positions used in _scroll_to_bottom (moderation)
MOD_SCROLL_Y_START  = 668
MOD_SCROLL_Y_END    = 200
MOD_SCROLL_Y_START2 = 668
