import sys, zstandard, json, re

p = sys.argv[1]
out = sys.argv[2]
d = zstandard.ZstdDecompressor().stream_reader(open(p, 'rb')).read().decode('utf-8', 'replace')

rows = []
for i, line in enumerate(d.splitlines()):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    blob = json.dumps(obj, ensure_ascii=False)
    if any(k in blob for k in ["console/action", "关键词兜底", "控制接口", "device/push"]):
        rows.append((i, obj))

with open(out, 'w', encoding='utf-8') as f:
    for i, obj in rows:
        f.write(f"\n===== line {i} =====\n")
        f.write(json.dumps(obj, ensure_ascii=False)[:6000])
        f.write("\n")
print("rows", len(rows))
