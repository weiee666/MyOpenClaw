# ============================================================
# 杀戮尖塔2 游戏助手 — 基于 Qdrant 向量检索 + OpenAI GPT
# ============================================================
# 用法：python chat_qdrant.py
# 输入游戏问题，按 Enter 获取回答，输入 quit 退出
# ============================================================

import os
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

# ── 配置（从 .env 文件读取）────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
QDRANT_URL     = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_GAME  = "STS2_GameData"
COLLECTION_VIDEO = "GameVideo_Guides"
EMBED_MODEL      = "text-embedding-3-small"
CHAT_MODEL       = "gpt-4o"
TOP_K            = 8    # 每个 collection 召回条数
# ──────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

SYSTEM_PROMPT = """你是杀戮尖塔2的专业游戏助手。
参考资料分两部分：【游戏数据】来自结构化数据库，【视频攻略】来自玩家上传的实战视频转录。
- 优先综合两部分资料回答，互相印证
- 引用视频内容时注明视频标题和时间
- 只使用提供的资料作答，不要编造
- 回答要具体、实用
- 用中文回答"""


def get_embedding(text: str) -> list[float]:
    resp = openai_client.embeddings.create(input=[text], model=EMBED_MODEL)
    return resp.data[0].embedding


def search_game(query: str, top_k: int = TOP_K, table_filter: str = None) -> list[dict]:
    """检索游戏结构化数据"""
    query_vec = get_embedding(query)

    search_filter = None
    if table_filter:
        from qdrant_client import models
        search_filter = models.Filter(
            must=[models.FieldCondition(
                key="table",
                match=models.MatchValue(value=table_filter)
            )]
        )

    hits = qdrant_client.query_points(
        collection_name=COLLECTION_GAME,
        query=query_vec,
        limit=top_k,
        query_filter=search_filter,
    ).points

    return [{"score": h.score, "_source": "game", **h.payload} for h in hits]


def search_video(query: str, top_k: int = TOP_K) -> list[dict]:
    """检索视频攻略转录"""
    query_vec = get_embedding(query)

    hits = qdrant_client.query_points(
        collection_name=COLLECTION_VIDEO,
        query=query_vec,
        limit=top_k,
    ).points

    return [{"score": h.score, "_source": "video", **h.payload} for h in hits]


def format_context(game_hits: list[dict], video_hits: list[dict]) -> str:
    parts = []

    if game_hits:
        lines = ["【游戏数据】"]
        for i, h in enumerate(game_hits, 1):
            lines.append(f"[{i}] (相关度:{h['score']:.3f}) {h.get('text', '')}")
        parts.append("\n".join(lines))

    if video_hits:
        lines = ["【视频攻略】"]
        for i, h in enumerate(video_hits, 1):
            title      = h.get("video_title", "未知视频")
            characters = ",".join(h.get("characters", []))
            cards      = ",".join(h.get("cards", []))
            relics     = ",".join(h.get("relics", []))
            potions    = ",".join(h.get("potions", []))
            entity_parts = []
            if characters:
                entity_parts.append(f"角色:{characters}")
            if cards:
                entity_parts.append(f"卡牌:{cards}")
            if relics:
                entity_parts.append(f"遗物:{relics}")
            if potions:
                entity_parts.append(f"药水:{potions}")
            entity_line = " | ".join(entity_parts) if entity_parts else "（无实体标签）"
            text = h.get("text", "")[:200]
            lines.append(
                f"[{i}] 《{title}》 (相关度:{h['score']:.3f})\n"
                f"{entity_line}\n"
                f"{text}..."
            )
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def ask(question: str, table_filter: str = None) -> str:
    game_hits  = search_game(question, table_filter=table_filter)
    video_hits = search_video(question)
    context    = format_context(game_hits, video_hits)

    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"{context}\n\n问题：{question}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def main():
    print("=" * 55)
    print("  杀戮尖塔2 游戏助手（Qdrant + GPT）")
    print("=" * 55)

    # 检查 Collection
    try:
        info_game  = qdrant_client.get_collection(COLLECTION_GAME)
        info_video = qdrant_client.get_collection(COLLECTION_VIDEO)
        print(f"  游戏数据：{info_game.points_count} 条 | 视频攻略：{info_video.points_count} 条")
    except Exception as e:
        print(f"  ✗ 无法连接 Qdrant：{e}")
        return

    print("  输入 quit 退出，输入 /卡牌、/遗物、/药水 可限定搜索范围")
    print("-" * 55)

    table_map = {"/卡牌": "卡牌", "/遗物": "遗物", "/药水": "药水",
                 "/角色": "角色", "/关系": None}

    while True:
        try:
            question = input("\n你的问题：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not question:
            continue
        if question.lower() == "quit":
            print("再见！")
            break

        # 检测过滤指令
        table_filter = None
        for prefix, tname in table_map.items():
            if question.startswith(prefix):
                table_filter = tname
                question = question[len(prefix):].strip()
                if table_filter:
                    print(f"  （限定搜索范围：{table_filter}）")
                break

        if not question:
            continue

        print("  检索中...", flush=True)
        try:
            answer = ask(question, table_filter=table_filter)
            print(f"\n助手：{answer}")
        except Exception as e:
            print(f"  ✗ 出错：{e}")


if __name__ == "__main__":
    main()
