# Sean 的三層架構、八個步驟與八元素：解釋與對照

> **資料來源**：只引用原始材料。
> - 9/18 會議逐字稿：`Sean會議記錄/20260918/sean_ontology_20260918_逐字稿_校正版.md`
> - 9/30 會議逐字稿：`Sean會議記錄/20260930/sean_lumori_逐字稿校正版.md`
> - 9/30 簡報：`Sean會議記錄/20260930/chapter01～06/`（以下簡稱「第 X 章第 Y 頁」，頁碼依資料夾內檔名序號）
>
> **用途**：對齊團隊對 Sean 方法論的理解，避免把不同層次的東西混在一起。

---

## 一、先講結論

1. **Semantic Engineering ＝ Define Meaning，Governed Architecture ＝ Preserve Meaning，Evidence-Driven ＝ Prove Meaning。** 三組是同一個三層架構的兩種叫法：前者是**工程名稱**，後者是**這一層要達成的目標**。
2. **第 1 章第 6 頁「八個步驟」只涵蓋第一層。** 它從 Reality 走到 Canonical Model，終點就是第一層的產出；之後的實作（第二層）和驗證（第三層）不在這張投影片裡。
3. **第 4 章第 4 頁「八元素」也是第一層的內容**，但它是「模型要回答的八個問題」，不是做事的順序；它和八個步驟是兩份不同的清單。
4. **第 2 章第 2 頁是總覽**：用一張圖比較傳統開發和 Lumori。Lumori 這邊的流程是 **5 個步驟**（現實世界 → 語意建模 → 共同語意基礎 → 各領域應用 → 驗證與運行）；下方圓柱上的 8 個詞是第 3 步「共同語意基礎」的組成內容（和八元素相同），不是步驟。
5. **Evidence 這個字在三個地方出現，意思都不一樣**（見第五節）。

---

## 二、三層架構

Sean 在 9/18 會議提出三層，9/30 簡報第 4 章把每一層配上一個動詞。

| 層 | 工程名稱 | 目標 | 一句話 |
|---|---|---|---|
| Layer 1 | Semantic Engineering（語意工程） | Define Meaning（定義意思） | 世界上有什麼、邊界在哪裡 |
| Layer 2 | Governed Architecture Engineering（治理式架構工程） | Preserve Meaning（守住意思） | 意思穿過資料庫、API、流程時不走樣 |
| Layer 3 | Evidence-Driven Product Engineering（證據驅動產品工程） | Prove Meaning（證明意思） | 用證據證明意思沒有改變 |

**名稱對應的依據**
- 9/18 逐字稿 [01:21:25]：「第一層叫 semantic engineering，第二層叫做 governance architecture engineering，第三層叫 evidence-driven product engineering。」
- 9/30 簡報第 4 章：每一頁都把兩種名稱並列，例如「Layer 1：Semantic Engineering — 先定義『世界是什麼』」「Layer 2：Governed Architecture — 讓 Meaning 守恆」；總結頁（第 9 頁）標題是「Define → Preserve → Prove → Trust」，並寫出 1 Semantic Engineering 定義世界、2 Governed Architecture 守恆意義、3 Evidence-Driven Product 證明不變。
- 9/30 逐字稿 [00:56:38]：「他有三層：第一層 semantic engineering，第二層 governance architect，第三層就是哪些東西可以拿來做為 proof。」

**三層的依賴關係**：9/18 逐字稿 [01:21:34]：「第三個基於第二個；第二個如果沒有第一個做規則的界定、boundary 的界定，你是做不出來。」

### Layer 1：Semantic Engineering／Define Meaning

| 項目 | 內容 |
|---|---|
| 核心問題 | What does it mean? 先不談資料庫、API、UI（第 4 章第 3 頁） |
| Sean 口述 | 「第一層在做什麼？Ontology 定義有哪些東西、這些東西的邊界是什麼……所以要把 boundary 界定出來。」（9/18 [01:21:47]）；接著是「時間、生命週期的界定」（9/18 [01:22:17]） |
| 簡報內容 | 觀察真實世界的人、事、物、規則、時間、行為；用 Person P001 ＋ Employment E001、E002 說明同一個人可以有多段僱傭；八個要回答的問題（八元素）；Anti-Collapse 清單（第 4 章第 3、4 頁） |
| 產出 | Canonical Semantic Model（共同語意模型），也就是企業共同理解世界的語意基礎 |
| 在工程地圖的位置 | 第 5 章第 3 頁最上兩層：Semantic Foundation（SE-00～SE-03、Freeze A）與 Domain Canonical Models（12 個領域） |

