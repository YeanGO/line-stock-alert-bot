# LINE Stock Alert Bot

FastAPI + LINE Messaging API 台股監控機器人。專案可在本機執行，使用 SQLite 儲存使用者、監控清單、全市場設定與通知紀錄，並透過 APScheduler 定期抓取 yfinance 資料判斷是否推播 LINE 訊息。

## 目前功能

- LINE Webhook：`POST /webhook`
- 健康檢查：`GET /health`
- 手動觸發一般監控：`POST /admin/run-monitor`
- 一般價格、漲跌幅、量能、均線突破追蹤
- 盤中動能追蹤
- 早盤急漲低量個股監控
- 早盤全市場掃描通知
- 個人聊天室與群組聊天室分開儲存、分開通知
- 同一目標、同一股票、同一天、同一 alert type 避免重複通知

## 本機啟動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

啟動後測試：

```text
http://127.0.0.1:8000/health
```

正常會回：

```json
{"status":"ok"}
```

## 環境變數

`.env` 由 `.env.example` 複製後填入 LINE 憑證。

```dotenv
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

DATABASE_URL=sqlite:///./stock_alert.db

MONITOR_INTERVAL_SECONDS=90
DEFAULT_COOLDOWN_MINUTES=20
DYNAMIC_COOLDOWN_MINUTES=5

SCAN_INTERVAL_SECONDS=180
BATCH_SIZE=80
MAX_SCAN_SECONDS=170
ALERT_GAIN_20M=0.08
ALERT_VOLUME_LIMIT_LOTS=2500
MORNING_ALERT_TYPE=MORNING_GAIN_LOW_VOLUME
MORNING_SCAN_START=09:00
MORNING_SCAN_END=13:30
MORNING_SCAN_WEEKDAYS=0,1,2,3,4

STOCK_SYMBOL_SUFFIX=.TW
APP_ENV=development
```

注意：`.env` 建議使用 UTF-8 without BOM。若 LINE Bot 沒回應，請先確認程式是否讀得到 `LINE_CHANNEL_ACCESS_TOKEN`。

## LINE 指令

輸入 `help` 可查看目前指令範例。

```text
追蹤 2330 高於 1000
追蹤 2330 低於 900
追蹤 2330 漲幅超過 3
追蹤 2330 跌幅超過 3
追蹤 2330 成交量放大 2
追蹤 2330 突破均線 MA20

監控早盤 2330 20 8 2500 週三週四週五 09:30-11:00
早盤清單
刪除早盤 2330
取消早盤 2330

開啟早盤全市場
關閉早盤全市場
設定早盤全市場條件 20 8 2500
設定早盤全市場時間 週三週四週五 09:30-11:00
早盤設定

查看追蹤
刪除 2330
狀態
help
```

數字股票代號會自動補上 `.TW`，例如 `2330` 會轉成 `2330.TW`。

## 一般追蹤

一般追蹤由 scheduler 每 `MONITOR_INTERVAL_SECONDS` 秒檢查一次，預設 90 秒。

支援條件：

- `高於`：股價大於等於目標價
- `低於`：股價小於等於目標價
- `漲幅超過`：日漲幅大於等於指定百分比
- `跌幅超過`：日跌幅小於等於指定百分比
- `成交量放大`：成交量大於等於 5 日均量乘上倍數
- `突破均線 MA5/MA10/MA20/MA60`

一般追蹤 cooldown 預設 20 分鐘。

## 盤中動能追蹤

程式仍支援動能追蹤指令，雖然預設 `help` 不再列出重複範例。

```text
動能追蹤 2330
動能追蹤 2330 8 2500 20 週四週五 09:00-10:30
```

格式：

```text
動能追蹤 股票代號 漲幅% 成交量張數 分鐘 星期 時間
```

預設值：

- 20 分鐘
- 漲幅 >= 8%
- 成交量 <= 2500 張
- 週四週五
- 09:00-10:30

動能追蹤 cooldown 預設 5 分鐘，並使用 condition-active 狀態避免條件持續成立時一直重複通知。

## 早盤個股監控

