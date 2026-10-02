# Ontology 與 Ontology Engineering 的輸入與輸出（依 Sean 全部原始材料）

> 本文件只依據 Sean 的原始材料，不引用團隊先前的任何整理。各節的出處代號如下：
>
> | 代號 | 原始材料 |
> |---|---|
> | A | 「詢問 AI Talent Hub」逐字稿＋generated_files（Round、FP0～FP10） |
> | B | 「回顧人資系統架構」逐字稿＋generated_files（含程式碼）＋`SeanHRSystemWay/完整對話_PV1_專案執行紀錄.md` |
> | C | `SeanHRSystemWay/` 文件包：SeanOntologyExample、WP1_10 登錄表、UML／US／UC 報告、TR0 文件包（18 個 zip）、D01～D15 原型 |
> | D | 「人資系統實體資料架構」逐字稿 |
> | E | 「Ontology與Neo4j比較」「專案系統進度整理」逐字稿＋generated_files |
> | F | `Sean會議記錄/` 9/18、9/21 會議逐字稿，以及 AITalentHub PPT、PPT2、PPT3 |
> | G | `Sean會議記錄/20260930/`：9/30 Lumori 會議逐字稿與 6 章簡報（含各章 `說明.md`） |
>
> 對話逐字稿都在 `sean_ontology_conversation/<對話名>/raw_transcript/`。文中的 L 行號指對應逐字稿的行號，[hh:mm:ss] 指會議逐字稿的時間碼。本文以原始材料為唯一錨點：要查證某項內容，請依代號回到對應的逐字稿、文件或簡報。
>
> **材料本身的缺口**：FP1～FP9、FP10-WP1、Round 4.5 WP7／WP8 的檔案當初沒下載到；Round 1～4 部分檔案只有開頭；User Story 的機器可讀登錄檔、PM 專案的 .sql 檔、PPT3 第 9～11 頁不在材料中。這些部分只能依對話中的轉述判斷。

---

## 一、結論先講

「Ontology」在 Sean 的材料裡有四種講法（前三種到 9/21 為止，第四種是 9/30 的最新說法）：

| 層次 | 說法 | 出處 |
|---|---|---|
| Sean 口述 | 多個系統之間的「最大公因數」＝核心名詞，讓大家用同一個名詞溝通；它是標準（canonical model）；用來限制 AI 的範圍；資料庫是它的投影 | F（9/18 [00:11:42]、[00:13:21]、[00:10:00]、[01:08:44]、[01:19:11]） |
| 執行計畫 | 現實世界存在什麼、如何關聯、如何發生與改變、法律如何成為有來源的規則；經實例與測試驗證後凍結 | C（AI-Only 計畫 §十六） |
| 實際操作 | 一份凍結的機器可讀登錄：**FP11 Canonical Registry**，8 類共 3,323 筆，版本 `TW-SME-DCHRO-ONTOLOGY-CORE-1.1`；所有下游都以它為唯一語意輸入 | A、B、C、E |
| Sean 9/30 | 在一個世界裡辨識出**名詞與動詞**及其關係；「meaning comes from relationship」；Ontology 定義邊界（名詞、動詞）與規則（路徑）；在 AI 的語意空間「建水泥牆」；產出稱為 canonical semantics model；產品化為 Lumori（Enterprise Ontology System） | G（[00:11:45]、[00:51:24]、[00:55:48]、[00:52:50]、[00:25:28]、[00:02:53]） |

**務實的一句話**：Ontology 是一份凍結、有版本、可以用機器讀取的「意思」定義（名詞、動詞、關係、事件與狀態、有來源的規則、約束）；它本身不執行任何東西，資料庫、API、程式、測試、UML／User Story／Use Case 都是從它投影出來，並且要能指回它。

---

## 二、最終版本實際包含什麼（Core 1.1／FP11 Registry）

