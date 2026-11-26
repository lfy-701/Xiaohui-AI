import httpx
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})

a = c.get("/api/agents").json()["agents"][0]
print("旧人设:", a["persona"][:40], "...")

NEW = ("你叫小小，是主人身边最亲近的伙伴。说话温柔自然，像熟人聊天一样，"
       "不客套、不说「作为一个AI」这类话。回答简短，两三句说完，"
       "偶尔关心一下主人今天过得怎么样。")

r = c.put("/api/agents/" + a["id"], json={"persona": NEW}).json()
print("新人设:", r["persona"])

h = c.get("/").text
print("预设标签数量:", h.count('class="chip"'))
print("包含毒舌损友:", "毒舌损友" in h)
