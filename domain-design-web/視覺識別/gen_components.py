import os
C = {}
def comp(name, group, height, readme, body):
    C[name] = (group, height, readme, body)

comp("Wordmark","品牌",150,"""頂列與封面用的 Lumori 字標：全大寫、字距 0.35em，O 是天藍到蜜桃的漸層圓環，下方一行子標題「Domain 設計」。

- 提供：子標題文字（網頁固定寫「Domain 設計」）。
- 頂列用標準尺寸（字 20px）；首頁或登入畫面用 `lg`（56px）。
- O 圓環只用 `ring-sky` → `ring-peach`，不換色、不加陰影。
- 這是依簡報封面用字型重現的字標，不是正式標誌檔；拿到 Sean 的向量檔後換成檔案。
""", """<div class="lm-pad" style="gap:28px">
  <a class="lm-wordmark" href="#"><b><span>LUM</span><span class="o" aria-hidden="true"></span><span>RI</span></b><small>DOMAIN 設計</small></a>
  <a class="lm-wordmark lg" href="#" aria-label="Lumori Domain 設計"><b><span>LUM</span><span class="o" aria-hidden="true"></span><span>RI</span></b><small>DOMAIN 設計</small></a>
</div>""")

comp("TopBar","版面",64,"""白底頂列：左邊字標，中間是目前位置與六步進度，右邊是 AI 對話按鈕。

- 提供：麵包屑文字（切片名稱與步驟）、六步各自的狀態（完成、目前、未開始）、AI 狀態。
- 背景用 `bg`，下緣 1px `line`；不用深色底。
- 進度條完成用 `ok`、目前用 `accent`、未開始用 `line`。
""", """<header class="lm-top">
  <a class="lm-wordmark" href="#"><b><span>LUM</span><span class="o" aria-hidden="true"></span><span>RI</span></b><small>DOMAIN 設計</small></a>
  <div class="mid">
    <span class="crumb">hire-employee ／ ② 名詞盤點</span>
    <div class="lm-progress" aria-label="六步進度：完成 1 步，目前第 2 步"><span class="done"></span><span class="cur"></span><span></span><span></span><span></span><span></span></div>
  </div>
  <span class="lm-chip busy">AI 進行中</span>
</header>""")

comp("SideNav","版面",340,"""左側導覽：切片與六步的樹狀列表，選中的一列用淡藍底。

- 提供：切片列表、每一步的狀態（凍結、等你、草稿、未開始）、右側的提示（例：「輪到你」）。
- 步驟圓圈：凍結 `ok`、等你 `turn`、草稿細框、未開始虛線；圓圈裡一律寫編號，不只靠顏色。
- 分組標題用 overline。
""", """<nav class="lm-nav" aria-label="導覽">
  <div class="lm-overline h">規劃</div>
  <a href="#">切片地圖</a>
  <div class="lm-overline h">hire-employee</div>
  <a href="#"><i class="frozen">1</i>範圍與驗收問題</a>
  <a href="#" class="on"><i class="wait">2</i>名詞盤點<span class="x lm-chip turn">輪到你</span></a>
  <a href="#"><i class="draft">3</i>流程與狀態</a>
  <a href="#"><i>4</i>規則與限制</a>
  <a href="#"><i>5</i>投影到實作</a>
  <a href="#"><i>6</i>跑起來驗證</a>
</nav>""")

comp("PageHeader","版面",190,"""每一頁最上面的標題區：eyebrow（步驟編號與名稱）→ 大標 → 導言，三層。

- 提供：步驟編號與名稱、一句標題、一到兩行導言。
- eyebrow 用 `accent-strong`；大標用 display 或 h1；導言用 lead、`ink-2`。
- 一頁只有一個標題區。
""", """<div class="lm-pad"><div class="lm-page-head">
  <div class="lm-eyebrow">02　名詞盤點</div>
  <h1 class="lm-display">一個人，<span class="grad">不等於一個員工</span></h1>
  <p class="lm-lead">同一個人可以有好幾段雇用關係。這一步確認哪些是「一個東西」、彼此是什麼關係。</p>
</div></div>""")