| 類別 | 數量 | 實際構成 | 出處 |
|---|---|---|---|
| Entity | 143 | 每筆一張 48 欄 Entity Card；分屬 15 個 BoundedContext；上層抽象類別 13 個 | C；A |
| Relationship | 383 | 每筆一張 36 欄卡片（含基數、時間性、ownership）；380 有效、2 重新分類、1 退役 | C |
| Constraint | 1,241 | **858 = 143 個 Entity × 6 種邊界**（身分、生命週期、一致性、權限、證據、法律效果）＋ **383 = 每條關係一筆**完整性約束 | C |
| Event | 215 | 16 欄 | C |
| State Machine | 27 | | C |
| Guard | 36 | 狀態轉換前提 | C |
| Rule | 132 | 32 欄 Rule Card，帶法源、確定性、自動化模式 | A、C |
| Mapping | 1,146 | 766 關係正反向謂詞、286 Entity 英中名稱、54 舊別名、24 未來匯入欄位、15 多型端點、1 附屬物件 | C |

另外，文件中的本體還包含 62 個 Command、31 個更正／重播契約、28 條能力問題、24 張情境卡；這些沒有全部計入 3,323 筆（A）。

---

## 三、什麼不算 Ontology

依 T0～T3 四層真相模型（B），**Ontology＝T0 語意定義**，以下都不算：

| 不算 Ontology | 例子 | 出處 |
|---|---|---|
| T1 業務實例 | 某筆請假、某次規則執行紀錄 | B |
| T2 投影 | 目前狀態、餘額、快取、mapping 的執行結果 | B |
| T3 外部觀察 | 政府、銀行回執 | B |
| 15 類表現形式 | UI、資料表、ORM、API DTO、政府 API schema、AI 解讀、Token、測試資料 | B（TR0-WP1 Forbidden 清單） |
| 實作契約 | IE1 的持久化對照、邏輯模型、API、runtime 契約（是 Ontology 的投影） | B |
| 程式實作 | PV1 的 semantic adapter（要另外人工核准） | B |
| 執行時產生的資料 | RuleVersion、Evidence 的實例 | E |
| 範圍外 | 招募、績效、人才盤點、30 人以上義務、跨國薪資、Token、區塊鏈 | A |

GPT 的邊界原則：「Ontology 是語意來源。資料庫是儲存投影。API 是操作契約」（A，L7694–7698）；「Representation may change. Meaning may not silently change.」（B、E）。

### 灰色地帶

1. **Mapping 算不算 Ontology，文件沒有明文回答。**
   - 算入 3,323 筆，所有「覆蓋率 3,323／3,323」都包含它；TR0-WP2 寫「Exact-mapping contract is T0」（B、C）。
   - 但 Sean 的方法論把 Exact Mapping 放在第二層（語意投影到系統）；UML 把它歸為「Implementation Mapping」；TR0 只當溯源後設資料；沒有任何 Use Case 擁有它（A、C）。
   - 實際內容多半是名稱、謂詞、別名的查找表，由 Entity 與關係機械展開（C）。
   - 另有一種「Persistence Mapping」（IE1，3,323 列），明確是投影，不是 Ontology（B）。兩者都叫 mapping。
2. **原屬實作層的概念被移進本體**：Aggregate、Command、System of Record、未來匯入欄位對照，原本在「資料庫與 API」步驟，後來進了凍結的本體文件（A）。
3. **Ontology 與 Registry 是一層還是兩層**：文件寫成「Ontology → Canonical Registry」兩步，但沒說明差異；操作上是同一份東西（C、E）。

**團隊流程的處理方式**（《團隊開發流程_精簡版.md》0.1）：名稱、別名這類對照寫在 Entity 卡裡，屬於 Ontology；「概念 ↔ 表／API」的對照是第 ⑤ 步的投影契約，不屬於 Ontology、不放進 `core/`。Aggregate、Command 等實作概念也放在第 ⑤ 步。

---

## 四、輸入

### 4.1 實際放進去的

| 輸入 | 內容 | 出處 |
|---|---|---|
| Sean 的指令 | 範圍（30 人以下、請假到發薪）、產業例子、定義 entity、Token 觀點、驗證需求、薪資細節（全勤、內外帳、特權給予）、三層方法論、「不用跟人討論，用 AI 自我論述」、要求記錄凍結版本 | A |
| GPT 自己前一階段的產出 | 每個 Round、WP、FP 都以前一階段的產出為輸入；FP11 由 2,183 個卡片檔產生 | A、C |
| 官方法源 | 24 個來源、53 份整理過的快照；文件自承「不是官方原始檔封存」 | A |
| AI 合成資料（D0） | FP10 的 6 家合成企業、701／1,051 個實例、528 個測試案例；保險費率、稅率也是合成值 | A、B |

