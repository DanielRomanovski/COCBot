"""
COCBot — Clash of Clans automation framework.

Architecture
============
src/cocbot/
  config.py          — Pydantic settings loaded from .env
  adb/
    device.py        — ADB connection, screenshot, tap/swipe primitives
    input.py         — Higher-level input helpers (human-like delays, drag, etc.)
  vision/
    screen.py        — Screenshot → PIL/numpy array helpers
    matcher.py       — OpenCV template matching to find UI elements
    ocr.py           — pytesseract wrappers to read numbers/text on screen
  api/
    client.py        — coc.py async wrapper (player, clan, war data)
  game/
    state.py         — State machine: which screen is the game currently on?
    navigator.py     — Navigation helpers (go to village, open attack menu, etc.)
    resources.py     — Dataclasses for game resources (gold, elixir, etc.)
  tasks/
    farm.py          — Farming loop: find match → assess → attack → collect
    donate.py        — Auto-donate troops to clan members
    war.py           — Clan war helpers (read war state, flag targets)
  utils/
    delays.py        — Human-like random delay utilities
    logging.py       — Loguru logger setup
  main.py            — Entry point, CLI, task scheduler
"""
