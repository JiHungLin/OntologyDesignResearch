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
8. **流程修改與 HR 的切片設計分開 session**：同一個 session 同時改流程、做切片、做 git 操作，經過摘要壓縮後容易憑記憶寫。HR 那邊建議一個 session 做一步（工具包 `CLAUDE.md` 開頭）。

## 文件分工

正本在根目錄；衝突時：內容以精簡版為準，格式以輸入輸出規範為準，平台決定以平台架構約定為準。

| 文件 | 內容 |
|---|---|
| `團隊開發流程_精簡版.md` | Domain 設計規範（流程正式依據）：規劃、六步、回頭、兩個循環 |
| `Domain設計輸入輸出規範.md` | 每份交付物的格式、編號、標記、檢查、交接 |
| `平台架構約定.md` | 平台層級決定一次的事（P1～P13） |
| `本體論設計指南.md` | 詳細手冊；開頭有修訂紀錄（目前到 #46） |
| `Domain設計心法.md`、`Domain設計心法_精華版.md` | 每個階段的目的 |
| `團隊開發流程.html`、`Domain設計心法.html`、`Domain設計心法_精華版.html` | 三個網頁的原始檔 |
| `團隊開發流程_對抗性審查.md` | 所有流程修改的理由（每次改流程都要記一筆） |
| `Entity判斷問題驗證.md` | 第 ② 步六問的案例驗證 |
| `Sean三層架構與八步八元素對照.md`、`DoubleDiamond研究.md` | Sean 方法的研究 |
| `AI協作方式分析報告.md` | 與 AI 協作方式的分析 |

**修改流程時**：
0. 先用精簡版 0.10 的四個問題判斷這個提議（新增、修改或移除）：解決什麼問題、放在哪裡、產出和完成標準、成本。不論提議來自使用者、主管、文章或 AI，都要能回答；結論（採納／先試用／歸到別處／暫不採納）記在對抗性審查紀錄。
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
| 流程演進判斷（0.10 四個問題＋10/07 會議提案的建議結論） | https://claude.ai/artifact/GeQFc5kyihoQcnvCPEvR9G | `流程演進判斷.html` |
| 第二條切片成效分析（hire-employee vs annual-leave-grant，10/07 決議的成效） | https://claude.ai/artifact/MTv1Wk1tFAwq47d5vxtkXk | `流程成效分析.html`（正本 `20261021流程成效分析.md`） |
| 人資 Domain 設計計畫（一頁投影片，給 Sean） | https://claude.ai/artifact/YAC1AoDadBYi6DjF7sUmea | 不在 repo，需要時用 Artifact read 取回 |
| 人資計畫海報（Double Diamond，交付到 ⑤ 含紙上驗證） | https://claude.ai/artifact/1vTGniL2vFGFZpkJXkzNgB | 同上 |
| AI 協作方式海報 | https://claude.ai/artifact/LcPWoaxiroNAZmLtSWmeJS | 同上 |

## 進度紀錄

只寫做了什麼與 commit，不寫「尚未 push」「尚未同步」這類會變的狀態（以 git 為準，要回報時再查）。

