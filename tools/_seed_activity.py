"""Re-seed last_seen data from known offline info. Preserves all other fields."""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc)

def ts(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()

SEEDS = {
    # Over a month (35 days)
    "#QJ8YYPG99":  ts(35),
    "#2RVJPQRRP":  ts(35),
    "#8R9U82880":  ts(35),
    "#2VGQ0R0L":   ts(35),
    "#QVQJ8J20J":  ts(35),
    "#L0LVGP8RU":  ts(35),
    "#GYPQVYY9G":  ts(35),
    "#YRVRJCVP":   ts(35),
    "#Y89CR2990":  ts(35),
    "#2U2U920R":   ts(35),
    # 3 weeks ago (21 days)
    "#Y0J2J9Y8Y":  ts(21),
    "#Q9J82VQJL":  ts(21),
    # 2 weeks ago (14 days)
    "#8VYC0YPPR":  ts(14),
    "#Q2LJLRUYG":  ts(14),
    # A week ago (7 days)
    "#QQL0CGY22":  ts(7),
    "#QJQ88CC8G":  ts(7),
    "#9Y9YLJ2YV":  ts(7),
    # 4 days ago
    "#R0RC8PJ0":   ts(4),
    # 3 days ago
    "#2LURU0YCQ":  ts(3),
    # 2 days ago
    "#88C2P8C9":   ts(2),
    # A day ago
    "#LL999PY0U":  ts(1),
    "#22020LQP0":  ts(1),
}

f = Path(__file__).parent / "member_activity.json"
data = json.loads(f.read_text())

seeded = 0
for tag, entry in data.items():
    if tag in SEEDS:
        entry["last_seen"] = SEEDS[tag]
        seeded += 1
    elif entry.get("last_seen") is None:
        # "played recently" — set to today so they're excluded from kicks
        entry["last_seen"] = ts(0.5)

f.write_text(json.dumps(data, indent=2))
print(f"Seeded {seeded} known entries, rest set to 'recently active'")
