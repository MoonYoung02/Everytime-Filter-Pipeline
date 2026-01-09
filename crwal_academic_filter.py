import re
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# dicts.py에 ACADEMIC_KEYWORDS가 있다면 이렇게:
from dicts import ACADEMIC_KEYWORDS

STATE_PATH = "everytime_state.json"
START_URL = "https://everytime.kr/384921"        # 자유게시판
PAGES_TO_SCRAPE = 10
OUT_PATH = Path("raw_academic.jsonl")  # 줄단위 JSON 저장

def contains_academic_keyword(title: str, snippet: str) -> bool:
    """
    제목 또는 snippet에 ACADEMIC_KEYWORDS 중 하나라도 포함되면 True
    """
    t = (title or "").lower()
    s = (snippet or "").lower()
    return any(k.lower() in t or k.lower() in s for k in ACADEMIC_KEYWORDS)

def extract_posts_on_page(page):
    posts = []
    items = page.locator("div.wrap.articles article.list a.article")
    count = items.count()

    for i in range(count):
        a = items.nth(i)

        title = a.locator("h2.medium.bold").first.inner_text().strip()
        snippet = a.locator("p.medium").first.inner_text().strip()

        # 학사 키워드가 제목/요약에 없으면 스킵
        if not contains_academic_keyword(title, snippet):
            # 필요하면 스킵 로그
            # print(f"[SKIP] {title} / {snippet}")
            continue

        time_loc = a.locator("time.small")
        post_time = time_loc.first.inner_text().strip() if time_loc.count() else ""

        href = a.get_attribute("href") or ""
        if href.startswith("/"):
            full_url = "https://everytime.kr" + href
        else:
            full_url = href

        posts.append({
            "board_url": page.url,
            "post_url": full_url,
            "title": title,
            "snippet": snippet,
            "time": post_time,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        })

    return posts

def append_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(storage_state=STATE_PATH)
    context.on("dialog", lambda d: d.dismiss())

    page = context.new_page()
    page.goto(START_URL, wait_until="domcontentloaded")

    for page_idx in range(1, PAGES_TO_SCRAPE + 1):
        page.locator("div.wrap.articles article.list").first.wait_for(timeout=15_000)

        posts = extract_posts_on_page(page)
        append_jsonl(OUT_PATH, posts)

        print(f"[{page_idx}] saved {len(posts)} posts from: {page.url}")

        if page_idx == PAGES_TO_SCRAPE:
            break

        next_link = page.locator("div.pagination a.next")
        if next_link.count() == 0:
            print("다음 링크를 못 찾음. 종료.")
            break

        next_link.scroll_into_view_if_needed()
        next_link.click()

        page.wait_for_url(re.compile(r".*/p/\d+"), timeout=15_000)
        page.wait_for_load_state("domcontentloaded")

    print(f"Done. Output: {OUT_PATH.resolve()}")
