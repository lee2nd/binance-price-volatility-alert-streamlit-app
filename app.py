"""
Binance Price Alert - Streamlit Community Cloud 版本 (Binance.US 現貨)

功能：
- 幣種 / 漲跌幅門檻 / 檢查間隔可在網頁上設定
- Telegram Bot Token / Chat ID 從 st.secrets 讀取（App 的 Settings -> Secrets 設定）
- 開始 / 停止按鈕控制背景監控執行緒
- 即時顯示運行狀態、最近一次檢查結果、累計通知次數

資料來源改打 Binance.US（現貨）而不是 Binance 主站的 Futures：
Binance 主站對美國地區 IP 有存取限制，Streamlit Community Cloud 的伺服器在美國會被擋；
Binance.US 是給美國用戶用的合規站台，不會擋美國 IP，但只有現貨、沒有永續合約/Futures，
可選幣種也比主站少。

部署到 Streamlit Community Cloud (share.streamlit.io)：
1. 把 app.py、requirements.txt push 到 GitHub repo（可以放進現有的
   frank-trading-toolkit，或另開一個 repo 都可以）
2. https://share.streamlit.io -> New app，選這個 repo / branch，
   Main file path 填 app.py（如果放在子資料夾，例如 alert/app.py，這裡就填完整路徑）
3. Deploy 之前或之後，進 App 右下角 ⋮ -> Settings -> Secrets，
   用 TOML 格式貼上：
     TELEGRAM_BOT_TOKEN = "你的 token"
     TELEGRAM_CHAT_ID = "你的 chat id"
   存檔後選 Reboot app 讓設定生效
"""

import os
import threading
import time
from datetime import datetime

import requests
import streamlit as st
from binance.client import Client

# ========== 預設值 ==========
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
DEFAULT_THRESHOLD = 0.35
DEFAULT_INTERVAL = 3
NOTIFY_COOLDOWN_SECONDS = 1200
RETRY_DELAY_SECONDS = 3
DEFAULT_KLINE_LABEL = "3分鐘"

# K 棒週期選項：顯示用文字 -> Client.KLINE_INTERVAL_* 常數
KLINE_INTERVAL_OPTIONS = {
    "1分鐘": Client.KLINE_INTERVAL_1MINUTE,
    "3分鐘": Client.KLINE_INTERVAL_3MINUTE,
    "5分鐘": Client.KLINE_INTERVAL_5MINUTE,
    "15分鐘": Client.KLINE_INTERVAL_15MINUTE,
    "30分鐘": Client.KLINE_INTERVAL_30MINUTE,
    "1小時": Client.KLINE_INTERVAL_1HOUR,
    "2小時": Client.KLINE_INTERVAL_2HOUR,
    "4小時": Client.KLINE_INTERVAL_4HOUR,
    "6小時": Client.KLINE_INTERVAL_6HOUR,
    "8小時": Client.KLINE_INTERVAL_8HOUR,
    "12小時": Client.KLINE_INTERVAL_12HOUR,
    "1天": Client.KLINE_INTERVAL_1DAY,
}

st.set_page_config(page_title="Binance Price Alert", page_icon="🚨", layout="centered")

# Telegram Token / Chat ID：從 Streamlit Community Cloud 的 Secrets 讀取，不寫死在程式碼裡
# (App 設定 -> Settings -> Secrets，用 TOML 格式填 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)
def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, "")


TELEGRAM_BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get_secret("TELEGRAM_CHAT_ID")


def get_binance_client() -> Client:
    """建立打 Binance.US 的 Client（tld='us' 會改連 api.binance.us），
    不會被美國地區 IP 擋，也就不需要 proxy 了"""
    return Client(tld="us")


