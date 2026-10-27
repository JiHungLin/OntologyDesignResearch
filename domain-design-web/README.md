# Domain 設計流程網頁

把 Domain 設計流程中「人要和 AI 互動」的地方做成網頁，降低在 terminal 與編輯器之間切換的成本，並讓人一眼看出這輪要做什麼。設計與盤點見 [`互動元件盤點.md`](互動元件盤點.md)。

**目前是第一版：只做審查。** 讀寫切片 repo 的審查頁（`slices/<切片>/reviews/*.md`），以及透過 AI session 交給 AI 處理。

## 依賴版本

開發與測試時實際使用的版本（2026-10-27）：

| 依賴 | 版本 | 用途 |
|---|---|---|
| Python | 3.10.12 | 後端 |
| FastAPI | 0.116.1 | API 與靜態檔 |
| Starlette | 0.47.2 | FastAPI 的底層 |
| Uvicorn | 0.35.0 | 啟動伺服器 |
| Pydantic | 2.11.7 | 請求格式 |
| Claude Code（`claude` CLI） | 2.1.311 | 執行工具包的 skills；用到 `-p`、`--session-id`、`--resume`、`-n`、`--output-format stream-json --verbose` |
| 工具包 `tools/md2build.py` | 切片 repo 裡的那一份 | 切表格欄位（和 `lint.py`、`table.py` 同一個方式）；切片 repo 沒有時用本 repo 的 `domain-design-kit/tools/` |
| pytest | 6.2.5 | 測試 |
| httpx | 0.27.0 | 測試（FastAPI TestClient） |
| 瀏覽器 | Chrome 系列或 Firefox 的近期版本 | 前端只用原生 JavaScript，不載入外部程式庫 |

安裝：`pip install -r requirements.txt`（版本固定在上表）。

## 使用

```bash
python3 server.py --repo <切片 repo 的路徑>    # 例：~/Projects/HR-Domain-Desing
# 打開 http://127.0.0.1:8765/
```

- 只綁 `127.0.0.1`，單人在本機使用。
- 切片 repo 的 `.gitignore` 要加一行 `.domain-web/`（AI session 登記表放在這裡，不是設計內容）；沒加時網頁左上會提醒。

## 畫面

| 區域 | 內容 |
|---|---|
| 左：切片與審查頁 | 每條切片的審查頁，數字是還沒作答的項目（題目＋確認列＋抽查＋結論） |
| 中：審查頁 | 分頁：要你回答（一次一題，點 A／B 或寫一句）、要你確認（打 ✓ 或寫意見）、黃金案例（第一版只顯示）、抽查、結論與交給 AI |
| 右：查閱檔案 | 點任何「檔名:行號」就在這裡打開，標出那一行 |
| 下：AI 對話 | 這條切片使用中的 session；平常收合 |

網址會記住審查頁與分頁（`#<審查頁路徑>@<分頁>`），重新整理後停在同一處。

## 寫回審查頁的方式

- `.md` 是正本，網頁只改人要填的地方：選擇題的「你的回答」、確認列的「確認」、抽查表、結論表。其他行不動（測試確認重寫後檔案逐字相同）。
- 每次寫入都帶著打開時的檔案摘要；檔案在那之後被改過（例：AI 正在修改）就拒絕寫入，請人重新載入。

## AI session

設計見《互動元件盤點》第五節。重點：

- 記憶在檔案，不在 session：網頁的狀態一律從 `.md` 算出。
- 一條切片同一時間一個使用中的 session，登記在 `<切片 repo>/.domain-web/sessions.json`。第一次用 `--session-id` 建立，之後用 `--resume`；在 terminal 可以 `claude --resume <id>` 接著做。
- 沒有 session、session 的用途和目前的審查頁不同、或經過摘要壓縮時，網頁用選擇題問要不要開新的；新 session 的交接提示由檔案產生（CHANGELOG、審查頁、未回覆的 EQ），送出前可以改。
- `-p` 不能互動核准權限：被擋下的動作會顯示在 AI 對話中，請到 terminal 用 `claude --resume <id>` 處理。

## 測試

```bash
python3 -m pytest tests -q
```

用 `tests/fixture/` 的假資料（不含任何真實切片內容）。

## 還沒做

- 黃金案例試算（C5）、專家問題（C6）、中途停止點（C7）、編號跳轉（C8 的 D-nn、X-nn 等）、完整的狀態總覽（C9）。
- 網頁上核准權限。