### Layer 2：Governed Architecture／Preserve Meaning

| 項目 | 內容 |
|---|---|
| 核心問題 | 意思經過 Canonical → Database → API → Events → Workflow → Applications → AI Agents → External Systems，每一層都可能流失，怎麼守住（第 4 章第 5 頁） |
| 核心原則 | Representation may change. Meaning may not silently change. |
| Sean 口述 | 「第二層 governance，重要的語意不能消失，怎麼去做 log、然後怎麼去做 map。」（9/18 [01:22:25]）；「第二層就會 map 到 implementation。」（9/30 [00:46:01]） |
| 簡報內容 | Semantic Conservation：Identity、Temporal、Authority、Evidence 四種守恆，加上 Exact Mapping、Layer Separation、Round-Trip；常見的 Semantic Loss（例：`role="manager"` 被當成 `can_approve=true`、HTTP 200 被當成業務完成、SQL NULL 被當成不存在） |
| 在工程地圖的位置 | Governed Architecture（Model Governance、Projection Contract、Reference Integrity、Temporal Governance、Change & Evolution）與 Implementation（Database、API、Runtime、Integration） |

### Layer 3：Evidence-Driven／Prove Meaning

| 項目 | 內容 |
|---|---|
| 核心問題 | 系統實際運作時，意思真的沒變嗎？「功能正常 ≠ Meaning 正確」（第 4 章第 7 頁） |
| Sean 口述 | 9/30 [00:56:48]～[00:57:02]：「這裡可以跟 CI/CD 做結合，這裡可以跟你的 trigger 或 constraint 去做結合……可以對應到資料庫建成的 constraint。」口述的重點放在用資料庫約束與 CI/CD 自動把關 |
| 簡報內容 | 驗證流程：Scenario → Test Vector → Execution → Evidence → Reconstruction → Diff & Gate；十種對抗測試（Mutation、Retry、Replay、Wrong Version、Authority Shortcut 等）；Gate 要求 Semantic Diff = 0、歷史可重建、Evidence Complete。簡報的重點放在情境與對抗測試 |
| 在工程地圖的位置 | Evidence & Validation（Test Vector、Independent Validation、Reconstruction、Semantic Diff、Evidence Manifest），最後到 Verified Trust |

> Layer 3 的口述與簡報重點不同（一個講資料庫約束與 CI/CD，一個講情境與對抗測試），但說的是同一層的兩個面向：前者是「讓規則由系統自動把關」，後者是「證明它確實守住了」。

---

## 三、三張投影片

### 第 1 章第 6 頁：把 Ontology 變成工程的八個步驟

**標題**：我們把 Ontology 變成一套工程——從現實世界到可運作的共同語意模型

| # | 步驟 | 投影片上的說明 |
|---|---|---|
| 01 | Reality 現實世界 | 來自業務、人員、設備、文件、系統等各種真實事件與資料來源 |
| 02 | Facts 事實拆解 | 將複雜情境拆解成可記錄的事實，避免混合推論與判斷 |
| 03 | Identity 身份定義 | 定義核心對象（人、組織、產品、客戶等），確保唯一性，避免混淆 |
| 04 | Relation 關係建模 | 定義對象之間的關係與角色，例如人與雇用、產品與訂單、專案與任務 |
| 05 | Time 時間與狀態 | 記錄在什麼時間發生、持續多久、狀態如何變化，保留完整歷史 |
| 06 | Rule 規則與約束 | 定義業務規則、法律規範與不可違反的約束條件 |
| 07 | Authority 權威來源 | 明確資料與規則的權威來源，確保可追溯與可治理 |
| 08 | Evidence 證據與驗證 | 保存來自文件、系統、事件的證據，支撐查核與可信任的決策 |

八步之後經「整合與標準化」形成 **Canonical Model**；工程產出是語意模型、規則與約束、標準化字典、可驗證成果。

