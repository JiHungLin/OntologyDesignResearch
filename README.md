# OntologyDesignResearch

從 Sean 提供的會議、簡報與對話紀錄，整理出團隊實際可用的 **Domain 設計流程**：怎麼把連續的現實切成系統能用的單位個體（Ontology），每一步交什麼、怎樣算完成、怎麼和 AI 協作。並把它做成一套可以直接在新 repo 使用的 Claude Code **設計流程工具包**。

---

## 先讀哪些

| 順序 | 文件 | 適合誰 | 內容 |
|---|---|---|---|
| 1 | [`Domain設計心法_精華版.md`](Domain設計心法_精華版.md)（[網頁](https://claude.ai/artifact/YJ5RrTAownYBGb28tiR1tV)） | 所有人 | 一頁讀完：主線、單位個體、四個信念、六個階段 |
| 2 | [`團隊開發流程.html`](團隊開發流程.html)（[網頁](https://claude.ai/artifact/BTkJn9DNAbTQdKB98NL4xi)） | 所有人 | 六步開發流程：每一步交什麼、怎樣算完成 |
| 3 | [`團隊開發流程_精簡版.md`](團隊開發流程_精簡版.md) | 要實際跑設計的人 | **Domain 設計規範**，流程的正式依據 |
| 4 | [`Domain設計輸入輸出規範.md`](Domain設計輸入輸出規範.md) | 要實際跑設計的人 | 每份交付物的確切格式、編號、標記、引用方式 |
| 5 | [`domain-design-kit/README.md`](domain-design-kit/README.md) | 要開始一個新 domain 的人 | 怎麼用工具包開新 repo、怎麼和 Claude Code 協作 |

---

## 文件一覽

### 流程規範（正本）

| 文件 | 內容 |
|---|---|
| [`團隊開發流程_精簡版.md`](團隊開發流程_精簡版.md) | Domain 設計規範：規劃、六步、凍結與修改、切片與共用核心、回頭與回歸 |
| [`Domain設計輸入輸出規範.md`](Domain設計輸入輸出規範.md) | 交付物格式：目錄、編號、標記、各檔案的固定章節與欄位、CHANGELOG、交接點 |
| [`平台架構約定.md`](平台架構約定.md) | 平台層級決定一次的事（P1～P10）：事件、歷史保存、資料身分、規則版本、多語標籤等 |
| [`本體論設計指南.md`](本體論設計指南.md) | 詳細手冊：判斷準則、YAML 宣告格式、檢查工具與案例 |
| [`Domain設計心法.md`](Domain設計心法.md)、[`Domain設計心法_精華版.md`](Domain設計心法_精華版.md) | 每個階段「為什麼要做」：連續現實 → 離散單位個體 |

**衝突時以誰為準**：內容要求以精簡版為準；交付物格式以輸入輸出規範為準；平台層級的決定以平台架構約定為準。手冊與心法是說明，不另立規定。

### 網頁（給團隊瀏覽）

| 網頁 | 原始檔 |
|---|---|
| [六步開發流程](https://claude.ai/artifact/BTkJn9DNAbTQdKB98NL4xi) | [`團隊開發流程.html`](團隊開發流程.html) |
| [Domain 設計心法](https://claude.ai/artifact/NYTNBtchjCAE4ZLZXy2JkY) | [`Domain設計心法.html`](Domain設計心法.html) |
| [Domain 設計心法精華版](https://claude.ai/artifact/YJ5RrTAownYBGb28tiR1tV) | [`Domain設計心法_精華版.html`](Domain設計心法_精華版.html) |

修改原始檔後要重新發布，網頁才會更新。

### 設計流程工具包

[`domain-design-kit/`](domain-design-kit/)：複製到新的 repo，用 Claude Code 打開就能依規範跑設計（`CLAUDE.md`、指令、範本、檢查工具、規範副本）。使用方式見它自己的 README。

- `domain-design-kit/docs/` 是本目錄規範的**副本**，不要直接修改。改完本目錄的正本後，在 `domain-design-kit/` 執行 `python3 build_kit.py` 重建副本與範本的檢查清單。
- 已經開始使用的設計 repo 不會自動更新，需要手動複製新版工具包檔案。

### 研究與對照

| 文件 | 內容 |
|---|---|
| [`Ontology輸入輸出定義_依Sean原始材料.md`](Ontology輸入輸出定義_依Sean原始材料.md) | 依 Sean 原始材料整理的 Ontology 輸入與輸出 |
| [`Sean三層架構與八步八元素對照.md`](Sean三層架構與八步八元素對照.md) | Define／Preserve／Prove 三層、八個步驟、八元素的解釋與對比，以及對應到我們的流程 |
| [`DoubleDiamond研究.md`](DoubleDiamond研究.md) | Double Diamond 的版本演進、是否線性，以及 Sean 的用法 |

### 紀錄

| 文件 | 內容 |
|---|---|
| [`團隊開發流程_對抗性審查.md`](團隊開發流程_對抗性審查.md) | 對流程的反方審查、每項的決定，以及之後所有修改的理由（流程的決策紀錄） |
| [`AI協作方式分析報告.md`](AI協作方式分析報告.md) | 本研究過程中與 AI 協作方式的分析 |

---

## 原始材料

Sean 的會議逐字稿、簡報與對話紀錄（`Sean會議記錄/`、`sean_ontology_conversation/`、`SeanHRSystemWay/`）只放在本機，**不納入本 repo**（見 `.gitignore`）。

文件中引用 Sean 的說法時，一律指向原始材料（檔名與逐字稿時間戳記），不引用整理過程中的暫存檔。

---

## 維護方式

1. 修改流程時，先改正本（精簡版、輸入輸出規範等），同步檢查其他文件有沒有衝突。
2. 在 [`團隊開發流程_對抗性審查.md`](團隊開發流程_對抗性審查.md) 的更新紀錄記下改了什麼、為什麼。
3. 在 `domain-design-kit/` 執行 `python3 build_kit.py`。
4. 有改到 `.html` 的，重新發布網頁。