新增個股早盤監控：

```text
監控早盤 2330 20 8 2500 週三週四週五 09:30-11:00
```

格式：

```text
監控早盤 股票代號 分鐘 漲幅% 成交量張數 星期 時間
```

也支援舊的簡短格式：

```text
監控早盤 2330
監控早盤 2330 09:30-11:00
早盤急漲 2330
急漲低量 2330
```

目前早盤條件邏輯：

```text
最近 N 分鐘內任一分鐘到現在的最大漲幅 >= X%
且
最近 N 分鐘總成交量 <= Y 張
```

實作上：

```text
目前最新 Close
vs
最近 N 分鐘內最低 Close
```

漲幅公式：

```text
(目前最新 Close - 最近 N 分鐘內最低 Close) / 最近 N 分鐘內最低 Close
```

成交量：

```text
最近 N 根 1 分鐘 K 的 Volume 加總 / 1000
```

所以設定 `20 8 2500` 代表：

```text
最近 20 分鐘內最大漲幅 >= 8%
且最近 20 分鐘總成交量 <= 2500 張
```

查詢與刪除：

```text
早盤清單
取消早盤 2330
刪除早盤 2330
```

## 早盤全市場掃描

開啟全市場通知：

```text
開啟早盤全市場
```

關閉全市場通知：

```text
關閉早盤全市場
```

設定全市場條件：

```text
設定早盤全市場條件 20 8 2500
```

格式：

```text
設定早盤全市場條件 分鐘 漲幅% 成交量張數
```

設定全市場通知時間：

```text
設定早盤全市場時間 週三週四週五 09:30-11:00
```

查詢設定：

```text
早盤設定
```

全市場掃描流程：

1. 每 `SCAN_INTERVAL_SECONDS` 秒執行一次，預設 180 秒。
2. 每輪最多執行 `MAX_SCAN_SECONDS` 秒，預設 170 秒。
3. 先掃描早盤監控清單中的股票。
4. 再掃描 `data/twse_listed_symbols.txt` 中其餘不重複股票。
5. 若時間不足，本輪停止，下一輪重新從 watchlist 優先開始。

全市場股票清單目前來自：

```text
data/twse_listed_symbols.txt
```

預設檔案只放少量範例股票。若要真的掃全上市股票，請把完整上市股票代號放進這個檔案，一行一個，例如：

```text
2330.TW
2317.TW
2454.TW
```

## 通知與去重

早盤通知規則：

- 股票在某目標的早盤 watchlist 中：通知該目標，來源顯示「你的早盤監控清單」。
- 股票不在 watchlist 中，但目標有開啟早盤全市場：通知該目標，來源顯示「全市場掃描」。
- 同一目標、同一股票、同一天、同一 alert type 只通知一次。

早盤 alert type：

```text
MORNING_GAIN_LOW_VOLUME
```

## 個人與群組行為

所有監控與設定指令都支援個人聊天室與群組聊天室。

個人聊天室輸入：

```text
line_target_id = user_id
target_type = user
```

群組聊天室輸入：

```text
line_user_id = 發指令的人
line_target_id = group_id
target_type = group
created_by_user_id = 發指令的人
```

效果：

- 個人設定只通知個人。
- 群組設定只通知群組。
- 群組中的 `早盤清單`、`查看追蹤` 只看該群組的監控。
- 群組中的 `開啟早盤全市場` 會讓該群組接收全市場訊號，不會寫到發指令者的個人設定。

## LINE Developers 與 ngrok

本機啟動後可用 ngrok 暴露：

```powershell
ngrok http 8000
```

LINE Developers 後台 Webhook URL：

```text
https://your-ngrok-domain/webhook
```

請確認：

- Webhook 已啟用
- Channel access token 已填入 `.env`
- Channel secret 已填入 `.env`
- FastAPI server 已重啟並讀到最新 `.env`

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest
```

測試涵蓋：

- 指令解析
- LINE webhook / dev-command
- 個人與群組 target 分離
- rule engine
- 股票資料 service
- 早盤掃描與通知去重
- watchlist repository

