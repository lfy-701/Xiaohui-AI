import asyncio
import collections
import sys

import edge_tts

sys.stdout.reconfigure(encoding="utf-8")
vs = asyncio.run(edge_tts.list_voices())
locs = collections.Counter(v["Locale"] for v in vs)
print("总音色:", len(vs), "| 语种数:", len(locs))

print("\n--- 中文相关 ---")
for v in sorted(vs, key=lambda x: x["Locale"]):
    if v["Locale"].startswith("zh"):
        print("  {:<34} {:<7} {}".format(v["ShortName"], v["Gender"], v["Locale"]))

print("\n--- 语种分布（前 24）---")
for loc, n in locs.most_common(24):
    print("  {:<8} {}".format(loc, n))
