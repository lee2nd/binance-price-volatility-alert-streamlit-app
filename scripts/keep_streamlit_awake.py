"""
用 headless 瀏覽器真的「造訪」一次 Streamlit app 網址，讓 Streamlit Community Cloud
判定為有流量，藉此延後 12 小時無流量自動休眠的時間。

如果去造訪時剛好 app 已經睡著了，畫面上會出現「Yes, get this app back up!」的喚醒按鈕，
腳本會自動點下去並等它重新啟動完成。

環境變數：
    STREAMLIT_APP_URL  你的 app 網址，例如
                        https://binance-price-volatility-alert-streamlit-app.streamlit.app
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright

WAKE_BUTTON_TEXT = "Yes, get this app back up!"
PAGE_LOAD_TIMEOUT_MS = 30_000
WAKE_WAIT_TIMEOUT_MS = 60_000


def main() -> int:
    app_url = os.environ.get("STREAMLIT_APP_URL", "").strip()
    if not app_url:
        print("尚未設定 STREAMLIT_APP_URL，請到 repo 的 Settings -> Secrets and variables -> "
              "Actions 新增這個 secret。")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        print(f"造訪 {app_url} ...")
        page.goto(app_url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")

        # 給頁面一點時間把內容（或睡眠畫面）渲染出來
        page.wait_for_timeout(5_000)

        wake_button = page.get_by_text(WAKE_BUTTON_TEXT, exact=False)
        if wake_button.count() > 0:
            print("偵測到 app 目前是休眠狀態，點擊喚醒按鈕...")
            wake_button.first.click()
            # 喚醒後 Streamlit 需要一點時間重新啟動，這裡多等一下再確認
            start = time.time()
            while time.time() - start < WAKE_WAIT_TIMEOUT_MS / 1000:
                page.wait_for_timeout(5_000)
                if wake_button.count() == 0:
                    print("app 已重新啟動完成。")
                    break
            else:
                print("等待喚醒完成逾時，但按鈕已點擊，下次排程再確認一次。")
        else:
            print("app 目前是醒著的，這次造訪順便延後休眠時間。")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
