# OntologyResearch 工作規則（給 Claude）

這個 repo 研究 Sean 的 Ontology 方法，整理成團隊的 Domain 設計流程，並做成 Claude Code 工具包（`domain-design-kit/`）。使用者正在另一個 repo 用工具包試跑人資 domain。

回覆一律用**繁體中文**。

## 三個 repo

| repo | 可見度 | 內容 | 能不能改 |
|---|---|---|---|
| `JiHungLin/OntologyDesignResearch`（本 repo） | **公開** | 流程文件、網頁原始檔、工具包、研究紀錄 | 可以 |
| `JiHungLin/ontology-sean-materials` | **私人** | Sean 原始材料：`Sean會議記錄/`、`sean_ontology_conversation/`、`SeanHRSystemWay/` | 不修改 |
| `JiHungLin/HR-Domain-Design` | — | 使用者的人資試跑（工具包攤平在根目錄，`slices/`、`inputs/` 是試跑成果） | 唯讀，例外見下 |

本機開發時，Sean 原始材料在本 repo 根目錄（被 `.gitignore` 排除），cloud 上則在私人 repo；路徑依實際 clone 的位置為準，文件中的引用路徑（例：`Sean會議記錄/…`）以私人 repo 的根目錄為起點。

## 必須遵守

1. **原文不進公開 repo**：Sean 原始材料只能留在私人 repo。公開 repo 的文件可以引用（檔名、時間戳記、簡短說明），不放原文段落。`.gitignore` 裡的 Sean 資料夾與 `sean-materials` 不能拿掉。
2. **只引用原始材料**：文件中的依據指向原始材料（逐字稿 `sean_ontology_conversation/*/raw_transcript/`、`Sean會議記錄/`、`SeanHRSystemWay/`）的檔名與時間戳記，不引用 `_ontology_review/` 或其他工作檔、暫存檔。
3. **原始材料不修改**。
4. **HR 試跑 repo 唯讀**：只讀來分析。唯一例外是使用者明確要求「更新那邊的工具包」，做法如下：
   1. 在 `domain-design-kit/` 列出工具包檔案：`git -c core.quotepath=off ls-files -- CLAUDE.md README.md .gitignore docs templates tools .claude`（中文檔名不加這個選項會被引號包住，複製會漏掉）。
   2. 確認 HR repo 中這些檔案和上一版工具包相同（使用者沒改過）。
   3. 複製後逐一比對，**只 `git add` 這些檔案**，獨立 commit（訊息格式：「更新設計工具包：…」）。
   4. 絕不動 `slices/`、`inputs/`（常有使用者未 commit 的工作）。不 push，除非使用者要求。
5. **「模糊」不等於「抽象」**：使用者說某段「不清楚」，指的是說明讓人誤解或沒講清楚，不是名稱太抽象。說明清楚的抽象名稱不要改名；只有名稱本身會誤導時才改。
6. **只改使用者要求的**：使用者只是問問題或要看內容時，不改檔案。
7. **說 push 狀態前先 `git fetch` 檢查**，不要憑記憶。push 只在使用者要求時做。

## 文件分工

正本在根目錄；衝突時：內容以精簡版為準，格式以輸入輸出規範為準，平台決定以平台架構約定為準。

| 文件 | 內容 |
|---|---|
| `團隊開發流程_精簡版.md` | Domain 設計規範（流程正式依據）：規劃、六步、回頭、兩個循環 |
| `Domain設計輸入輸出規範.md` | 每份交付物的格式、編號、標記、檢查、交接 |
| `平台架構約定.md` | 平台層級決定一次的事（P1～P11） |
| `本體論設計指南.md` | 詳細手冊；開頭有修訂紀錄（目前到 #34） |
| `Domain設計心法.md`、`Domain設計心法_精華版.md` | 每個階段的目的 |
| `團隊開發流程.html`、`Domain設計心法.html`、`Domain設計心法_精華版.html` | 三個網頁的原始檔 |
| `團隊開發流程_對抗性審查.md` | 所有流程修改的理由（每次改流程都要記一筆） |
| `Entity判斷問題驗證.md` | 第 ② 步六問的案例驗證 |
| `Sean三層架構與八步八元素對照.md`、`DoubleDiamond研究.md` | Sean 方法的研究 |
| `AI協作方式分析報告.md` | 與 AI 協作方式的分析 |