def send_telegram_notify(bot_token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": f"🚨 Binance Price Notify\n{message}"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"Telegram notify failed: {error}")
        return False


def check_price(client: Client, symbol: str, interval: str, threshold_percent: float):
    """回傳 (顯示用 dict, 若觸發門檻則為警示訊息字串否則 None)。用 Binance.US 現貨 K 棒"""
    klines = client.get_klines(symbol=symbol, interval=interval, limit=2)
    prev_close = float(klines[0][4])
    curr_close = float(klines[-1][4])
    change_percent = round(((curr_close - prev_close) / prev_close) * 100, 3)
    triggered = abs(change_percent) > threshold_percent
    arrow = "⬇" if change_percent < 0 else "⬆"
    message = None
    if triggered:
        message = f"{symbol[:-4]} {arrow} {abs(change_percent)}% {interval} [{prev_close}⮕{curr_close}]"
    row = {
        "幣種": symbol[:-4],
        "漲跌幅 %": change_percent,
        "前收": prev_close,
        "現價": curr_close,
        "觸發": "🔥" if triggered else "",
    }
    return row, message


class AlertRunner:
    """背景執行緒控制器。用 st.cache_resource 讓所有 rerun / session 共用同一個 instance，
    這樣按下開始後，就算網頁重新整理，背景執行緒也不會被中斷或重複啟動。"""

    def __init__(self):
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.status = {
            "running": False,
            "started_at": None,
            "last_check_at": None,
            "last_results": [],
            "notify_count": 0,
            "last_notify_at": None,
            "error": None,
        }

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, symbols, threshold, interval_seconds, kline_interval, bot_token, chat_id) -> bool:
        if self.is_running():
            return False
        self.stop_event.clear()
        with self.lock:
            self.status.update(
                running=True,
                started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error=None,
            )
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(symbols, threshold, interval_seconds, kline_interval, bot_token, chat_id),
            daemon=True,
        )
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()
        with self.lock:
            self.status["running"] = False

    def _sleep_interruptible(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds and not self.stop_event.is_set():
            step = min(1.0, seconds - elapsed)
            time.sleep(step)
            elapsed += step

    def _run_loop(self, symbols, threshold, interval_seconds, kline_interval, bot_token, chat_id) -> None:
        client = get_binance_client()
        while not self.stop_event.is_set():
            try:
                results = []
                notify_this_round = 0
                for symbol in symbols:
                    if self.stop_event.is_set():
                        break
                    row, message = check_price(client, symbol, kline_interval, threshold)
                    results.append(row)
                    if message and send_telegram_notify(bot_token, chat_id, message):
                        notify_this_round += 1
                with self.lock:
                    self.status["last_check_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.status["last_results"] = results
                    self.status["error"] = None
                    if notify_this_round:
                        self.status["notify_count"] += notify_this_round
                        self.status["last_notify_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._sleep_interruptible(NOTIFY_COOLDOWN_SECONDS if notify_this_round else interval_seconds)
            except Exception as error:  # noqa: BLE001
                with self.lock:
                    self.status["error"] = str(error)
                self._sleep_interruptible(RETRY_DELAY_SECONDS)
        with self.lock:
            self.status["running"] = False


@st.cache_resource
def get_runner() -> AlertRunner:
    return AlertRunner()


@st.cache_data(ttl=3600, show_spinner="正在取得 Binance.US 幣種列表...")
def fetch_spot_symbols() -> list[str]:
    try:
        client = get_binance_client()
        info = client.get_exchange_info()
        symbols = sorted(
            s["symbol"]
            for s in info["symbols"]
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
        )
        return symbols or DEFAULT_SYMBOLS
    except Exception as error:  # noqa: BLE001
        st.warning(f"取得幣種清單失敗，改用預設清單。原因：{error}")
        return DEFAULT_SYMBOLS


runner = get_runner()

# ========== UI ==========
st.title("🚨 Binance Price Alert")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    st.error(
        "尚未偵測到 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID。\n\n"
        "請到 Streamlit Community Cloud 的 App 右下角 ⋮ → Settings → Secrets 新增後 Reboot app。"
    )

all_symbols = fetch_spot_symbols()
is_running = runner.is_running()

st.subheader("參數設定")
symbols = st.multiselect(
    "監控幣種",
    options=all_symbols,
    default=[s for s in DEFAULT_SYMBOLS if s in all_symbols] or all_symbols[:3],
    disabled=is_running,
    key="symbols_ms",
)
threshold = st.number_input(
    "漲跌幅門檻 DROP_THRESHOLD_PERCENT (%)",
    min_value=0.01,
    max_value=20.0,
    value=DEFAULT_THRESHOLD,
    step=0.05,
    format="%.2f",
    disabled=is_running,
    key="threshold_input",
)
interval = st.number_input(
    "檢查間隔 CHECK_INTERVAL_SECONDS (秒)",
    min_value=1,
    max_value=3600,
    value=DEFAULT_INTERVAL,
    step=1,
    disabled=is_running,
    key="interval_input",
)
kline_label = st.selectbox(
    "K 棒週期 KLINE_INTERVAL",
    options=list(KLINE_INTERVAL_OPTIONS.keys()),
    index=list(KLINE_INTERVAL_OPTIONS.keys()).index(DEFAULT_KLINE_LABEL),
    disabled=is_running,
    key="kline_interval_select",
    help="用哪一根 K 棒的漲跌幅去跟門檻比較，例如選 3 分鐘就是比較最近兩根 3 分鐘 K 棒的收盤價",
)
kline_interval = KLINE_INTERVAL_OPTIONS[kline_label]
if is_running:
    st.caption("⚠️ 運行中無法修改參數，請先按停止")

st.subheader("控制")
col1, col2 = st.columns(2)
with col1:
    start_clicked = st.button("▶️ 開始監控", width="stretch", disabled=is_running, type="primary")
with col2:
    stop_clicked = st.button("⏹️ 停止監控", width="stretch", disabled=not is_running)

if start_clicked:
    if not symbols:
        st.error("至少要選一個幣種")
    elif not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        st.error("缺少 Telegram Token / Chat ID，無法啟動")
    else:
        runner.start(symbols, threshold, int(interval), kline_interval, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        st.rerun()

if stop_clicked:
    runner.stop()
    st.rerun()

st.subheader("狀態")
status = runner.status
running_now = runner.is_running()
st.markdown(f"**{'🟢 運行中' if running_now else '🔴 已停止'}**")

meta_col1, meta_col2 = st.columns(2)
with meta_col1:
    st.caption("啟動時間")
    st.write(status["started_at"] or "-")
with meta_col2:
    st.caption("最近檢查")
    st.write(status["last_check_at"] or "-")
st.metric("累計通知次數", status["notify_count"])

if status["last_notify_at"]:
    st.caption(f"最近一次通知：{status['last_notify_at']}")

if status["error"]:
    st.warning(f"最近一次錯誤：{status['error']}（會自動重試，不影響整體運行）")

if status["last_results"]:
    st.dataframe(status["last_results"], width="stretch", hide_index=True)
else:
    st.caption("尚無檢查紀錄")

# 運行中時每 2 秒自動刷新一次畫面，讓狀態即時更新
if running_now:
    time.sleep(2)
    st.rerun()