### 4.2 沒有放進去的

- **真實企業資料**：從未取得，PV1-WP15 因此卡住（B）。
- **外部專家或人工簽核**：原計畫中的法律顧問、薪資實務簽核，在「AI-Only」後取消（A，L7180）。
- 所有關卡的 PASS／FROZEN 都由 GPT 在回覆中宣告，材料中找不到其他人簽核的紀錄（A、D、E）。

### 4.3 Sean 口述中認為應有的輸入

範圍／domain、邊界、人的知識素養、例子、high level 加 first person view、分階段目標、法規提醒（F）。PPT2 把輸入畫成：法規文件、企業案例、業務資料、流程規則（F）。

---

## 五、過程：Ontology Engineering 的步驟

| 計畫的步驟（AI-Only 計畫） | 實際執行 | 備註 |
|---|---|---|
| 1 核心 Entity | Round 1 → FP1～FP3（索引、15 領域建卡、6 類邊界） | |
| 2 關係、基數、時間 | Round 2 → FP4～FP5 | |
| 3 事件、狀態機、更正 | Round 3 → FP8 | |
| 4 法律規則 | Round 4 → FP9 | |
| 5 實例 | FP10（6 家合成企業） | 見第八節「真實資料」 |
| 6 完整驗證 | FP10 | 原計畫至少 100 個測試；更嚴謹的 VA1～VA12 未執行 |
| — | FP6 約束、FP7 Exact Mapping | 計畫沒有，執行中加入本體 |
| — | FP11 機器可讀登錄 | 本體被「機器化」，成為唯一輸入 |
| 7 資料庫與 API（投影） | TR0 → IE1 → IE2 → PV1；UML → US → UC → TR0-00～16；IM1 | 不屬本體工程本身 |
| 8 Token（投影） | 未開始 | |

FP 編號是 Sean 要求「記錄凍結版本」後才產生的，之後至少改了五版；原計畫的 Round 5～8 沒有照原名執行（A）。

---

## 六、輸出與下游

### 6.1 權威順序

```
Ontology（T0）→ Canonical Registry（FP11）→ Persistence Mapping（IE1）→ 實體資料庫
```
圖資料庫、materialized view、搜尋索引都是可重建的投影，不能成為語意來源（E）。GPT 曾把 Neo4j 稱為「Semantic Source of Truth」，後來自己改口（E）。

### 6.2 下游怎麼使用 Ontology

| 下游 | 怎麼用 | 出處 |
|---|---|---|
| UML | D01、D02 直接由 FP11 生成；D03～D17 在對話中設計，147 個術語有 93 個不是 canonical 詞，事後用對照表補回 | C |
| User Story、Use Case | 宣稱由 UML 投影；Use Case 的追溯全部經由 User Story 間接產生 | C |
| TR0-00～16 | 輸入只寫 FP11；每個產物綁定 CanonicalRef；18,559 個產物約 72% 是對 3,323 筆逐列分類 | C |
| IE1 投影契約 | 3,323 筆逐一對到持久化、14 個邏輯類別、32 個 Command、14 個 Query、132 條規則 runtime 契約 | B |
| 實體資料庫（IM1） | 以 3,323 筆 canonical 紀錄為單位，不是以 143 個 Entity 為單位；實體資料用 `canonical_type_ref` 指回 | D |
| 程式碼（IE2） | 驗證契約檔的 SHA-256 與數量；ID 只當目錄；沒有處理程式就回傳 BLOCKED；業務規則邏輯未實作 | B |

### 6.3「Entity ≠ Table」的實際落實（IM1）

- 開表判準：有自己的身分、生命週期、時間歷史、基數、安全邊界、保存規則或存取需求之一，才開新表（D）。
- 例子：Person 拆 4 張表、Evidence 拆 5 張、Rule 拆 2 張；事件用共用表加各領域明細表；一張表可承載多個 canonical type，但要保留類型欄位（D）。
- 規模：D-2 列 65 個表名，D-9 主幹表 27 個（D）。
- 不落地為權威資料：餘額等投影、推導關係、目前狀態、快照（D）。

