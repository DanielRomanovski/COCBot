import sys, asyncio, json; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from cocbot.api.client import CoCAPIClient
from cocbot.config import settings

async def test():
    async with CoCAPIClient(settings.coc_api_token, settings.player_tag, '#2QQCCYQP') as c:
        p = await c.client.get_player('#22QJLC89L')
        raw = p._raw_data
        # scalar fields
        print("=== SCALAR FIELDS ===")
        for k, v in raw.items():
            if not isinstance(v, (list, dict)):
                print(f"  {k:40s} = {v}")
        # heroes
        print("\n=== HEROES ===")
        for h in raw.get('heroes', []):
            print(f"  {h.get('name'):30s} level={h.get('level'):>3}  maxLevel={h.get('maxLevel')}")
        # summary counts
        print(f"\n  troop count: {len(raw.get('troops', []))}")
        print(f"  spell count: {len(raw.get('spells', []))}")
        print(f"  heroEquipment count: {len(raw.get('heroEquipment', []))}")
        print(f"  achievement count: {len(raw.get('achievements', []))}")
        # show achievement names + values
        print("\n=== ALL ACHIEVEMENTS ===")
        for a in sorted(raw.get('achievements', []), key=lambda x: x.get('name','')):
            print(f"  {a.get('name'):50s} value={a.get('value'):>10}")

asyncio.run(test())
