---
title: Binance Price Alert
emoji: 🚨
colorFrom: yellow
colorTo: red
sdk: streamlit
app_file: app.py
pinned: false
---

# Binance Price Alert

監控 Binance Futures 幣種的短時間漲跌幅，超過門檻就發 Telegram 通知。

## 部署前準備

到這個 Space 的 **Settings → Variables and secrets → New secret**，新增（類型選 **Secret**）：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

存好後重新整理頁面即可使用。

## 使用方式

1. 選監控幣種、設定漲跌幅門檻與檢查間隔
2. 按「開始監控」，背景執行緒會持續檢查並在觸發門檻時發 Telegram 通知
3. 頁面下方「狀態」區塊每 2 秒自動更新，可看到目前是否運行中、最近一次檢查結果、累計通知次數
4. 按「停止監控」即可暫停

## 注意事項

- 免費方案的 Space 閒置一段時間會自動休眠，休眠後背景監控也會停止；若要 24 小時不中斷運行，需要升級成 always-on 的付費方案，或另外設定保活機制（例如外部排程定時 ping Space）。
- 每次 Space 重建（例如改了程式碼重新 push）背景執行緒都會重置，需要重新按一次「開始監控」。
