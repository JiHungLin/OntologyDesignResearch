Lumori 是 Domain 設計網頁的視覺識別，取自 Sean 簡報〈Lumori 價值主張〉的風格：**白底、深藍字、一個藍色重點、淡彩分類、柔光點綴**。網頁名稱是 Lumori，子標題是「Domain 設計」。

## 文字與語氣

- 寫人看得懂的話：說「輪到你審查」，不說「review pending」。

按鈕寫出按下會發生什麼：「送出答案」「先存草稿」「凍結 ② 名詞盤點」。

問人的地方一律寫成選擇題，每個選項是「做法 → 結果」，建議答案放第一個。

- 不用 emoji 當裝飾。英文只用在品牌字標、overline 註記與領域名詞（Person、Employment）。
- 中文與英文、數字之間不加空格的規則跟著工具包文件走；編號（D-12、R04）與檔名用 `code` 樣式。

## 品牌字標

- 字標用 **Wordmark** 元件：`LUMORI` 全大寫、字距 0.35em，下方 overline 寫「DOMAIN 設計」。
- 字母 L U M R I 不是純色：由上往下從 `wordmark-top`（鋼藍）漸層到 `wordmark-bottom`（近黑），漸層集中在上半（42% 處已是 `wordmark-mid`）。
- O 是一圈漸層圓環：上方 `ring-sky`（藍）、右側 `ring-mist`（淡青）、下方 `ring-peach`（蜜桃）。圓環粗細和字母筆畫差不多。
- 頂列用標準尺寸；首頁或空白狀態用 `lg`。
- 目前沒有正式標誌檔，字標是依簡報封面用字型重現的；拿到向量檔後換成檔案。

## 色彩

- 色調以簡報封面的背景為基礎：天藍（`sky-100`～`sky-400`）、長春花紫（`periwinkle-200`）、淡紫（`lavender-100`、`lavender-200`）、杏桃（`apricot-100`、`apricot-200`）、玫瑰（`rose-100`、`rose-200`），加上白色光源。這組色板只當底色、光暈與裝飾，不放字。
- 頁面底用 `bg`，側欄與次要區塊用 `bg-soft`，卡片用 `surface`。
- 正文用 `ink`；次要字用 `ink-2`；`muted` 只放 18px 以上的導言（淺色主題對比 3.9）；`faint` 不放要讀的字。
- 強調只有一種藍：大字與圖形用 `accent`，連結與小字用 `accent-strong`，主要按鈕底用 `accent-fill`、上面的字用 `on-accent`。
- 六步的分類色都取自封面色板：① `c1` 天藍、② `c2` 長春花紫、③ `c3` 淡紫、④ `c4` 杏桃、⑤ `c5` 玫瑰、⑥ `c6` 鋼藍（取自字標）。分類色只用在編號、圖示與淡底（`c*-soft`），要讀的字用 `c*-ink`；正文永遠是 `ink`。
- 狀態：完成 `ok`、輪到你 `turn`、提示 `hint`、錯誤 `bad`，各有 `-soft` 淡底與 `-ink` 字色。狀態一定同時寫出文字或符號（✓ ✕ !），不只靠顏色。狀態色不在封面色板裡（封面沒有綠色），刻意和分類色分開；④ 杏桃和「輪到你」相近，所以狀態膠囊一定有字。
- 漸層只有三處：字標（字母與 O 圓環）、首頁大標的一行（`accent` → `accent-2`）、頁面光暈（`glow-blue`、`glow-lavender`、`glow-peach`）。按鈕、卡片不用漸層。
- 一個畫面同時出現的分類色不超過四種（六步流程列除外）。

## 頁面背景

- 頁面用 `lm-bg`：`bg` 白底，右上 `glow-blue`、右下 `glow-lavender`、下方 `glow-peach`、左下 `sky-200` 四團光暈，左上留白放標題，和封面的構圖一樣。
- 光暈固定在視窗上（不跟著捲動），內容卡片用 `surface-glass`（80% 白＋模糊），讓光暈透出來。
- 表格、長文件、程式碼區塊用不透明的 `surface`，閱讀時不受光暈干擾。

## 字體

- 字族 `sans`：Manrope 排英文與數字，Noto Sans TC 排中文（兩者都從 Google Fonts 載入）。`mono` 用系統等寬字。
- 標題：`display`（40px／900，一頁一個）、`h1` 28px、`h2` 22px、`h3` 17px。
- 內文：`lead` 18px 導言、`body` 16px、`small` 14px。
- 標籤：`eyebrow` 13px 粗體、字距 0.08em、`accent-strong`，放在標題上方寫步驟編號與名稱；`overline` 12px 全大寫、字距 0.2em、`faint`，只放英文註記。
- 編號與日期用 `tabular-nums`。

## 版面

- 每一頁的骨架：**PageHeader**（eyebrow → 標題 → 導言）→ 視需要一條 **Callout**（AI 要你做什麼）→ 內容卡片。
- 主區塊最大寬 1120px，左右邊界 `max(24px, 4vw)`，手機 16px。
- 間距只用 `space-*`：卡片之間 `space-4`，卡片內距 `space-6`，標題區到內容 `space-12`，區塊之間 `space-16`。
- 比較兩種做法用 **Compare**（左錯右對）；流程用 **StepFlow**；歷史用 **Timeline**。