---

## 七、定義演變與漂移（重點）

| # | 項目 | 變化 | 出處 |
|---|---|---|---|
| 1 | Ontology 的指涉 | 從「核心本體（Entity、關係、事件、規則）」→ FP11 之後改稱「Canonical Registry」，下游不再給 Ontology 獨立定義；IM1 後半完全不提「143 entity」，只提 3,323 筆 | C、D |
| 2 | Exact Mapping 的位置 | 從第二層（投影）→ 凍結本體中具正式語意效力的文件，內容變成名稱與別名對照 | A |
| 3 | 驗證的性質 | 能力問題從「某人某天的雇主是誰」的查詢題（門檻 40 題）→ 28 題「能否…」的是非題；情境改由 132 條規則衍生，24 張情境卡變異與步驟相同 | A |
| 4 | PASS 的意思 | IM1 D-9 以前是文字宣告；D-10 起改為「NOT_EXECUTED ≠ PASS」；GPT 承認 D-9 宣稱全數涵蓋的機器可讀登錄原檔不存在 | D |
| 5 | FP 編號 | 至少五版；FP12～16 被撤回改作他用；兩份簡報的 FP12 意思不同 | A、B、F |
| 6 | FP11 範圍 | 原規劃 13 類，實際 8 類 | B |
| 7 | 數字 | Round → FP11：Entity 134→143、關係 305→383、事件 150→215、狀態機 13→27、Guard 16→36、規則 124→132 | C |
| 8 | Evidence | 從語意來源的一部分被移出，改為「Evidence ≠ Truth」 | B |
| 9 | Shared Foundation（PM） | 從「共用 Person、Evidence 等 entity」（預估 30～40%）→ 只共用「X ≠ Y」規則、基本元素、抽象模式，共用的具體業務 entity 為 0 | E |
| 10 | 本體內容的新增 | PV1-WP5B 由 GPT 自行解決規則衝突並產生新規則版本，是實作階段唯一一次在本體層新增語意 | B |
| 11 | Ontology 的核心單位 | 9/18 是「最大公因數＝核心名詞」→ 9/30 是「名詞＋動詞＋關係」，動詞也有生命週期與狀態機 | F → G（[00:11:45]、[00:23:24]） |
| 12 | 人資的地位 | 9/18 把產品收斂為「只做人資」→ 9/30「foundation 已經不是 HR，上一次只是為了讓各位練習」，範圍擴大為 12～15 個領域 | F → G（[00:08:42]、[00:30:19]） |
| 13 | 三層方法論的名稱 | Semantic／Governed Architecture／Evidence-Driven → Define／Preserve／Prove Meaning；第三層的證明手段具體化為 CI/CD、資料庫 constraint 與 trigger | F → G（[00:56:38]～[00:57:15]） |
| 14 | 階段代號 | FP、TR0、IM1 等之外，又出現 SE-00～03、MM01～MM12、Freeze A 一套新代號 | G（Ch05、Ch06） |
| 15 | 語意分層 | 9/30 提出 core semantic → shared → 特殊 domain 三層；與 PM 專案 Shared Foundation 的 L0～L3 概念相近 | G（[00:46:08]）、E |

---

## 八、已知矛盾（需與 Sean 確認）

