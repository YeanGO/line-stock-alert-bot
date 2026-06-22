# LINE Stock Alert Bot

FastAPI + LINE Messaging API 的台股監控 Bot，可在本機執行，使用 SQLite 儲存追蹤條件，並透過 APScheduler 定期檢查股價與早盤急漲低量條件。

## 功能

- LINE Webhook：`POST /webhook`
- 健康檢查：`GET /health`
- 手動執行一般監控：`POST /admin/run-monitor`
- 一般股價追蹤
- 早盤急漲低量個股監控
- 早盤全市場掃描通知
- 個人與群組分開儲存監控設定
- 同一目標、同一股票、同一天、同一 alert type 不重複通知

## 安裝與啟動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

健康檢查：

```text
http://127.0.0.1:8000/health
```

正常回覆：

```json
{"status":"ok"}
```

## 環境變數

`.env` 是目前本機實際使用的設定，`.env.example` 是範例檔。

```dotenv
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

DATABASE_URL=sqlite:///./stock_alert.db

MONITOR_INTERVAL_SECONDS=90
DEFAULT_COOLDOWN_MINUTES=20

SCAN_INTERVAL_SECONDS=180
BATCH_SIZE=80
MAX_SCAN_SECONDS=170
MORNING_ALERT_TYPE=MORNING_GAIN_LOW_VOLUME
MORNING_SCAN_START=09:00
MORNING_SCAN_END=13:30
MORNING_SCAN_WEEKDAYS=0,1,2,3,4

STOCK_SYMBOL_SUFFIX=.TW
APP_ENV=development
```

注意：`.env` 建議使用 UTF-8 without BOM。

## LINE 指令

輸入 `help` 會顯示目前支援的指令：

```text
追蹤 2330 高於 1000
追蹤 2330 低於 900
追蹤 2330 漲幅超過 3
追蹤 2330 跌幅超過 3
追蹤 2330 成交量放大 2
追蹤 2330 突破均線 MA20

監控早盤 2330 45 5 5000 週一週二 09:00-13:30
早盤清單
刪除早盤 2330

開啟早盤全市場
關閉早盤全市場
設定早盤全市場條件 45 5 5000
設定早盤全市場時間 週一週二 09:00-13:30
早盤設定

查看追蹤
刪除 2330
狀態
help
```

股票代號可輸入 `2330`，系統會自動轉成 `2330.TW`。

## 一般追蹤

一般追蹤由 `MONITOR_INTERVAL_SECONDS` 控制輪詢頻率，目前範例為 90 秒。

支援條件：

- `高於`：目前價格大於等於指定價格
- `低於`：目前價格小於等於指定價格
- `漲幅超過`：日漲幅大於等於指定百分比
- `跌幅超過`：日跌幅大於等於指定百分比
- `成交量放大`：目前成交量大於等於 5 日均量倍數
- `突破均線`：支援 `MA5`、`MA10`、`MA20`、`MA60`

一般追蹤 cooldown 使用 `DEFAULT_COOLDOWN_MINUTES`。

## 早盤個股監控

新增早盤監控必須完整輸入條件，不會套用預設值：

```text
監控早盤 股票代號 分鐘 漲幅% 成交量張數 星期 時間
```

範例：

```text
監控早盤 2330 45 5 5000 週一週二 09:00-13:30
```

代表：

```text
最近 45 分鐘內任一分鐘到現在，漲幅 >= 5%
最近 45 分鐘總成交量 <= 5000 張
只在週一、週二 09:00-13:30 監控
```

查詢與刪除：

```text
早盤清單
刪除早盤 2330
```

## 早盤條件邏輯

早盤急漲低量使用 Yahoo/yfinance 的 1 分 K 資料。

漲幅計算：

```text
目前最新 Close
vs
最近 N 分鐘內最低 Close
```

公式：

```text
(目前最新 Close - 最近 N 分鐘內最低 Close) / 最近 N 分鐘內最低 Close
```

成交量計算：

```text
最近 N 根 1 分 K Volume 加總 / 1000
```

所以 `45 5 5000` 代表：

```text
最近 45 分鐘內任一分鐘到現在，漲幅 >= 5%
最近 45 分鐘總成交量 <= 5000 張
```

開盤初期資料未滿 45 分鐘時，會先用目前已有的 1 分 K 資料判斷；資料滿 45 分鐘後，才固定使用最近 45 分鐘滑動視窗。

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
設定早盤全市場條件 45 5 5000
```

格式：

```text
設定早盤全市場條件 分鐘 漲幅% 成交量張數
```

設定全市場時間：

```text
設定早盤全市場時間 週一週二 09:00-13:30
```

查詢設定：

```text
早盤設定
```

注意：早盤全市場沒有預設條件。只輸入 `開啟早盤全市場` 但尚未設定時間或條件時，`早盤設定` 會顯示未設定，掃描時也不會使用任何隱含條件。

## 掃描流程

早盤掃描由 `SCAN_INTERVAL_SECONDS` 控制，目前範例為 180 秒。

每輪流程：

1. 先掃描使用者或群組早盤清單中的股票。
2. 再掃描 `data/twse_listed_symbols.txt` 內的上市股票。
3. 若單輪掃描達到 `MAX_SCAN_SECONDS`，本輪停止，下一輪照常重新開始。
4. 通知時以 watchlist 目標優先；非 watchlist 命中的股票會通知有開啟早盤全市場且設定完整的目標。

全市場股票清單：

```text
data/twse_listed_symbols.txt
```

每行一個股票代號，例如：

```text
2330.TW
2317.TW
2454.TW
```

## 通知規則

早盤 alert type：

```text
MORNING_GAIN_LOW_VOLUME
```

重複通知規則：

```text
同一目標 + 同一股票 + 同一天 + 同一 alert type，只通知一次
```

通知來源：

- 股票在該目標的早盤清單中：來源顯示「你的早盤監控清單」
- 股票不在該目標清單中，但該目標有開啟早盤全市場且設定完整：來源顯示「全市場掃描」

## 個人與群組

個人聊天室：

```text
line_target_id = user_id
target_type = user
```

群組聊天室：

```text
line_user_id = 發送指令者
line_target_id = group_id
target_type = group
created_by_user_id = 發送指令者
```

行為：

- 個人設定只通知個人。
- 群組設定只通知群組。
- 群組中的 `早盤清單`、`查看追蹤` 只看該群組的監控。
- 群組中的 `開啟早盤全市場` 會讓該群組接收全市場訊號，不會寫到發指令者的個人設定。

## LINE Developers 與 ngrok

本機測試可使用 ngrok：

```powershell
ngrok http 8000
```

LINE Developers Webhook URL：

```text
https://your-ngrok-domain/webhook
```

請確認：

- Webhook 已啟用
- Channel access token 已寫入 `.env`
- Channel secret 已寫入 `.env`
- FastAPI server 已重新啟動並讀到最新 `.env`

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest
```

測試涵蓋：

- 指令解析
- LINE webhook / dev-command
- 個人與群組 target 分離
- 一般 rule engine
- 股票資料 service
- 早盤掃描與通知去重
- watchlist repository
