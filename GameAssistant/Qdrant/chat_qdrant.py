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

COLLECTION_NAME = "STS2_GameData"
EMBED_MODEL     = "text-embedding-3-small"
CHAT_MODEL      = "gpt-4o"
TOP_K           = 10    # 每次检索召回条数
# ──────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

SYSTEM_PROMPT = """你是杀戮尖塔2的专业游戏助手。
根据提供的游戏数据（卡牌、遗物、药水、角色、怪物等），回答玩家的问题。
- 只使用提供的数据作答，不要编造不存在的内容
- 回答要具体、实用，适合玩家实际使用
- 如果数据不足以回答，请直接说明
- 用中文回答"""


def get_embedding(text: str) -> list[float]:
    resp = openai_client.embeddings.create(input=[text], model=EMBED_MODEL)
    return resp.data[0].embedding


def search(query: str, top_k: int = TOP_K, table_filter: str = None) -> list[dict]:
    """向量检索，可选按表名过滤"""
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
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
        query_filter=search_filter,
    ).points

    return [{"score": h.score, **h.payload} for h in hits]


def format_context(hits: list[dict]) -> str:
    """把检索结果格式化为 GPT 上下文"""
    lines = []
    for i, h in enumerate(hits, 1):
        score = h.get("score", 0)
        text  = h.get("text", "")
        lines.append(f"[{i}] (相关度:{score:.3f}) {text}")
    return "\n".join(lines)


def ask(question: str) -> str:
    hits    = search(question)
    context = format_context(hits)

    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"游戏数据：\n{context}\n\n问题：{question}"},
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
        info = qdrant_client.get_collection(COLLECTION_NAME)
        print(f"  已连接数据库，共 {info.points_count} 条向量")
    except Exception as e:
        print(f"  ✗ 无法连接 Qdrant：{e}")
        print(f"  请先运行 upload_to_qdrant.py 入库")
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
            answer = ask(question) if not table_filter else _ask_filtered(question, table_filter)
            print(f"\n助手：{answer}")
        except Exception as e:
            print(f"  ✗ 出错：{e}")


def _ask_filtered(question: str, table_filter: str) -> str:
    hits    = search(question, table_filter=table_filter)
    context = format_context(hits)
    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"游戏数据：\n{context}\n\n问题：{question}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    main()
