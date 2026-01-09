from playwright.sync_api import sync_playwright

STATE_PATH = "everytime_state.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()

    # 다이얼로그가 뜨면 자동으로 닫기/확인
    context.on("dialog", lambda dialog: dialog.dismiss())

    page = context.new_page()
    page.goto("https://account.everytime.kr/login", wait_until="domcontentloaded")

    print("브라우저에서 직접 로그인한 뒤, 첫 화면이 뜨면 Enter를 누르세요.")
    input()

    # 혹시 로그인 직후 네비게이션/JS 작업이 끝나기 전에 state 저장하면 꼬일 수 있으니 대기
    page.wait_for_timeout(1500)

    context.storage_state(path=STATE_PATH)
    browser.close()

print(f"Saved session to {STATE_PATH}")