- 第 ② 步 Entity 判斷剛由三問改為六問（分流、身分、被指到、推導、持續、不能合併），新增平台約定 P11（識別範圍、資料性質要不要標、資料存放，都由平台決定一次）。工具包已更新到 HR repo（commit `2dd2880`）。
- HR repo 的 `hire-employee` 第 ② 步已用六問重跑（`ee54dd2`），並依使用者審查意見修改（`5f18e64`、`c97a3cc`、`17edb83`，使用者在本 repo 的 session 中要求直接在 HR repo 處理）：新增切片 `personnel-record`（獎懲、傷病，地圖 D-32）；WarningOverride 補撤回者與時間；地圖 D-33——判定以「有沒有對應的規則版本」為界，既有員工加入系統時事實照填，日後補進舊法規即可判定；使用者原則「只記錄系統中的登記與變化，系統外或使用前的狀態先不管」。
- 2026-10-07 依使用者本機審查補三個流程缺口：新需求要擴充現有切片還是開新切片（精簡版 0.9）；`core/` 項目新增「已取代」「已停用」狀態；詞彙對照表狀態欄的值與一致性。HR repo 的 `hire-employee` 第 ② 步之後已凍結（`08edcc4`）。這次的工具包更新已同步到 HR repo（分支 `claude/epic-hopper-mi7xcv`）。
- 2026-10-07 規劃文件的變更紀錄改為獨立的 `slices/CHANGELOG.md`（PLAN.md、ENTITY_SKETCH.md 不再放紀錄；`domain-plan` 會提議搬移舊紀錄）。這次已同步到 HR repo（同上分支）。
- 2026-10-14 CHANGELOG 紀錄規則改為：第一次凍結前，送審後只逐筆記改變設計的修改，整理性修改在凍結那一筆總結（依據 HR `hire-employee` ① 有 19 筆小修改、③ 漏記刪除核准流程）。已同步到 HR repo（`6e32697`）。
- 2026-10-14 檢查工具改版（依 HR 第 ④ 步整理的問題，兩批）：`check.py` 沒檢查的不再顯示通過；規則用 `` `Entity.attribute` ``、`[解讀: …]`、`[已取消: …]`，「決定與理由」加「提出／同意」；新增 `tools/md2build.py`（轉 YAML）、`tools/lint.py`（引用檢查）、`tools/tests/`（23 項）。同日決定規則不登錄在詞彙對照表（規則只有編號，規則表就是登錄處）。
- 2026-10-14 依 HR `hire-employee` 實作（MongoDB＋FastAPI，branch `impl/hire-employee`，未 commit）發現的問題補流程：④ 判定類規則寫出每一種結果；⑤ 對照表加第六區「Use Case 走一遍」、`api.yaml` 寫到欄位層級；⑥ 實作時發現的設計問題列在 `signoff.md`、不在程式裡自己補；實作程式碼由人決定放哪裡與 commit；回頭規則不限專家意見，`domain-change` 接受實作缺口（記在 `signoff.md`，不用寫驗收問題），回歸範圍加上實作程式碼與 ④ → ⑤。
- 2026-10-16 依 HR `hire-employee` 實作第二、三輪（#13～#20）補流程：挑錯新增「實作者」角度（③④⑤）；《平台架構約定》新增 P12 模型演進與既有資料（新屬性在舊資料上是未知、規則遇到未知判資料不足、補值與遷移留事件），④ 判定類規則寫出資料未知時的結果，⑤ 對照表第四區加「既有資料」，CR 範本的舊資料欄照 P12。
- 2026-10-19 依 HR `hire-employee` 的完成標準反向檢查（132 個反例的來源：挑錯 107、實作 24、人審查 1）：①～⑤ 完成標準標類別（關鍵決定 15／修正線索／品質檢查），68 條減為 65 條；檢查會改看「審查重點」＋抽查（⑥ 照舊）；回頭修改只審差異、多步一起凍結、CHANGELOG 可合寫；0.10 新增「先試用中的項目」表（實作者角度、P12 的 Domain 部分改列先試用）；`build_kit.py` 從行尾〔…〕標記產生「類」欄與審查重點表。凍結腳本（檔頭、`core/` 同步、數字）暫緩。分析文件在 Claude Doc「完成標準反向檢查」。
- 2026-10-19 10/07 會議設計方向逐項決定（《20261007設計方向_對照現行流程》）：④ 參數表先試用、決策表採納為寫法；《平台架構約定》新增 P13 非功能需求；整體流程圖、BRD 指標暫緩，AI 出題併入審查重點。決議紀錄見《20261007設計方向_決議》；已同步到 HR repo（fa38b98）。
- 2026-10-19 `lint.py` 新增「格式」檢查：`md2build.py` 看不懂的列逐條列出、算進紅燈（原本只印一行「注意」，HR `annual-leave-grant` ① 檢查紀錄表多一欄時被漏看）。已同步到 HR repo（9aa33f5）。
- 2026-10-19 審查重點與「決定與理由」用白話寫法條（寫法律名稱與條號，附一句白話；只寫 §nn 或證據編號不算）：精簡版 0.2、`domain-step`。依據：使用者審查 HR `annual-leave-grant` ① 時看不懂「§10」。已同步到 HR repo（fc3bca5）。
- 2026-10-21 HR `annual-leave-grant` 做完 ⑤，依《流程待處理清單》18 項一次評估、一次修改（使用者逐項同意）：斷言歸屬與上游有無要寫出查到的位置；法條原文用「」、推論標 `[解讀]`；使用者在選項中的決定不算客戶端來源、說出的內容才存成 `inputs/`；審查重點打勾即同意 D-nn；第一次凍結前直接改審查重點表；EQ「影響」依檔案分組並由 lint 比對；core 的 Q、UC、US-D 加前綴；research「用在」只可追加；黃金案例沒挑的候選標「不採用」、所有編號不刪除；範本佔位符統一為 `{{切片}}`；`lint.py` 新增 9 類檢查（含不屬於任何表格的列）、新增 `table.py`，測試 35 項（a6108d8）。已同步到 HR repo（9043475）。
- 2026-10-21 先試用項目到期判斷（使用者決定）：回頭修改只審差異、多步一起凍結改為採納；審查重點＋抽查繼續試用到 `annual-leave-grant` 實作之後（使用者：看的東西少了，但仍容易不看細節直接打勾——這是 10/07「AI 出題」的加入條件，這次先不加）。已同步到 HR repo（8b5f2bd）。
- 2026-10-21 三個先試用項目實作後判斷（使用者「照建議做」，依《20261021流程成效分析》第七節）：參數表採納，補可選做法寫代碼、表格型參數寫欄位、⑤「參數放在哪裡」（`lint.py` 新增檢查）；挑錯的實作者角度延長到第三條切片，反例來源改記角度；審查重點改做法再試一條——沒有依據的 AI 決定寫成問題、審查者用一句話回答，人的意見記成 X-nn（10/07「AI 出題」加入）。手冊修訂 #46。
- 可回流到流程的觀察（使用者尚未要求修改）：六問第 0 問「發生的事之後還有狀態要追蹤 → 當作東西」讓試跑 AI 在 WarningOverride 來回（事件 ↔ Entity），使用者也誤以為違反「狀態不是 Entity」；判斷的關鍵其實是第 3 問（無法推導）與第 5 問（不能併成對象的狀態）。
- 曾提議但使用者還沒要求的：海報加上 Double Diamond 的來源註記；把 `Sean三層架構與八步八元素對照.md` 做成網頁。
