# Binance Price Alert

監控 Binance Futures 幣種的短時間漲跌幅，超過門檻就發 Telegram 通知。部署在 [Streamlit Community Cloud](https://share.streamlit.io)。

## 部署步驟

1. 把 `app.py`、`requirements.txt` push 到 GitHub repo（可以放進 `frank-trading-toolkit`，也可以另開新 repo）
2. 到 https://share.streamlit.io -> **New app**，選這個 repo / branch，**Main file path** 填 `app.py`（若放在子資料夾，例如 `alert/app.py`，就填完整路徑）
3. 點 App 右下角 **⋮ → Settings → Secrets**，用 TOML 格式貼上：

   ```toml
   TELEGRAM_BOT_TOKEN = "你的 token"
   TELEGRAM_CHAT_ID = "你的 chat id"
   ```

4. 存檔後選 **Reboot app** 讓 Secrets 生效

## 使用方式

1. 選監控幣種、設定漲跌幅門檻與檢查間隔
2. 按「開始監控」，背景執行緒會持續檢查並在觸發門檻時發 Telegram 通知
3. 頁面下方「狀態」區塊每 2 秒自動更新，可看到目前是否運行中、最近一次檢查結果、累計通知次數
4. 按「停止監控」即可暫停

## 注意事項

- Streamlit Community Cloud 的免費 app 閒置一段時間會進入休眠（顯示 "Zzz"），有人打開頁面才會被喚醒重跑；休眠期間背景監控會跟著停掉，喚醒後需要重新按「開始監控」。如果要接近 24 小時不中斷，得自己想辦法保持有人/有東西定期access（例如外部排程定時打開 app 網址），或改用其他常駐主機。
- 每次 app reboot（不論是你手動 reboot、改了程式碼重新 push、還是被喚醒重跑）背景執行緒都會重置，都要重新按一次「開始監控」。
- 多個瀏覽器分頁 / 多人同時打開同一個 app 網址，看到的是同一個背景執行緒狀態（因為用 `st.cache_resource` 共用），不會各自開一份。
