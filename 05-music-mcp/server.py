"""小慧 · 音乐 MCP Server

以 Streamable HTTP 方式提供音乐查询工具，供 model-service 的 MCP Client 注册。

数据源：Apple iTunes Search API（免费、无需 Key）
- 支持中文/英文关键词搜索
- 返回 30 秒试听直链（previewUrl），浏览器可直接播放

启动：
    python server.py            # 默认 0.0.0.0:8102，端点 /mcp
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

ITUNES_SEARCH = "https://itunes.apple.com/search"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
TIMEOUT = 12.0

mcp = FastMCP(
    "music",
    instructions="音乐搜索与试听服务。可以按歌名、歌手或风格搜索歌曲，返回可播放的试听链接。",
)
mcp.settings.host = os.getenv("MUSIC_HOST", "0.0.0.0")
mcp.settings.port = int(os.getenv("MUSIC_PORT", "8102"))

READ_ONLY = ToolAnnotations(readOnlyHint=True)


def _shape(item: Dict[str, Any]) -> Dict[str, Any]:
    """把 iTunes 的字段裁成模型好读的形状。"""
    ms = item.get("trackTimeMillis") or 0
    return {
        "track_id": item.get("trackId"),
        "title": item.get("trackName"),
        "artist": item.get("artistName"),
        "album": item.get("collectionName"),
        "duration_seconds": round(ms / 1000) if ms else None,
        "genre": item.get("primaryGenreName"),
        "release_date": (item.get("releaseDate") or "")[:10],
        "preview_url": item.get("previewUrl"),
        "cover_url": (item.get("artworkUrl100") or "").replace("100x100", "300x300"),
        "store_url": item.get("trackViewUrl"),
    }


def _search(query: str, limit: int, country: str) -> List[Dict[str, Any]]:
    params = {
        "term": query,
        "media": "music",
        "entity": "song",
        "limit": max(1, min(limit, 20)),
        "country": country,
        "lang": "zh_cn",
    }
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.get(ITUNES_SEARCH, params=params)
        r.raise_for_status()
        data = r.json()
    return [_shape(x) for x in data.get("results", []) if x.get("previewUrl")]


@mcp.tool(annotations=READ_ONLY)
def search_music(query: str, limit: int = 5, country: str = "cn") -> Dict[str, Any]:
    """按歌名、歌手或关键词搜索歌曲，返回可试听的歌曲列表。

    Args:
        query: 搜索关键词，例如「周杰伦 晴天」「爵士」「Taylor Swift」
        limit: 返回数量，1-20，默认 5
        country: 商店区域，cn 或 us，默认 cn；中文歌搜不到时可以试 us
    """
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "query 不能为空", "songs": []}

    songs = _search(q, limit, country)
    if not songs and country != "us":
        songs = _search(q, limit, "us")

    return {
        "ok": True,
        "query": q,
        "count": len(songs),
        "songs": songs,
        "note": "preview_url 是 30 秒试听直链，可直接播放" if songs else "没有找到带试听音源的歌曲",
    }


@mcp.tool(annotations=READ_ONLY)
def get_music_preview(track_id: int) -> Dict[str, Any]:
    """按歌曲 ID 获取详情和试听链接。

    Args:
        track_id: search_music 返回的 track_id
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(ITUNES_LOOKUP, params={"id": int(track_id), "country": "cn"})
            r.raise_for_status()
            results = r.json().get("results", [])
    except Exception as e:
        return {"ok": False, "error": f"查询失败：{e}"}

    if not results:
        return {"ok": False, "error": "没有找到这首歌曲"}

    song = _shape(results[0])
    return {"ok": True, "song": song}


@mcp.tool(annotations=READ_ONLY)
def recommend_music(mood: str = "轻松", limit: int = 5) -> Dict[str, Any]:
    """按心情或场景推荐几首歌。

    Args:
        mood: 心情或场景，例如「放松」「运动」「专注」「睡前」「开心」
        limit: 返回数量，1-20，默认 5
    """
    mapping = {
        "放松": "chill acoustic", "轻松": "chill acoustic",
        "安静": "piano relaxing", "睡前": "sleep piano",
        "运动": "workout upbeat", "跑步": "running motivation",
        "专注": "lofi study", "学习": "lofi study",
        "开心": "happy pop", "快乐": "happy pop",
        "伤感": "sad piano", "怀旧": "classic oldies",
        "中文": "华语流行", "国风": "国风 古风",
    }
    keyword = mapping.get((mood or "").strip(), mood or "chill")
    songs = _search(keyword, limit, "us")
    if not songs:
        songs = _search(keyword, limit, "cn")
    return {
        "ok": True,
        "mood": mood,
        "keyword_used": keyword,
        "count": len(songs),
        "songs": songs,
    }


@mcp.tool(annotations=READ_ONLY)
def list_moods() -> Dict[str, Any]:
    """列出推荐音乐支持的心情/场景关键词。"""
    return {
        "ok": True,
        "moods": ["放松", "轻松", "安静", "睡前", "运动", "跑步",
                  "专注", "学习", "开心", "快乐", "伤感", "怀旧", "中文", "国风"],
    }


# ---------------------------------------------------------------- REST 兼容层
# MCP 是给模型用的；控制台页面用普通 REST 更方便，两套接口共享同一份实现。

from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402


@mcp.custom_route("/rest/search", methods=["GET"])
async def rest_search(request: Request) -> JSONResponse:
    q = request.query_params.get("q", "")
    limit = int(request.query_params.get("limit", "5") or 5)
    country = request.query_params.get("country", "cn")
    return JSONResponse(search_music(q, limit, country))


@mcp.custom_route("/rest/recommend", methods=["GET"])
async def rest_recommend(request: Request) -> JSONResponse:
    mood = request.query_params.get("mood", "放松")
    limit = int(request.query_params.get("limit", "5") or 5)
    return JSONResponse(recommend_music(mood, limit))


@mcp.custom_route("/rest/health", methods=["GET"])
async def rest_health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "music-mcp", "tools": 4})


if __name__ == "__main__":
    transport = os.getenv("MUSIC_TRANSPORT", "streamable-http")
    print(f"music-mcp 启动：{mcp.settings.host}:{mcp.settings.port} transport={transport}")
    mcp.run(transport=transport)