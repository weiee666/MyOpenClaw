# ============================================================
# 杀戮尖塔2 灰机Wiki 爬虫
# ============================================================
# 使用 Playwright 渲染 JS 页面，爬取 wiki 关键栏目，
# 将每个页面保存为可在浏览器查看的 HTML 文件（仿 bios40 格式）
# ============================================================
# 安装依赖：
#   pip install playwright beautifulsoup4
#   python -m playwright install chromium
# ============================================================

import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
BASE_URL   = "https://sts2.huijiwiki.com"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "saved_pages", "wiki")

# 要爬取的 wiki 页面（中文名 -> 路径）
PAGES = {
    "首页":     "/wiki/%E9%A6%96%E9%A1%B5",
    "角色总览":  "/wiki/%E8%A7%92%E8%89%B2",
    "铁甲战士":  "/wiki/%E9%93%81%E7%94%B2%E6%88%98%E5%A3%AB",
    "静默猎手":  "/wiki/%E9%9D%99%E9%BB%98%E7%8C%8E%E6%89%8B",
    "储君":     "/wiki/%E5%82%A8%E5%90%9B",
    "亡灵契约师": "/wiki/%E4%BA%A1%E7%81%B5%E5%A5%91%E7%BA%A6%E5%B8%88",
    "故障机器人": "/wiki/%E6%95%85%E9%9A%9C%E6%9C%BA%E5%99%A8%E4%BA%BA",
    "游戏指南":  "/wiki/%E6%B8%B8%E6%88%8F%E6%8C%87%E5%8D%97",
    "怪物图鉴":  "/wiki/%E6%80%AA%E7%89%A9",
    "遗物":     "/wiki/%E9%81%97%E7%89%A9",
}

WAIT_BETWEEN = 1.5   # 每次请求间隔（秒），避免对服务器造成压力


# ------------------------------------------------------------
# Fetch & parse one wiki page with Playwright
# ------------------------------------------------------------
def fetch_wiki_page(page, url: str) -> tuple[str, str, list[dict]]:
    """
    返回 (page_title, clean_text, sublinks)
    sublinks: [{text, href, full_url}]
    """
    page.goto(url, timeout=30000)
    page.wait_for_load_state("networkidle", timeout=15000)
    html = page.content()

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.split(" - ")[0].strip() if soup.title else url

    # 提取正文
    content_el = soup.select_one("div.mw-parser-output")
    if not content_el:
        return title, "[页面内容为空或需要登录]", []

    # 收集内部 wiki 链接
    sublinks = []
    for a in content_el.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if href.startswith("/wiki/") and text and "特殊" not in href and "文件" not in href:
            sublinks.append({
                "text": text,
                "href": href,
                "full_url": BASE_URL + href
            })

    # 清理文字
    for tag in content_el(["script", "style"]):
        tag.decompose()
    text = content_el.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return title, text, sublinks


