# ============================================================
# Slay the Spire 2 - 贴吧攻略搜索 (RAG-GPT style)
# ============================================================
# 流程：
#   1. SerpAPI Baidu 引擎 → 搜索杀戮尖塔2吧攻略帖子链接
#   2. OpenAI built-in web_search → 逐篇读取每个帖子全文
#   3. OpenAI Responses API → 综合提炼固定数量的攻略
# ============================================================
# 安装依赖：
#   pip install openai serpapi
# ============================================================

import os
import json
import serpapi
from dotenv import load_dotenv
from openai import OpenAI

# ------------------------------------------------------------
# Configuration (从 .env 文件读取)
# ------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY    = os.getenv("SERPAPI_KEY")

NUM_RESULTS    = 5       # 要返回的攻略条数
MODEL          = "gpt-4o"

# 固定在杀戮尖塔2贴吧内搜索攻略帖子
TIEBA_URL      = "https://tieba.baidu.com/f?kw=%E6%9D%80%E6%88%AE%E5%B0%96%E5%A1%942"
SEARCH_QUERY   = "杀戮尖塔2 攻略 site:tieba.baidu.com"

OUTPUT_DIR     = os.path.join(os.path.dirname(__file__), "saved_pages")

client = OpenAI(api_key=OPENAI_API_KEY)


# ------------------------------------------------------------
# Step 1: 用 SerpAPI Baidu 引擎搜索贴吧帖子链接
# ------------------------------------------------------------
def search_tieba_posts(query: str, num: int) -> list[dict]:
    """
    通过 SerpAPI 的百度引擎搜索贴吧帖子，返回 [{title, link, snippet}]
    """
    serp_client = serpapi.Client(api_key=SERPAPI_KEY)
    results = serp_client.search({
        "engine": "baidu",
        "q": query,
        "hl": "zh-cn",
        "num": num * 2,   # 多取一些，过滤掉非帖子链接
    })
    organic = results.get("organic_results", [])

    # 只保留 tieba.baidu.com/p/ 开头的帖子链接
    posts = [r for r in organic if "/p/" in r.get("link", "")][:num]
    print(f"[搜索] 找到 {len(posts)} 篇贴吧帖子（查询：'{query}'）")
    return posts


# ------------------------------------------------------------
# Step 2: 用 OpenAI web_search 读取每篇帖子内容
# ------------------------------------------------------------
def read_post_via_openai(title: str, url: str, snippet: str) -> str:
    """
    让 OpenAI 使用内置 web_search 工具读取指定帖子 URL，
    返回提取出的攻略文字摘要。
    """
    resp = client.responses.create(
        model=MODEL,
        input=[{
            "role": "user",
            "content": (
                f"请访问这个百度贴吧帖子并提取其中的游戏攻略内容：\n"
                f"标题：{title}\n"
                f"链接：{url}\n"
                f"摘要参考：{snippet}\n\n"
                f"用中文总结该帖子中的《杀戮尖塔2》攻略要点（300字以内）。"
            )
        }],
        tools=[{"type": "web_search_preview"}],
        tool_choice={"type": "web_search_preview"},
    )
    return resp.output_text


# ------------------------------------------------------------
# Step 3: 综合所有帖子内容，输出固定数量攻略
# ------------------------------------------------------------
def synthesize_guides(posts_content: list[dict], num_guides: int) -> str:
    """
    将所有帖子内容拼成 RAG context，让 OpenAI 整理成编号攻略列表。
    """
    context = "\n\n".join([
        f"=== 帖子 {i+1} ===\n标题：{p['title']}\nURL：{p['url']}\n内容：{p['content']}"
        for i, p in enumerate(posts_content)
    ])

    resp = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "你是《杀戮尖塔2》游戏攻略助手。"
                    "根据用户提供的贴吧帖子内容，整理出清晰的游戏攻略。"
                    f"请输出恰好 {num_guides} 条攻略，每条包含：攻略标题、来源URL、具体攻略内容。"
                    "用中文输出，格式为编号列表。"
                )
            },
            {
                "role": "user",
                "content": (
                    f"以下是从百度贴吧《杀戮尖塔2》吧获取的 {len(posts_content)} 篇帖子内容：\n\n"
                    f"{context}\n\n"
                    f"请整理出 {num_guides} 条游戏攻略。"
                )
            }
        ],
    )
    return resp.output_text


# ------------------------------------------------------------
# Step 4: 保存帖子页面快照（HTML）
# ------------------------------------------------------------
def save_html_snapshot(index: int, title: str, url: str, content: str):
    """
    将帖子内容存为本地 HTML 文件，仿照 bios40 格式，可在浏览器打开查看。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:60]
    fname = f"{index}_{safe_title}.html"
    fpath = os.path.join(OUTPUT_DIR, fname)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
           max-width: 860px; margin: 40px auto; padding: 0 20px;
           line-height: 1.8; color: #222; background: #fafafa; }}
    h1   {{ font-size: 1.4em; border-bottom: 2px solid #c0392b;
           padding-bottom: 8px; color: #c0392b; }}
    .meta {{ font-size: 0.85em; color: #666; margin-bottom: 20px; }}
    .meta a {{ color: #2980b9; }}
    .content {{ background: #fff; border: 1px solid #ddd;
               border-radius: 6px; padding: 24px;
               white-space: pre-wrap; word-wrap: break-word; }}
    .badge {{ display:inline-block; background:#c0392b; color:#fff;
             padding:2px 10px; border-radius:12px; font-size:0.8em;
             margin-bottom:12px; }}
  </style>
</head>
<body>
  <span class="badge">杀戮尖塔2 · 百度贴吧攻略</span>
  <h1>{title}</h1>
  <div class="meta">
    来源：<a href="{url}" target="_blank">{url}</a>
  </div>
  <div class="content">{content}</div>
</body>
</html>"""

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"    已保存 → saved_pages/{fname}")
    return fpath


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------
def main():
    print("=" * 60)
    print("杀戮尖塔2 贴吧攻略搜索（RAG-GPT 风格）")
    print(f"贴吧地址：{TIEBA_URL}")
    print(f"返回条数：{NUM_RESULTS}")
    print("=" * 60)

    # 1. 搜索贴吧帖子
    posts = search_tieba_posts(SEARCH_QUERY, num=NUM_RESULTS)
    if not posts:
        print("未找到帖子，请检查 SerpAPI key 或搜索词。")
        return

    # 2. 用 OpenAI web_search 读取每篇帖子 + 保存 HTML
    print("\n[读取帖子内容中...]")
    posts_content = []
    saved_files = []
    for i, post in enumerate(posts, 1):
        title   = post.get("title", f"帖子{i}")
        url     = post.get("link", "")
        snippet = post.get("snippet", "")
        print(f"[{i}/{len(posts)}] {title[:50]}")

        content = read_post_via_openai(title, url, snippet)
        posts_content.append({"title": title, "url": url, "content": content})

        fpath = save_html_snapshot(i, title, url, content)
        saved_files.append(fpath)

    # 3. 综合成攻略列表
    print("\n[OpenAI 整理攻略中...]")
    answer = synthesize_guides(posts_content, NUM_RESULTS)

    # 4. 输出结果
    print("\n" + "=" * 60)
    print(f"《杀戮尖塔2》TOP {NUM_RESULTS} 贴吧攻略")
    print("=" * 60)
    print(answer)

    print(f"\n[HTML 快照已保存至: {OUTPUT_DIR}]")
    for f in saved_files:
        print(f"  {os.path.basename(f)}")
    print("用浏览器打开上述 .html 文件即可查看每篇帖子内容。")


if __name__ == "__main__":
    main()
