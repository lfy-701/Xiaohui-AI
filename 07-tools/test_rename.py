import httpx

c = httpx.Client(base_url="http://127.0.0.1", timeout=10)
c.post("/login", data={"password": "xiaohui2026"})

a = c.get("/api/agents").json()["agents"][0]
print("当前名称 :", a["name"])
print("改名前 id:", a["id"])

r = c.put(f"/api/agents/{a['id']}", json={"name": "自定义测试"}).json()
print("改名返回 :", r["name"])

lst = c.get("/api/agents").json()["agents"]
print("列表里是 :", [x["name"] for x in lst])

c.put(f"/api/agents/{a['id']}", json={"name": "小小"})
print("已改回   :", c.get("/api/agents").json()["agents"][0]["name"])