1. **TRO／TR0 與 UML、User Story、Use Case 的先後**：9/21 口述「TRO 做完之後」才做 UML 等；PPT3 與 TR0-16 文件的順序是 UML → US → UC → TR0（F、C）。
2. **TRO 是語意層還是轉換契約**：口述說「語意層」；簡報說語意與實作之間的轉換契約（F）。
3. **Ontology 在三層方法論中的範圍**：口述說整個第一層就是 Ontology；簡報把它列為第一層五個子項之一（F）。
4. **Ontology 與 Persistent Layer 的方向**：9/21 有一處說以既有 Persistent Layer 為 ontology engineering 的基礎，與「資料庫是 Ontology 投影」相反（F）。
5. **EMP-010 的時間語意**：TR0-03 說 143 個 Entity 都有時間契約；IE1-WP1 標為「未指定」（D）。
6. **狀態機的對應**：UML15R 兩份檔案對 27 個狀態機的 UML 對應結論相反，兩邊都標 RESOLVED（C）。
7. **上層抽象類別編號**：FP11 內 ABS 有兩套衝突編號，例如 ABS-008 同時指 Plan 與 Entitlement（C）。
8. **產品範圍**：Round 4 從 1–29 人改成 1–30 人（C）。
9. **請假與出勤**：D-2 表清單有，D-9 主幹表與首批查詢路徑沒有（D）。
10. **領域數量**：9/30 口述 15 個 domain，簡報列 12 個（G）。
11. **八個核心元素兩個版本**：Ch01 為 Reality、Facts、Identity、Relation、Time、Rule、Authority、Evidence；Ch02、Ch04 為 Identity、Relation、Time、Rule、Authority、Evidence、Event、History（G）。
12. **9/30 進度簡報前後矛盾**：MM12 Freeze Gate 標為受阻，Freeze A 卻勾為已凍結；Layer 2、3 標為完成，同章其他頁顯示實作進行中、歷史重建受阻；「全域語意基礎 v0.2」與「Canonical Registry v1.0」版本號對不上（G，Ch06）。
13. **CI/CD 的定位**：9/21 說「CI/CD……將來用 AI 去做就好」；9/30 把 CI/CD 列為第三層的證明手段（F → G）。
14. **over design 與小切片**：9/30 說「AI 時代沒有 over design」（[00:46:50]），與方法論第三層的 thin vertical slice、defer abstraction 看似衝突；但同場作業要求「選一個 domain，從小範圍開始」（[01:01:29]）（G）。

---

## 九、更正初稿

初稿寫「Sean 指示用真實企業資料建立 Instance，被 GPT 改成合成資料」，**此說法不正確**：

- 「第五步：用真實企業資料建立 Instance」**最早由 GPT 寫出**（逐字稿 L4980 附近，GPT 回覆），Sean 在 L5904 照抄 GPT 的八步驟。
- 改成合成資料有兩次，**都是 GPT 決定**：
  - Sean 說「不用跟人討論，用 AI 自我論述」（L7174）後，GPT 改為「由 AI 建立三家完整合成企業」（L7564）。Sean 這句話沒提資料來源，之後也沒有表示同意或反對。
  - FP10：GPT 先寫「用真實企業資料」（L15240），接著在 WP1 規定「一律優先採用 D0 合成資料」（L16466）。
- 結論：「改用合成資料是 GPT 決定的」成立；「真實資料是 Sean 的原始設計」不成立（A）。

---

## 十、9/30 會議後的更新

9/30 是到目前為止 Sean 對 Ontology 講得最完整的一次（G），主要補充如下。

### 10.1 方法的三步

> 「第一步，做名詞；第二步，做動詞；第三步，驗證整個事件。」（[00:22:50]）
> 「動詞跟名詞同樣都會有生命週期，凡是有生命週期的東西就有狀態。」（[00:23:24]）

之後把資料歸類、定義規則，建立「一套可驗證的結構」，稱為 **canonical semantics model**（[00:25:15]～[00:25:28]）。名詞與動詞全部標準化，**先用英文訂標準，再產生中文等語言的對照**，因為中文的歧義較多（[00:26:37]～[00:26:54]）。

### 10.2 Ontology 與 AI 的關係

- 語言模型裡的每個詞是一片「分佈」（manifold），不是一個點；相似的概念會靠近，但「很近不代表相同」（[00:52:12]、[00:55:31]）。
- Ontology 是在這個高維空間裡「建水泥牆」，把相近但不同的概念隔開，避免 AI 產生幻覺（[00:52:50]）；「AI 是天馬，給他韁繩」（[00:29:52]）。
- 兩者結合稱為 neuro-symbolic；「不是把語言模型跟 Graph 放起來就 OK 了」（[00:56:07]～[00:56:18]）。
- 「一般 ontology 不是畫一張知識圖，而是一套工程」（[00:57:28]）。

### 10.3 三層方法論：Define／Preserve／Prove