- **性質**：做事的**順序**——先看現實、拆成事實，再逐一定義各個面向。
- **涵蓋**：只有 Layer 1。依據有三：
  1. 終點是 Canonical Model，正是 Layer 1 的產出（第 5 章第 3 頁把 Canonical 放在 Semantic Foundation 與 Domain Canonical Models，後面才是治理、實作、驗證）。
  2. Sean 在 9/30 講這段時 [00:45:47]～[00:46:01]：「我們現在做的是 reality，就是剛剛講的 reality、fact，然後這個是名詞跟動詞，然後是規則……我們講的 ontology 的三層。三層，第一層在做這裡，第二層就會 map 到 implementation。」
  3. 第 2 章第 3 頁的七步可以對上：現實世界、事實、本體模型、共同語意基礎（Layer 1）→ 實作（Layer 2）→ 驗證，Semantic Diff = 0（Layer 3）→ 領域應用。八步就是把前四站展開。

### 第 2 章第 2 頁：Same Business. Different Starting Point.

**標題**：從軟體開發，走向企業語意工程

- **左邊：傳統軟體開發**：需求 → 功能 → 介面 → 資料庫 → API → 上線。HR、PM、Finance、CRM 各自定義員工、成員、付款人、聯絡人，結果是相同概念不同定義、資料難以整合、流程斷裂、AI 誤解。
- **右邊：Lumori 企業語意工程**，分兩塊：
  - **上方一排圖示是 5 個步驟**：現實世界 → 語意建模（Semantic Model）→ 共同語意基礎（Canonical Model）→ 各領域應用 → 驗證與運行（Verified Execution）。
  - **下方中間的圓柱**標著 Canonical Semantic Foundation，上面由上到下寫著 8 個詞：Identity、Relation、Time、Rule、Authority、Evidence、Event、History。它們是第 3 步「共同語意基礎」的組成內容，不是步驟。左右的 HR、PM、Finance、Production、CRM、Transaction、Product、AI Agents 都連到這個圓柱，表示各系統共用同一份語意。

- **性質**：**總覽與比較**，說明「起點不同」。
- **涵蓋**：全程概觀。前兩站（語意建模、共同語意基礎）是 Layer 1；「各領域應用」是同一個語意基礎投影到各系統（Layer 2 守住的對象）；「驗證與運行」對應 Layer 3。但這頁沒有展開第二、三層的做法。
- **圓柱上的 8 個詞**：是共同語意基礎的**內容**，和第 4 章的八元素是同一份清單。因為圓柱畫成一層一層疊起來，簡報說明檔稱它為「八層」，但它不是流程步驟。

### 第 4 章第 4 頁：Layer 1 的核心元素

**標題**：定義企業世界的 Semantic Model——Semantic Engineering 必須回答企業世界中的八個核心問題

| 元素 | 要回答的問題 |
|---|---|
| Identity 身分 | 什麼情況下仍然是同一件事？ |
| Relation 關係 | 兩個東西之間是什麼關係？ |
| Time 時間 | 何時發生？何時有效？何時被系統知道？ |
| Rule 規則 | 什麼規則在什麼條件下適用？ |
| Authority 權責 | 誰有權做出這個決定？ |
| Evidence 證據 | 根據什麼知道這件事？ |
| Event 事件 | 究竟發生了什麼？ |
| History 歷史 | 未來能不能精確重建當時的世界？ |

- 中間用「員工到職、離職、重新到職」示範：Person P001 有 Employment E001（2022–2024）與 E002（2027–），三個事件串起時間、規則、權責與證據。
- 右邊是 **Anti-Collapse**：Person ≠ Employee、Employment ≠ Employee Record、Role ≠ Authority、Evidence ≠ Truth、Decision ≠ Execution、Execution ≠ Outcome、Product ≠ Goods。
- **性質**：模型要回答的**問題清單**，加上不能合併的概念清單。
- **涵蓋**：只有 Layer 1（頁面標題就寫 Layer 1）。

---

## 四、對比

### 三張投影片

| | 第 1 章第 6 頁 | 第 2 章第 2 頁 | 第 4 章第 4 頁 |
|---|---|---|---|
| 是什麼 | 做事的八個步驟 | 傳統與 Lumori 的總覽比較 | 八個核心元素與 Anti-Collapse |
| 回答 | 怎麼從現實走到共同語意模型 | 為什麼起點不同 | 共同語意模型要回答哪些問題 |
| 清單 | 8 步：Reality、Facts、Identity、Relation、Time、Rule、Authority、Evidence | 5 步：現實世界、語意建模、共同語意基礎、各領域應用、驗證與運行；圓柱上 8 個詞：Identity、Relation、Time、Rule、Authority、Evidence、Event、History | 八元素：同左邊圓柱的 8 個詞 |
| 涵蓋的層 | Layer 1 | 全程概觀（L1 為主，L2、L3 只點到） | Layer 1 |
| 終點 | Canonical Model | 驗證與運行 | Canonical Semantic Model |

