"""GitHub Profile README auto-updater (stdlib only).

Fetches my blog RSS + public repo list, rewrites the block between
`---start---` and `---end---` in README.md. Runs in GitHub Actions;
each failure degrades to a placeholder instead of killing the update.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

USER = "yangyang1187"
BLOG_RSS = "https://v2yy.com/rss.xml"
UA = {"User-Agent": "profile-readme-bot", "Accept": "application/vnd.github+json"}


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def blog_posts(limit: int = 3):
    """Top-N recent posts from the blog's RSS 2.0 feed."""
    try:
        root = ET.fromstring(http_get(BLOG_RSS))
        items = []
        for it in root.findall("./channel/item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if title and link:
                items.append((title, link))
        if not items:
            raise ValueError("feed has no items")
        return items[:limit]
    except Exception as exc:  # noqa: BLE001 - keep README updating anyway
        print(f"WARN: blog feed unavailable: {exc}", file=sys.stderr)
        return None


def featured_repos(limit: int = 5):
    """Non-fork public repos sorted by stars then recency (profile repo excluded)."""
    try:
        data = json.loads(
            http_get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed&direction=desc")
        )
        repos = [r for r in data if not r["fork"] and r["name"].lower() != USER.lower()]
        repos.sort(key=lambda r: (r["stargazers_count"], r["pushed_at"]), reverse=True)
        return [
            (r["name"], r["html_url"], r["stargazers_count"], (r["description"] or "").strip())
            for r in repos[:limit]
        ]
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: repo list unavailable: {exc}", file=sys.stderr)
        return None


def build_block() -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    out = [
        "---start---\n\n",
        "## 📌 自动生成区\n\n",
        f"> 更新时间：{now}（北京时间）· 由 GitHub Actions 每天 09:15 / 17:15 自动抓取，无需人工维护\n\n",
        "### 📰 博客最新（[v2yy.com](https://v2yy.com)）\n\n",
    ]
    posts = blog_posts()
    if posts:
        out += [f"- [{title}]({link})\n" for title, link in posts]
    else:
        out.append("- （RSS 暂时抓不到，下次运行会自动恢复）\n")
    out.append("\n### 🔧 开源项目精选\n\n")
    repos = featured_repos()
    if repos:
        out += [
            f"- **[{name}]({url})** ⭐{stars}" + (f" · {desc}" if desc else "") + "\n"
            for name, url, stars, desc in repos
        ]
    else:
        out.append("- （GitHub API 暂时不可用）\n")
    out.append("\n---end---")
    return "".join(out)


def main() -> None:
    path = "README.md"
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    if "---start---" not in content or "---end---" not in content:
        sys.exit("README.md missing ---start---/---end--- markers")
    new = re.sub(
        r"---start---(.|\n)*---end---",
        lambda _m: build_block(),
        content,
        count=1,
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    print("README.md updated")


if __name__ == "__main__":
    main()
