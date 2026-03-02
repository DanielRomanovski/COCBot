"""Preview the leaderboard embed layout in the terminal (no Discord needed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from moderation import _fetch_ranked_members, PLAYERS_TO_KICK

# Inline copy of _table_field for terminal preview
NAME_W = 18
def _table_field(members, kick_tags):
    rows = []
    for rank, m in members:
        name    = m.name[:NAME_W].ljust(NAME_W)
        offline = f"{m.days_offline:.1f}d".rjust(6) if m.days_offline is not None else "   ???"
        don     = str(m.donations).rjust(5)
        note    = " <KICK" if m.tag in kick_tags else ("  [protected]" if m.excluded else "")
        rows.append(f"{rank:>2}  {name}  {offline}  {don}{note}")
    header  = f"{'#':>2}  {'Name':<{NAME_W}}  {'Offln':>6}  {'Don':>5}"
    divider = "─" * len(header)
    return "\n".join([header, divider] + rows)

async def main():
    ranked = await _fetch_ranked_members()
    eligible   = [m for m in ranked if not m.excluded]
    kick_tags  = {m.tag for m in eligible[:PLAYERS_TO_KICK]}
    ranked_num = list(enumerate(ranked, 1))

    sections = {
        "🔪 Kick Targets":       [(r, m) for r, m in ranked_num if m.tag in kick_tags],
        "💀 Over a Month (>30d)": [(r, m) for r, m in ranked_num if not m.excluded and m.days_offline and m.days_offline > 30 and m.tag not in kick_tags],
        "🔴 14–30 Days":         [(r, m) for r, m in ranked_num if not m.excluded and m.days_offline and 14 < m.days_offline <= 30],
        "🟠 7–14 Days":          [(r, m) for r, m in ranked_num if not m.excluded and m.days_offline and 7 < m.days_offline <= 14],
        "❓ No Baseline":        [(r, m) for r, m in ranked_num if not m.excluded and m.days_offline is None],
        "🟢 Active/Protected":   [(r, m) for r, m in ranked_num if m.excluded or (m.days_offline is not None and m.days_offline <= 7)],
    }
    for title, members in sections.items():
        if not members:
            continue
        print(f"\n{'═'*50}")
        print(f"  {title}  ({len(members)})")
        print('═'*50)
        print(_table_field(members, kick_tags))

asyncio.run(main())
