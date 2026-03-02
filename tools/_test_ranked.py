import sys, asyncio
sys.path.insert(0, 'src')
sys.path.insert(0, 'tools')
from dotenv import load_dotenv; load_dotenv()
from moderation import _fetch_ranked_members

ranked = asyncio.run(_fetch_ranked_members())
for i, m in enumerate(ranked, 1):
    offline = f"{m.days_offline:.1f}d" if m.days_offline is not None else "???"
    excl = " [EXCL]" if m.excluded else ""
    print(f"  {i:>2}. {m.name:20s} {m.tag:14s}  don={m.donations:>5}  offline={offline}{excl}")