| 層 | 9/30 名稱 | 任務 | 關鍵機制（簡報 Ch04） |
|---|---|---|---|
| 1 | Semantic Engineering | Define Meaning：世界是什麼 | 八個核心元素（Identity、Relation、Time、Rule、Authority、Evidence、Event、History）、Anti-Collapse |
| 2 | Governed Architecture | Preserve Meaning：意思在 DB、API、事件、流程、AI 之間不流失 | 「Representation may change. Meaning may not silently change.」、Projection Contract、Exact Mapping、Round-Trip |
| 3 | Evidence-Driven Product | Prove Meaning：用證據證明意思沒變 | 情境測試、十種對抗測試、歷史重建、Semantic Diff = 0；可結合 CI/CD、資料庫 constraint 與 trigger（[00:56:48]） |

### 10.4 決策流程

Sean 以團隊的請假系統為例說明「程序做完很 OK，但整體不 OK」（[00:35:58]）：企業決策應依序為

```
訊號 → 對應證據並 find out → 判斷整體狀態 → 產生 proposal → 找到 human in the loop，共同決定
```

例如員工要請特休時，系統應查他還剩幾天、對照專案進度，再同時給員工與主管建議；老闆端也應有主動的 AI，每週掃描並提出休假建議（[00:35:24]～[00:38:10]）。這把「AI 建議 ≠ 人的決定」從原則變成具體的流程要求。

### 10.5 工作包與進度（簡報 Ch05、Ch06）

- 新的工作包：SE-00 語意憲法、SE-01 標準語意模型（MM01～MM12）、SE-02 認知憲法（憑什麼相信）、SE-03 權威與真實來源、Freeze A（四者合併凍結成共同語意基礎），之後才展開 12 個領域。
- Meaning（是什麼意思）、Knowledge（憑什麼相信）、Authority（誰有權決定）三者分開處理，是 9/30 新增的區分。
- 進度：HR 領域標為 FROZEN，PM、Contract 為 VALIDATED，其餘多數進行中；工程主線在「05 Implementation」，主要阻礙仍是 Native PostgreSQL 環境。數字有前後矛盾，見第八節。

### 10.6 對輸入輸出定義的影響

| 項目 | 9/30 之前 | 9/30 之後 |
|---|---|---|
| 核心單位 | 名詞（Entity） | 名詞＋動詞，兩者都有生命週期 |
| 輸出名稱 | Canonical Registry | canonical semantics model（實體上仍是同一類登錄） |
| 命名 | 英中並列 | 英文為標準，其他語言為對照 |
| 輸出結構 | 單一人資本體 | core → shared → domain 三層，跨 12～15 個領域 |
| 證明方式 | GPT 自評的 Gate | 加入 CI/CD、資料庫 constraint 與 trigger |
| 下游 | 資料庫、API、程式 | 另加決策流程（建議 → 人決定）、chat 與 dashboard 兩種介面（[00:43:42]） |

---

## 十一、務實版的輸入與輸出

把以上整理成團隊可以用的定義：

| | 內容 |
|---|---|
| **輸入** | 範圍與邊界；規範來源（官方法規、公司政策）；真實情境、例外與反例；（驗證用）實例資料 |
| **過程** | 定義名詞 → 動詞（含生命週期）→ 關係 → 事件與狀態 → 有來源的規則 → 約束 → 用實例嘗試推翻 → 凍結並機器化 |
| **輸出** | 一份凍結、有版本、機器可讀的定義集：Entity（含 6 種邊界，英文標準名稱＋各語言對照）、動詞與關係（含基數與時間）、事件、狀態機（名詞與流程皆有）、轉換前提、有來源與版本的規則、約束；分 core／shared／domain 三層；加上驗證報告與決策紀錄 |
| **不產出** | 資料表、API、UI、程式碼、業務實例、投影（這些是之後投影出來的，並要能指回 Ontology） |
| **下游如何使用** | 每張表、每支 API、每個程式物件都綁定到某一筆 Ontology 紀錄（CanonicalRef、canonical_type_ref、hash）；能用資料庫 constraint、trigger 與 CI 自動檢查的規則就自動把關；決策類功能走「建議 → 人決定」 |
| **Sean 材料實際缺的輸入** | 真實企業資料、外部專家與人工簽核；所有通過判定都由 GPT 自行宣告 |
