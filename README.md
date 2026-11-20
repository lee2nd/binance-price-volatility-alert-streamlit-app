# Binance Price Alert

監控 Binance.US 現貨幣種的短時間漲跌幅，超過門檻就發 Telegram 通知。部署在 [Streamlit Community Cloud](https://share.streamlit.io)。

## 部署步驟

1. 把 `app.py`、`requirements.txt` push 到 GitHub repo（可以放進 `frank-trading-toolkit`，也可以另開新 repo）
2. 到 https://share.streamlit.io -> **New app**，選這個 repo / branch，**Main file path** 填 `app.py`（若放在子資料夾，例如 `alert/app.py`，就填完整路徑）
3. 點 App 右下角 **⋮ → Settings → Secrets**，用 TOML 格式貼上：

   ```toml
   TELEGRAM_BOT_TOKEN = "你的 token"
   TELEGRAM_CHAT_ID = "你的 chat id"
   ```

4. 存檔後選 **Reboot app** 讓 Secrets 生效

## 為什麼是 Binance.US

Streamlit Community Cloud 的伺服器跑在美國，Binance 主站（Futures/Spot）依規定會擋美國地區
IP，會遇到 `Service unavailable from a restricted location` 這種錯誤。Binance.US 是給美國
用戶用的合規站台，不會擋美國 IP，所以這個版本改用 `Client(tld="us")` 打 Binance.US，不需要
額外的 proxy。

代價是：

- **只有現貨，沒有永續合約 / Futures**：程式改成打 `get_klines` / `get_exchange_info`（現貨
  端點），不是原本的 `futures_klines` / `futures_exchange_info`。現貨的波動特性跟 Futures
  不完全一樣，沒有槓桿驅動的劇烈波動，觸發頻率可能會比原本用 Futures 時低
- **可選幣種變少**：Binance.US 上架的交易對比 Binance 主站少很多。`BTCUSDT / ETHUSDT /
  SOLUSDT` 這三個預設幣種都有，但比較冷門的幣可能選不到

## 使用方式

1. 選監控幣種、設定漲跌幅門檻與檢查間隔
2. 按「開始監控」，背景執行緒會持續檢查並在觸發門檻時發 Telegram 通知
3. 頁面下方「狀態」區塊每 2 秒自動更新，可看到目前是否運行中、最近一次檢查結果、累計通知次數
4. 按「停止監控」即可暫停

## Keep Awake（自動保持喚醒）

`.github/workflows/keep-streamlit-awake.yml` 這個 GitHub Actions 會自動幫 app 保持醒著：

- **觸發方式**：只保留 `workflow_dispatch`，不使用 GitHub 的 `schedule` 排程。
  原因是 GitHub 會在 repo 連續 60 天沒有 commit 活動時自動停用 `schedule` 觸發，
  且這個 workflow 自己的執行紀錄不算活動，等於每隔一段時間就會悄悄失效、需要人工回去
  手動點 **Enable workflow** 才能恢復，很容易忽略。
- **實際排程方式**：改用外部免費排程服務 [cron-job.org](https://cron-job.org/) 每 6 小時
  呼叫一次 GitHub REST API（`POST /repos/<owner>/<repo>/actions/workflows/keep-streamlit-awake.yml/dispatches`）
  來觸發 `workflow_dispatch`，不受 GitHub 那個 60 天自動停用規則影響；也可以隨時在
  GitHub 的 Actions 分頁手動點 **Run workflow** 立即跑一次（例如剛部署完想馬上測試）
- **運作方式**：用 headless 瀏覽器（Playwright）真的造訪一次 app 網址；如果去的時候
  app 剛好已經睡著了，會自動點「Yes, get this app back up!」把它喚醒
  （單純對 app 網址發 HTTP GET 是不夠的——那只會打到 Streamlit Community Cloud 的靜態
  殼頁面，碰不到實際的 app container，所以不能只靠 cron-job.org 直接 ping app 網址）
- **需要的設定**：
  - repo 的 **Settings → Secrets and variables → Actions** 要有一個
    secret `STREAMLIT_APP_URL`，值是你的 app 網址
  - 到 [cron-job.org](https://cron-job.org/) 設定一個 Cronjob：
    - URL：`https://api.github.com/repos/<owner>/<repo>/actions/workflows/keep-streamlit-awake.yml/dispatches`
    - Method：`POST`
    - Headers：`Accept: application/vnd.github+json`、`Authorization: Bearer <你的 GitHub PAT>`、
      `X-GitHub-Api-Version: 2022-11-28`、`Content-Type: application/json`
    - Request body：`{"ref":"main"}`
    - 排程：每 6 小時一次（例如每天 00:00 / 06:00 / 12:00 / 18:00 UTC）
    - PAT 建議用 fine-grained personal access token，只授權這個 repo 的
      **Actions：Read and write** 權限，降低外洩風險
- **喚醒後還是要手動按開始監控**：這個 Actions 只能保持 app 醒著、或把睡著的 app 叫醒，
  但不管是哪一種情況，Streamlit process 重啟後背景監控執行緒的狀態都會歸零，
  還是要有人進去點一次「開始監控」，這步沒辦法自動化

## 注意事項

- Streamlit Community Cloud 的免費 app 閒置一段時間會進入休眠（顯示 "Zzz"），有人打開頁面才會被喚醒重跑；休眠期間背景監控會跟著停掉，喚醒後需要重新按「開始監控」。如果要接近 24 小時不中斷，得自己想辦法保持有人/有東西定期 access（例如外部排程定時打開 app 網址），或改用其他常駐主機。
- 每次 app reboot（不論是你手動 reboot、改了程式碼重新 push、還是被喚醒重跑）背景執行緒都會重置，都要重新按一次「開始監控」。
- 多個瀏覽器分頁 / 多人同時打開同一個 app 網址，看到的是同一個背景執行緒狀態（因為用 `st.cache_resource` 共用），不會各自開一份。