comp("Callout","版面",200,"""結論橫條：全寬淡底，左邊圖示與短標籤，右邊一句粗體結論加一行說明。用在每頁最上面「AI 要你做什麼」。

- 提供：標籤（兩到四字）、一句結論、一行說明。
- 一般用 `bg-soft` 底、`accent-strong` 結論；輪到人做事時加 `turn`。
- 一頁最多一條。
""", """<div class="lm-pad">
  <div class="lm-callout"><span class="ico" aria-hidden="true">●</span><span class="k">關鍵觀念</span><div><div class="m">同一個真實世界的對象，可以有多段不同的關係與狀態。</div><div class="d">先把 Person 和 Employment 分開，年資、權限、歷史才算得對。</div></div></div>
  <div class="lm-callout turn"><span class="ico" aria-hidden="true">!</span><span class="k">輪到你</span><div><div class="m">回答 3 題選擇題，確認新增的名詞與關係。</div><div class="d">每題都有建議答案；看例子再選。</div></div></div>
</div>""")

comp("Button","動作",88,"""按鈕：主要動作用藍底白字，其他動作用白底細框，最次要的用無框藍字。

- 提供：按鈕文字（寫出按下會發生什麼，例：「送出答案」）。
- 一個畫面最多一個 `primary`。
- 按下不位移；停用時透明度 45%。
""", """<div class="lm-pad"><div class="lm-row">
  <button class="lm-btn primary">送出答案</button>
  <button class="lm-btn">先存草稿</button>
  <button class="lm-btn quiet">看完整檔案</button>
  <button class="lm-btn" disabled>凍結（還有 2 題沒答）</button>
</div></div>""")

comp("Card","內容",230,"""卡片：白底、1px `line` 邊、`radius-lg` 圓角、柔陰影；要表示分類或提示時改用淡彩底、不加邊。

- 提供：標題與內容。
- `tint c1`～`c6` 對應六步；`tint hint` 是提示；`tint bad` 是錯誤做法。
- 卡片裡不再放卡片。
""", """<div class="lm-pad"><div class="lm-row" style="align-items:stretch">
  <div class="lm-card" style="flex:1 1 220px"><div class="lm-h3">Person</div><div class="lm-small">同一個人，不會因為離職而改變。</div></div>
  <div class="lm-card tint c2" style="flex:1 1 220px"><div class="lm-h3">Employment</div><div class="lm-small">一段雇用關係：開始、結束、部門與職位。</div></div>
  <div class="lm-card tint hint" style="flex:1 1 220px"><div class="lm-h3">提示</div><div class="lm-small">年資要從 Employment 算，不從 Person 算。</div></div>
</div></div>""")

comp("StepFlow","內容",170,"""六步流程列：每一步一張淡彩卡片，編號用該步的深色字，中間細線連接。

- 提供：六步各自的狀態（目前、未開始）。
- 顏色：① `c1` ② `c2` ③ `c3` ④ `c4` ⑤ `c5` ⑥ `c6`；編號用 `c*-ink`。
- 未開始改虛線框、灰字；目前那一步加 `accent-strong` 外框。
- 手機寬度改成兩欄。
""", """<div class="lm-pad"><div class="lm-steps">
  <div class="lm-step c1"><span class="n">01</span><span class="t">範圍與驗收問題</span><span class="s">做到哪裡</span></div>
  <div class="lm-step c2 cur"><span class="n">02</span><span class="t">名詞盤點</span><span class="s">哪些是一個東西</span></div>
  <div class="lm-step c3"><span class="n">03</span><span class="t">流程與狀態</span><span class="s">事情怎麼發生</span></div>
  <div class="lm-step c4"><span class="n">04</span><span class="t">規則與限制</span><span class="s">什麼必須成立</span></div>
  <div class="lm-step c5"><span class="n">05</span><span class="t">投影到實作</span><span class="s">放在哪張表</span></div>
  <div class="lm-step locked"><span class="n">06</span><span class="t">跑起來驗證</span><span class="s">未開始</span></div>
</div></div>""")

comp("Compare","內容",270,"""對照：左邊是錯誤或修改前（淡紅底、✕），右邊是正確或修改後（淡藍底、✓），中間箭頭。用在選項的「做法 → 結果」與修改前後。

- 提供：兩邊的標題與要點。
- 左邊固定 `bad-soft`，右邊固定 `c1-soft`；不換邊。
- 手機寬度上下排。
""", """<div class="lm-pad"><div class="lm-compare">
  <div class="side before"><div class="lm-status"><span class="lm-mark bad" aria-hidden="true">✕</span><span class="lm-h3">只存成「員工」</span></div><ul><li>分不出兩段雇用</li><li>年資、特休算錯</li><li>歷史被覆蓋</li></ul></div>
  <div class="arrow" aria-hidden="true">→</div>
  <div class="side after"><div class="lm-status"><span class="lm-mark ok" aria-hidden="true">✓</span><span class="lm-h3">分開 Person 與 Employment</span></div><ul><li>同一人有多段雇用</li><li>每段各算年資</li><li>可以回答「當時是什麼」</li></ul></div>
</div></div>""")