# ------------------------------------------------------------
# Save as styled HTML (bios40 style)
# ------------------------------------------------------------
def save_html(index: int, name: str, url: str, title: str,
              text: str, sublinks: list[dict]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)
    fname = f"{index:02d}_{safe_name}.html"
    fpath = os.path.join(OUTPUT_DIR, fname)

    # 构建子链接 HTML
    links_html = ""
    seen = set()
    for lk in sublinks:
        if lk["text"] not in seen and len(seen) < 30:
            seen.add(lk["text"])
            links_html += (
                f'<li><a href="{lk["full_url"]}" target="_blank">'
                f'{lk["text"]}</a></li>\n'
            )

    content_html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif;
      margin: 0; padding: 0; background: #1a1a2e; color: #e0e0e0;
    }}
    .header {{
      background: linear-gradient(135deg, #c0392b, #8e1a12);
      padding: 20px 40px;
    }}
    .header .badge {{
      display: inline-block; background: rgba(255,255,255,0.2);
      color: #fff; padding: 3px 12px; border-radius: 12px;
      font-size: 0.8em; margin-bottom: 8px;
    }}
    .header h1 {{ margin: 0; color: #fff; font-size: 1.6em; }}
    .header .source {{
      margin-top: 8px; font-size: 0.85em; color: rgba(255,255,255,0.7);
    }}
    .header .source a {{ color: #ffcdd2; }}
    .container {{
      display: flex; max-width: 1200px; margin: 30px auto; padding: 0 20px; gap: 24px;
    }}
    .sidebar {{
      flex: 0 0 220px; background: #16213e;
      border-radius: 8px; padding: 16px;
      border: 1px solid #2d3561; height: fit-content;
    }}
    .sidebar h3 {{ margin: 0 0 12px; font-size: 0.9em; color: #c0392b; text-transform: uppercase; letter-spacing: 1px; }}
    .sidebar ul {{ margin: 0; padding: 0 0 0 16px; }}
    .sidebar li {{ margin: 6px 0; font-size: 0.88em; }}
    .sidebar a {{ color: #90caf9; text-decoration: none; }}
    .sidebar a:hover {{ color: #fff; text-decoration: underline; }}
    .main {{
      flex: 1; background: #16213e;
      border-radius: 8px; padding: 24px;
      border: 1px solid #2d3561;
    }}
    .content {{
      white-space: pre-wrap; word-wrap: break-word;
      line-height: 1.9; font-size: 0.95em; color: #cfd8dc;
    }}
    .nav-bar {{
      background: #0f3460; padding: 10px 40px;
      display: flex; gap: 16px; flex-wrap: wrap;
    }}
    .nav-bar a {{
      color: #90caf9; font-size: 0.88em; text-decoration: none;
      padding: 4px 10px; border-radius: 4px;
    }}
    .nav-bar a:hover {{ background: rgba(144,202,249,0.15); }}
  </style>
</head>
<body>
  <div class="header">
    <div class="badge">杀戮尖塔2 · 灰机Wiki</div>
    <h1>{title}</h1>
    <div class="source">来源：<a href="{url}" target="_blank">{url}</a></div>
  </div>

  <div class="nav-bar">
    <a href="{BASE_URL}/wiki/%E9%A6%96%E9%A1%B5" target="_blank">🏠 首页</a>
    <a href="{BASE_URL}/wiki/%E8%A7%92%E8%89%B2" target="_blank">👤 角色</a>
    <a href="{BASE_URL}/wiki/%E6%B8%B8%E6%88%8F%E6%8C%87%E5%8D%97" target="_blank">📖 游戏指南</a>
    <a href="{BASE_URL}/wiki/%E6%80%AA%E7%89%A9" target="_blank">👾 怪物图鉴</a>
    <a href="{BASE_URL}/wiki/%E9%81%97%E7%89%A9" target="_blank">🏺 遗物</a>
  </div>

  <div class="container">
    <div class="sidebar">
      <h3>页内链接</h3>
      <ul>
{links_html}
      </ul>
    </div>
    <div class="main">
      <div class="content">{content_html}</div>
    </div>
  </div>
</body>
</html>"""

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)
    return fpath


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    print("=" * 60)
    print("杀戮尖塔2 灰机Wiki 爬虫")
    print(f"目标：{len(PAGES)} 个页面")
    print(f"保存至：{OUTPUT_DIR}")
    print("=" * 60)

    saved = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for i, (name, path) in enumerate(PAGES.items(), 1):
            url = BASE_URL + path
            print(f"\n[{i:02d}/{len(PAGES)}] 爬取：{name}")
            print(f"    URL: {url}")

            try:
                title, text, sublinks = fetch_wiki_page(page, url)
                fpath = save_html(i, name, url, title, text, sublinks)
                print(f"    ✓ 保存 → wiki/{os.path.basename(fpath)}")
                print(f"    文字长度：{len(text)} 字 | 子链接：{len(sublinks)} 个")
                saved.append(fpath)
            except Exception as e:
                print(f"    ✗ 失败：{e}")

            if i < len(PAGES):
                time.sleep(WAIT_BETWEEN)

        browser.close()

    print("\n" + "=" * 60)
    print(f"完成！共保存 {len(saved)} 个页面")
    print("=" * 60)
    for f in saved:
        print(f"  {os.path.basename(f)}")

    # 用浏览器打开首页快照
    if saved:
        import subprocess
        subprocess.Popen(["open", saved[0]])
        print(f"\n已在浏览器打开：{os.path.basename(saved[0])}")


if __name__ == "__main__":
    main()