## 邊框、陰影、圓角

- 卡片：`surface-glass` 底＋1px `line` 邊＋`shadow-card`＋`radius-lg`。分類或提示卡片改淡彩底、不加邊、不加陰影。
- 按鈕與輸入框：`radius-md`；主要按鈕 `shadow-btn`；次要按鈕 1px `line-strong` 邊。
- 抽屜、對話框：`radius-xl`＋`shadow-pop`。
- 不用粗黑框、硬位移陰影；按下按鈕不位移。
- 焦點框：2px `accent-strong`，離元件 2px。

## 深色主題

- 每個顏色 token 都有深色值；元件只用 token，主題切換不用改元件。
- 深色主題的主要按鈕是淺藍底（`accent-fill`）配深色字（`on-accent`），不是白字。
- 淡底在深色主題是低亮度的同色相，字一樣用 `*-ink`。

## 圖示

- 目前沒有圖示庫；狀態用 ✓ ✕ ! 字元放在 **StatusMark** 圓裡，其他地方用文字。
- 之後加圖示時：線條圖示、2px 線寬、放在 `*-soft` 淡色圓底上，顏色用對應的分類色或狀態色。

---

## Consuming this system (generated — do not edit)

Every path named below is under `project/` in this design system: read `project/api/tokens.md`, not `api/tokens.md`.

14 components are documented without a runnable `components/bundle.js`: read each component’s card, and its README where it has one (`components/<Comp>/README.md`), and build to those guidelines. Tokens: the values are on `api/tokens.md`; a Slides deck or Design canvas also takes `tokens.json` by file path. On a Design canvas, also copy `tokens.css` to `project/ds/<folder>/tokens.css` in the call that installs this system, and link it in each artboard that uses this system, right after the `support.js` line and before the system’s other stylesheets: `<link rel="stylesheet" href="ds/<folder>/tokens.css">` (with one `../` in front for each folder the artboard is in).

**Read, per thing:** a component’s props, parts and examples: `api/components/<Comp>.md`; token values: `api/tokens.md`. After this README, fetch the cards and fonts you need in ONE message as parallel calls — none depends on another.

**Two rules.** Before you use a thing — a component, a token group, an icon, an asset — read its card from the index below; a value you did not read from a card is a guess. `tokens.json`, `manifest.json` and `design-system.json` are sources for tools: hand them over. `components/<Comp>/README.md` is the long-form second read a card links to; `SKILL.md` and `artifact-type/` beside them are authoring guidance, not needed to consume the system.

## Index (generated — do not edit)

**Tokens**

- `api/tokens.md` — Every token: surface, text, fill, border, palette, type, spacing, radius, shadow. (11.3k)

**Components** (`api/components/<Comp>.md`, 14)

- **動作**: `Button` — 按鈕：主要動作用藍底白字，其他動作用白底細框，最次要的用無框藍字。
- **版面**: `Callout` — 結論橫條：全寬淡底，左邊圖示與短標籤，右邊一句粗體結論加一行說明。用在每頁最上面「AI 要你做什麼」。 · `PageHeader` — 每一頁最上面的標題區：eyebrow（步驟編號與名稱）→ 大標 → 導言，三層。 · `SideNav` — 左側導覽：切片與六步的樹狀列表，選中的一列用淡藍底。 · `TopBar` — 白底頂列：左邊字標，中間是目前位置與六步進度，右邊是 AI 對話按鈕。
- **內容**: `Card` — 卡片：白底、1px line 邊、radius-lg 圓角、柔陰影；要表示分類或提示時改用淡彩底、不加邊。 · `Compare` — 對照：左邊是錯誤或修改前（淡紅底、✕），右邊是正確或修改後（淡藍底、✓），中間箭頭。用在選項的「做法 → 結果」與修改前後。 · `StepFlow` — 六步流程列：每一步一張淡彩卡片，編號用該步的深色字，中間細線連接。 · `Timeline` — 時間軸：左邊日期、中間圓點與細線、右邊事件。用在 CHANGELOG 與全自動的每一圈。
- **狀態**: `Chip` — 膠囊：小型狀態或分類標籤，圓點加字。 · `StatusMark` — 狀態圓：✓ 通過、✕ 不通過、! 要處理，實色圓配白色符號，旁邊一定接文字。
- **輸入**: `Option` — 選擇題選項：每個選項一張卡片，左上字母、粗體做法、灰字結果；建議答案用淡藍底，選中加 2px 藍框。 · `TextField` — 輸入框：白底、1px line-strong 邊、radius-md 圓角；聚焦時 2px accent-strong 外框。
- **品牌**: `Wordmark` — 頂列與封面用的 Lumori 字標：全大寫、字距 0.35em，O 是天藍到蜜桃的漸層圓環，下方一行子標題「Domain 設計」。