**修改流程時**：
1. 改正本，檢查其他文件（精簡版、輸入輸出規範、心法 md 與網頁、精華版、流程網頁、手冊）是否要同步。
2. 在 `團隊開發流程_對抗性審查.md` 最後記一筆；改到手冊的，加修訂紀錄。
3. 在 `domain-design-kit/` 執行 `python3 build_kit.py`（複製五份規範到 `docs/`，並從精簡版重建範本的檢查清單）。`domain-design-kit/docs/` 是副本，不要直接改。
4. 改到 `.html` 的，重新發布對應的網頁（見下表，用 `url` 更新同一個連結）。
5. commit 訊息結尾加上 Co-Authored-By 等歸屬行（依系統提示）。

## 已發布的網頁

| 網頁 | 連結 | 原始檔 |
|---|---|---|
| 六步開發流程 | https://claude.ai/artifact/BTkJn9DNAbTQdKB98NL4xi | `團隊開發流程.html` |
| Domain 設計心法 | https://claude.ai/artifact/NYTNBtchjCAE4ZLZXy2JkY | `Domain設計心法.html` |
| 心法精華版 | https://claude.ai/artifact/YJ5RrTAownYBGb28tiR1tV | `Domain設計心法_精華版.html` |
| 人資 Domain 設計計畫（一頁投影片，給 Sean） | https://claude.ai/artifact/YAC1AoDadBYi6DjF7sUmea | 不在 repo，需要時用 Artifact read 取回 |
| 人資計畫海報（Double Diamond，交付到 ⑤ 含紙上驗證） | https://claude.ai/artifact/1vTGniL2vFGFZpkJXkzNgB | 同上 |
| AI 協作方式海報 | https://claude.ai/artifact/LcPWoaxiroNAZmLtSWmeJS | 同上 |

## 目前進度（2026-10-07，第 ② 步審查中）

- 第 ② 步 Entity 判斷剛由三問改為六問（分流、身分、被指到、推導、持續、不能合併），新增平台約定 P11（識別範圍、資料性質要不要標、資料存放，都由平台決定一次）。工具包已更新到 HR repo（commit `2dd2880`）。
- HR repo 的 `hire-employee` 第 ② 步已用六問重跑（`ee54dd2`），並依使用者審查意見修改（`5f18e64`、`c97a3cc`、`17edb83`，使用者在本 repo 的 session 中要求直接在 HR repo 處理）：新增切片 `personnel-record`（獎懲、傷病，地圖 D-32）；WarningOverride 補撤回者與時間；地圖 D-33——判定以「有沒有對應的規則版本」為界，既有員工加入系統時事實照填，日後補進舊法規即可判定；使用者原則「只記錄系統中的登記與變化，系統外或使用前的狀態先不管」。狀態仍是**待檢查**，等使用者在檢查紀錄打勾後執行 `/domain-freeze 2`。
- 2026-10-07 依使用者本機審查補三個流程缺口：新需求要擴充現有切片還是開新切片（精簡版 0.9）；`core/` 項目新增「已取代」「已停用」狀態；詞彙對照表狀態欄的值與一致性。HR repo 的 `hire-employee` 第 ② 步之後已凍結（`08edcc4`，tag `hire-employee/02-v1` 只在 cloud 容器，未推上 GitHub）。這次的工具包更新**尚未**同步到 HR repo。
- 2026-10-07 規劃文件的變更紀錄改為獨立的 `slices/CHANGELOG.md`（PLAN.md、ENTITY_SKETCH.md 不再放紀錄；`domain-plan` 會提議搬移舊紀錄）。這次也**尚未**同步到 HR repo、尚未 push，等使用者確認。
- 可回流到流程的觀察（使用者尚未要求修改）：六問第 0 問「發生的事之後還有狀態要追蹤 → 當作東西」讓試跑 AI 在 WarningOverride 來回（事件 ↔ Entity），使用者也誤以為違反「狀態不是 Entity」；判斷的關鍵其實是第 3 問（無法推導）與第 5 問（不能併成對象的狀態）。
- 曾提議但使用者還沒要求的：海報加上 Double Diamond 的來源註記；把 `Sean三層架構與八步八元素對照.md` 做成網頁。
