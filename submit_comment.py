from playwright.sync_api import sync_playwright

STATE_PATH = "everytime_state.json"
POST_URL = "https://everytime.kr/384921/v/397723377"  # 댓글 달 글
COMMENT_TEXT = "ㅋㅋㅋㅋㅋㅋ"  # 여기에 원하는 댓글

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=400)
    context = browser.new_context(storage_state=STATE_PATH)

    # alert/popup 뜨면 닫기(안전장치)
    context.on("dialog", lambda d: d.dismiss())

    page = context.new_page()
    page.goto(POST_URL, wait_until="domcontentloaded")

    # 댓글 입력칸 대기
    comment_input = page.locator('form.writecomment input[name="text"]')
    comment_input.wait_for(timeout=3000)

    # (선택) 익명 토글을 켜고 싶으면 클릭
    # 익명 여부는 사이트가 class로 상태를 관리할 수 있어서, 토글이 필요할 때만 사용
    page.locator("form.writecomment ul.option li.anonym").click()

    # 댓글 입력
    comment_input.fill(COMMENT_TEXT)


    # 완료(등록) 클릭
    submit_btn = page.locator("form.writecomment ul.option li.submit")
    submit_btn.click()

    # 등록 후 댓글이 로딩되는 시간 조금 기다림
    page.wait_for_timeout(2000)

    print("등록 시도 완료. 실제로 달렸는지 화면에서 확인하세요.")
    input("Enter 누르면 종료")
