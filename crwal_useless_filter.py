import re
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from dicts import USELESS_KEYWORDS

STATE_PATH = "everytime_state.json"
START_URL = "https://everytime.kr/384921"   # 자유게시판 - current: 30
PAGES_TO_SCRAPE = 30                         # 몇 페이지까지 저장할지
OUT_PATH = Path("everytime_posts_filtered.jsonl")    # 줄단위 JSON 저장

def extract_posts_on_page(page):
    """
    현재 페이지의 글 목록에서 제목/요약/시간/링크를 추출해서 list[dict]로 반환
    HTML 구조(네가 준 것) 기준:
      div.wrap.articles > article.list > a.article > div.desc > h2 + p + div.info(time)
    """
    posts = []
    items = page.locator("div.wrap.articles article.list a.article")
    count = items.count()

    for i in range(count):
        a = items.nth(i)

        title = a.locator("h2.medium.bold").first.inner_text().strip()
        # 🚫 제목에 쓸모없는 키워드가 포함되면 스킵
        if is_useless_title(title):
            print(f"[SKIP] {title}")
            continue
        snippet = a.locator("p.medium").first.inner_text().strip()

        # 시간은 없는 글도 있을 수 있어서 안전하게
        time_loc = a.locator("time.small")
        post_time = time_loc.first.inner_text().strip() if time_loc.count() else ""

        href = a.get_attribute("href") or ""
        # href가 /384921/v/... 형태이므로 절대 URL로 바꿔 저장
        abs_url = page.url.split("/p/")[0].rstrip("/")  # https://everytime.kr/384921 또는 .../p/n 제거
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

def is_useless_title(title: str) -> bool:
    title_lower = title.lower()
    return any(k.lower() in title_lower for k in USELESS_KEYWORDS)


def append_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1000)  # 천천히 보이게
    context = browser.new_context(storage_state=STATE_PATH)

    # 팝업/alert 같은 게 뜨면 닫아버리기(안전장치)
    context.on("dialog", lambda d: d.dismiss())

    page = context.new_page()
    page.goto(START_URL, wait_until="domcontentloaded")

    for page_idx in range(1, PAGES_TO_SCRAPE + 1):
        # 목록 로딩 보장: 글 리스트가 최소 1개 뜰 때까지
        page.locator("div.wrap.articles article.list").first.wait_for(timeout=15_000)

        posts = extract_posts_on_page(page)
        append_jsonl(OUT_PATH, posts)

        print(f"[{page_idx}] saved {len(posts)} posts from: {page.url}")

        # 각 페이지 잠깐 멈춰서 눈으로 확인
        # page.wait_for_timeout(2500)

        # 마지막 페이지면 종료
        if page_idx == PAGES_TO_SCRAPE:
            break

        # "다음" 클릭해서 이동 (네 HTML: <a class="next">다음</a>)
        next_link = page.locator("div.pagination a.next")
        if next_link.count() == 0:
            print("다음 링크를 못 찾음. 종료.")
            break

        next_link.scroll_into_view_if_needed()
        next_link.click()

        # URL이 /p/<숫자> 형태로 바뀌는 걸 기다림
        page.wait_for_url(re.compile(r".*/p/\d+"), timeout=15_000)
        page.wait_for_load_state("domcontentloaded")

    print(f"Done. Output: {OUT_PATH.resolve()}")

