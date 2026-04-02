"""
MCP Server for Slay the Spire 2 Game Assistant
Exposes search_game_data tool backed by Qdrant vector search.
"""

import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from qdrant_client import QdrantClient

# ── Config (从 .env 文件读取) ─────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
QDRANT_URL     = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "STS2_GameData"
EMBED_MODEL     = "text-embedding-3-small"
TOP_K           = 10
# ─────────────────────────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

mcp = FastMCP("game-assistant")


def _get_embedding(text: str) -> list[float]:
    resp = openai_client.embeddings.create(input=[text], model=EMBED_MODEL)
    return resp.data[0].embedding


def _search(query: str, category: str = "") -> list[dict]:
    query_vec = _get_embedding(query)

    search_filter = None
    if category:
        from qdrant_client import models
        search_filter = models.Filter(
            must=[models.FieldCondition(
                key="table",
                match=models.MatchValue(value=category)
            )]
        )

    hits = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=TOP_K,
        query_filter=search_filter,
    ).points

    return [{"score": h.score, **h.payload} for h in hits]


def _format_context(hits: list[dict]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        score = h.get("score", 0)
        text  = h.get("text", "")
        lines.append(f"[{i}] (相关度:{score:.3f}) {text}")
    return "\n".join(lines)


@mcp.tool()
def search_game_data(query: str, category: str = "") -> str:
    """Search Slay the Spire 2 game data.

    Args:
        query: 查询内容（中英文均可）
        category: 可选过滤，值为 卡牌 / 遗物 / 药水 / 角色，空字符串表示全部

    Returns:
        相关游戏数据文本，供 AI 综合回答
    """
    hits = _search(query, category)
    if not hits:
        return "未找到相关游戏数据。"
    return _format_context(hits)


if __name__ == "__main__":
    mcp.run()
