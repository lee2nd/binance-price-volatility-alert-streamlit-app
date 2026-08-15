# Binance Price Alert

監控 Binance.US 現貨幣種的短時間漲跌幅，超過門檻就發 Telegram 通知。部署在 [Streamlit Community Cloud](https://share.streamlit.io)。

## 部署步驟

1. 把 `app.py`、`requirements.txt` push 到 GitHub repo
2. 到 https://share.streamlit.io -> **New app**，選這個 repo / branch，**Main file path** 填 `app.py`
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

## 注意事項

- Streamlit Community Cloud 的免費 app 閒置一段時間會進入休眠（顯示 "Zzz"），有人打開頁面才會被喚醒重跑；休眠期間背景監控會跟著停掉，喚醒後需要重新按「開始監控」。如果要接近 24 小時不中斷，得自己想辦法保持有人/有東西定期 access（例如外部排程定時打開 app 網址），或改用其他常駐主機。
- 每次 app reboot（不論是你手動 reboot、改了程式碼重新 push、還是被喚醒重跑）背景執行緒都會重置，都要重新按一次「開始監控」。
- 多個瀏覽器分頁 / 多人同時打開同一個 app 網址，看到的是同一個背景執行緒狀態（因為用 `st.cache_resource` 共用），不會各自開一份。
