# 小慧音乐 MCP 服务

给小慧 / model-service 用的音乐查询与试听服务。

## 是什么

一个标准 **MCP Server**（Streamable HTTP），同时带一层 REST 兼容接口。

| 项目 | 值 |
|---|---|
| 端口 | `8102` |
| MCP 端点 | `http://<ip>:8102/mcp` |
| REST 端点 | `http://<ip>:8102/rest/*` |
| 数据源 | Apple iTunes Search API（免费、无需 Key） |
| 传输 | streamable-http |

## MCP 工具（全部只读）

| 工具 | 说明 | 参数 |
|---|---|---|
| `search_music` | 按歌名/歌手/关键词搜索 | `query`, `limit`(1-20), `country`(cn/us) |
| `get_music_preview` | 按 ID 取详情与试听链接 | `track_id` |
| `recommend_music` | 按心情/场景推荐 | `mood`, `limit` |
| `list_moods` | 列出推荐关键词 | — |

四个工具都带 `annotations.readOnlyHint=true`，因此 model-service 会自动提供给模型调用。

返回结构示例：

```json
{
  "ok": true,
  "count": 3,
  "songs": [
    {
      "track_id": 1441633014,
      "title": "屋顶",
      "artist": "Landy Wen & Jay Chou",
      "album": "爱回温 新歌+精选",
      "duration_seconds": 319,
      "genre": "国语流行",
      "preview_url": "https://audio-ssl.itunes.apple.com/.../xxx.m4a",
      "cover_url": "https://is1-ssl.mzstatic.com/.../300x300b.jpg",
      "store_url": "https://music.apple.com/..."
    }
  ]
}
```

`preview_url` 是 30 秒试听直链，浏览器、播放器都能直接播。

## 启动

```powershell
cd services\music-mcp
.\.venv\Scripts\python.exe server.py
```

环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MUSIC_HOST` | `0.0.0.0` | 监听地址 |
| `MUSIC_PORT` | `8102` | 端口 |
| `MUSIC_TRANSPORT` | `streamable-http` | 也可用 `sse` |

自测：

```powershell
curl.exe "http://127.0.0.1:8102/rest/health"
curl.exe "http://127.0.0.1:8102/rest/search?q=周杰伦&limit=3"
```

## 注册到 model-service

在成员 A 的 `config/mcp_servers.json` 的 `servers` 里追加：

```json
{
  "id": "music-local",
  "name": "小慧音乐",
  "transport": "streamable_http",
  "url": "http://<你的服务地址>:8102/mcp",
  "enabled": true,
  "read_only": true,
  "discovery_timeout_seconds": 10,
  "call_timeout_seconds": 20
}
```

> ⚠️ 地址必须写 model-service **能访问到**的地址（不要写 `127.0.0.1`——
> 那个地址在 model-service 看来是它自己。

改完在管理页点「重新连接」，工具列表里会出现 4 个音乐工具。

## 在小慧控制台里用

控制台有独立的「音乐」页签，直接调用 REST 接口，不需要经过 MCP：

- 搜索框：歌名 / 歌手 / 关键词
- 快捷标签：放松 / 专注 / 运动 / 睡前 / 开心 / 怀旧
- 每首歌带「▶ 试听」和「商店页 ↗」

控制台通过 `MUSIC_BASE_URL`（默认 `http://127.0.0.1:8102`）访问本服务。

## 防火墙

其他机器要访问 8102，需要放行（管理员）：

```powershell
netsh advfirewall firewall add rule name="xiaohui-svc-8102" dir=in action=allow protocol=TCP localport=8102 remoteip=100.64.0.0/10
```

`allow-firewall.ps1` 已经包含这条规则。