### 八步與八元素的差異

| 項目 | 八個步驟（第 1 章） | 八元素（第 2、4 章） |
|---|---|---|
| Reality、Facts | 有（第 1、2 步） | 沒有 |
| Identity、Relation、Time、Rule、Authority、Evidence | 有 | 有 |
| Event、History | 沒有獨立成步；第 5 步「時間與狀態」的說明涵蓋「狀態如何變化、保留完整歷史」 | 有 |

**解讀**：八步是**過程**，所以從 Reality、Facts 開始；八元素是**結果要具備的面向**，所以 Event、History 獨立出來。兩份清單同名為「八」，但不是同一個東西。這是 Sean 簡報本身的不一致，團隊開發流程精簡版附錄 E.4 已記錄。

---

## 五、容易混淆的地方

### 1. 同一層有兩個名字
Semantic Engineering 和 Define Meaning 是同一層，不是兩件事；其餘兩層同理。

### 2. Evidence 出現在三個地方，意思不同

| 出現在 | 意思 | 屬於 |
|---|---|---|
| 八步的第 08 步、八元素的 Evidence | 根據什麼知道這件事：保存證據、來源 | Layer 1：意思的一部分 |
| Layer 2 的 Evidence Preservation | 證據經過資料庫、API 等之後沒有遺失或被換掉（例：Content Hash 不等於 Evidence Identity） | Layer 2：守住證據 |
| Layer 3 的 Evidence-Driven | 用測試產生的證據，證明系統守住了意思 | Layer 3：證明 |

### 3. 「八」有好幾種
八個步驟、八元素（第 2 章圓柱上的 8 個詞也是這份）是兩份清單；第 2 章第 2 頁的流程則是 5 步；第 5 章的 SE-01 則有 MM01～MM12 十二項，是更細的工作項目。

### 4. Canonical Model 是交接點
它是 Layer 1 的產出，也是 Layer 2 的起點（第 4 章第 5 頁：Canonical → Database → API → …）。

### 5. 驗證不只在 Layer 3
第 5 章的 MM10 Adversarial Validation 是在**語意模型層**對抗驗證，屬於 Layer 1 內部；第 4 章 Layer 3 的十種對抗測試是在**實作層**。兩者名字相近，層次不同。

---

## 六、對應到我們的流程

| Sean | 我們的流程 | 說明 |
|---|---|---|
| Reality、Facts | 規劃（現實資料盤點、切片地圖）＋ ① 範圍與驗收問題 | 先蒐集現實，再拆成情境與驗收問題 |
| Identity、Relation | ② 名詞盤點 | Entity 卡、關係、不是 Entity 清單；Anti-Collapse ＝ 卡片上的「不能跟誰合併」 |
| Time、Event、History | ③ 流程與狀態 | 事件、狀態機、三種時間、歷史需求、更正方式 |
| Rule | ④ 規則與限制 | 規則表、守恆式 |
| Authority | ③ 的「誰可以做」＋ ④ 的「來源」 | 誰有權觸發；規則依據哪個權威來源 |
| Evidence（八元素） | ③ 事件的「證據」欄 ＋ ④ 的「來源、核對」＋ `inputs/research/` | 根據什麼知道 |
| Canonical Model | `core/`（②③④ 的產出） | 共同語意基礎 |
| Layer 1 內部的驗證（類似 MM10） | 每一步的 AI 挑錯 ＋ ⑤ 的紙上驗證 | 驗的是設計對不對得上現實，還沒有實作 |
| Layer 2 Preserve | ⑤ 對照設計 ＋ 每一步的凍結 ＋ 平台架構約定 | Exact Mapping ＝ 05_mapping；Layer Separation ＝ 平台 P3；Correction ≠ Overwrite ＝ 原則 4、平台 P2 |
| Layer 3 Prove | ⑥ 跑起來驗證 ＋ 平台 P9 自動化檢查 | 黃金案例、守恆式、權限、更正測試 |

**和 Sean 的差距（照實寫）**
- 我們的 ⑥ 只涵蓋 Sean 十種對抗測試中的一部分（更正、權限、重算一致、守恆）；Replay、Wrong Version、Interchange、Round-Trip 等目前沒有列為必做。
- 本階段只交付到 ⑤ 的設計文件：**Layer 1 完整，Layer 2 只有對照設計（Projection Contract 的文件），Layer 3 尚未進行。**