comp("Timeline","內容",250,"""時間軸：左邊日期、中間圓點與細線、右邊事件。用在 CHANGELOG 與全自動的每一圈。

- 提供：日期、事件、一行說明、狀態（一般、完成、輪到你）。
- 日期用等寬數字；圓點顏色照狀態。
""", """<div class="lm-pad"><ol class="lm-timeline">
  <li><span class="when">2026-10-07</span><span class="dot ok"></span><span class="what">② 凍結<small>tag hire-employee/02-v1</small></span></li>
  <li><span class="when">2026-10-14</span><span class="dot"></span><span class="what">③ 送審<small>審查頁 reviews/2026-10-14_03.md</small></span></li>
  <li><span class="when">2026-10-16</span><span class="dot turn"></span><span class="what">等你回答 2 題<small>到職日更正要不要重算特休</small></span></li>
</ol></div>""")

comp("Chip","狀態",96,"""膠囊：小型狀態或分類標籤，圓點加字。

- 提供：一到六個字。
- 預設是藍（一般資訊）；`ok` 完成、`turn` 輪到你、`hint` 提示、`bad` 錯誤、`busy` 進行中（圓點閃爍）。
- 不靠顏色單獨表示狀態：字一定寫出來。
""", """<div class="lm-pad"><div class="lm-row">
  <span class="lm-chip">建議</span><span class="lm-chip ok">已凍結</span><span class="lm-chip turn">輪到你</span>
  <span class="lm-chip hint">支線</span><span class="lm-chip bad">不通過</span><span class="lm-chip busy">全自動進行中</span>
</div></div>""")

comp("StatusMark","狀態",110,"""狀態圓：✓ 通過、✕ 不通過、! 要處理，實色圓配白色符號，旁邊一定接文字。

- 提供：狀態與一句說明。
- 用在檢查結果、審查結論、對照的標題。
""", """<div class="lm-pad"><div class="lm-row" style="gap:24px">
  <span class="lm-status"><span class="lm-mark ok" aria-hidden="true">✓</span>lint 通過</span>
  <span class="lm-status"><span class="lm-mark bad" aria-hidden="true">✕</span>2 項格式錯誤</span>
  <span class="lm-status"><span class="lm-mark turn" aria-hidden="true">!</span>1 題等你回答</span>
</div></div>""")

comp("Option","輸入",300,"""選擇題選項：每個選項一張卡片，左上字母、粗體做法、灰字結果；建議答案用淡藍底，選中加 2px 藍框。

- 提供：字母、做法、結果；哪一個是建議。
- 建議答案放第一個，標「建議」膠囊。
- 選中的狀態除了框線，標題列也寫「已選」。
""", """<div class="lm-pad"><div class="lm-h3">到職日更正後，已經給的特休要不要重算？</div><div class="lm-opts">
  <button class="lm-opt rec"><span class="lm-row"><span class="k">A</span><span class="lm-chip plain">建議</span></span><b>重算並留下更正事件</b><span class="out">→ 特休天數跟著到職日變，舊的結果仍查得到。</span></button>
  <button class="lm-opt on" aria-pressed="true"><span class="lm-row"><span class="k">B</span><span class="lm-chip ok">已選</span></span><b>不重算，只記差異</b><span class="out">→ 已給的天數不變，由人工決定要不要補。</span></button>
  <button class="lm-opt"><span class="k">C</span><b>看情況</b><span class="out">→ 另外寫一條規則決定。</span></button>
</div></div>""")

comp("TextField","輸入",130,"""輸入框：白底、1px `line-strong` 邊、`radius-md` 圓角；聚焦時 2px `accent-strong` 外框。

- 提供：標籤、提示文字。
- 標籤寫在框外上方，不只靠 placeholder。
""", """<div class="lm-pad"><div class="lm-field" style="max-width:520px">
  <label for="why">你的意見（選「其他」時填）</label>
  <input class="lm-input" id="why" type="text" placeholder="例：離職後 3 個月內回任，年資接續">
</div></div>""")

for n,(g,h,readme,body) in C.items():
    d=f"project/components/{n}"; os.makedirs(d,exist_ok=True)
    open(f"{d}/README.md","w").write(f"# {n}\n\n{readme}")
    open(f"{d}/preview.html","w").write(f'<!-- @dsCard group="{g}" height={h} -->\n<!doctype html>\n<html lang="zh-Hant">\n<head><meta charset="utf-8"><title>{n}</title></head>\n<body class="lm-bg">\n{body}\n</body>\n</html>\n')
print(len(C))
