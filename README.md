# OntologyDesignResearch

一套用 Claude Code 跑 **Domain 設計**的工具包：把一個業務領域（例：人資）從現實整理成系統設計。AI 負責產出與自我挑錯，你負責提供資料、審查、做決定。

**使用的人不需要先讀任何文件**，照下面做就好。

---

## 怎麼用

**1. 把工具包複製到一個新的 repo**

複製的是 `domain-design-kit/` 資料夾**裡面的東西**，要放在新 repo 的**最上層**：

```bash
mkdir -p ~/projects/hr-domain-design
cp -r domain-design-kit/. ~/projects/hr-domain-design/    # 結尾的 /. 會連隱藏的 .claude/、.gitignore 一起複製
cd ~/projects/hr-domain-design
rm build_kit.py
git init && git add . && git commit -m "Domain 設計工具包"
claude
```

複製完，新 repo 的最上層要看得到 `CLAUDE.md` 和 `.claude/`；如果它們在 `domain-design-kit/` 裡面，Claude Code 會讀不到規則。

**2. 直接用說的**

```
我們要做連鎖飲料店的人資系統
```

AI 會問你問題、找資料、和你一起決定分成哪幾段來做，每做完一步就停下來等你審查。之後說「繼續」「現在做到哪？」「審查好了」「專家回覆了：……」就行。

更多說法和你要負責的事，見 [`domain-design-kit/README.md`](domain-design-kit/README.md)。

---

## 用網頁操作（web-ui）

不想在終端機打字，可以改用網頁：每個「輪到 AI」的地方是一個按鈕，AI 在背景跑；審查頁的題目變成選擇題卡片，模型與狀態圖畫成圖。網頁只是操作介面，設計內容都在設計 repo 的檔案裡，關掉網頁照樣能用終端機繼續。

**需要**：Python 3.10 以上、已登入的 Claude Code（`claude` 指令）、Chrome 或 Firefox。

**1. 安裝**

```bash
cd domain-design-web
pip install -r requirements.txt
```

**2. 啟動**

```bash
# 新的 domain：在空資料夾建立設計 repo（會複製工具包、git init）
python3 server.py --repo ~/projects/hr-domain-design --init

# 已有的設計 repo（例如照上面「怎麼用」複製出來的）
python3 server.py --repo ~/projects/hr-domain-design

# 換 port，或讓同一個網路的其他電腦也能開
python3 server.py --repo ~/projects/hr-domain-design --port 8768 --host 0.0.0.0
```

打開 http://127.0.0.1:8765/ （預設 port 8765）。用 `--host 0.0.0.0` 時，終端機會列出區網網址。網頁**沒有登入機制**，同一個網路的人都能打開、叫 AI 修改設計 repo，只在信任的網路上用。

**3. 照總覽的大按鈕走**

總覽最上面一律寫著「現在輪到誰、做什麼」，照著按就好：

1. **主題草案**：用自己的話寫想做什麼、給誰用，交給 AI 規劃。
2. **規劃**：補資料、看推想草稿、同意切片地圖。
3. **一條一條切片**：每一步交給 AI 產出；輪到你時，在審查頁一題一題作答、算黃金案例、抽查、簽名，再請 AI 凍結。
4. **專家問題**：可以複製給專家；專家回覆了，貼上原話交給 AI。

**全自動**（先試用）：在「規劃」把執行模式切成全自動後，左側會出現「全自動」頁。AI 會一路做完所有切片，人的關卡由 AI 代答，不能自己決定的留在「全自動留給你的決定」。預設設定：每條只做到 ⑤、每 3 條停一次、最多 200 圈。碰到用量上限會等到重置後接著跑。

畫面、全自動的細節與 API 見 [`domain-design-web/README.md`](domain-design-web/README.md)。

---

## 想了解流程的人

不需要讀，但想知道背後在做什麼時可以看：

- [Domain 設計心法精華版](https://claude.ai/artifact/YJ5RrTAownYBGb28tiR1tV)：一頁讀完，每個階段為什麼要做
- [六步開發流程](https://claude.ai/artifact/BTkJn9DNAbTQdKB98NL4xi)：每一步交什麼、怎樣算完成
- [Domain 設計心法](https://claude.ai/artifact/NYTNBtchjCAE4ZLZXy2JkY)：完整版

---

## 維護工具包的人

### 正本文件

| 文件 | 內容 |
|---|---|
| [`團隊開發流程_精簡版.md`](團隊開發流程_精簡版.md) | Domain 設計規範：流程的正式依據 |
| [`Domain設計輸入輸出規範.md`](Domain設計輸入輸出規範.md) | 每份交付物的格式、編號、標記 |
| [`平台架構約定.md`](平台架構約定.md) | 平台層級決定一次的事（P1～P13） |
| [`本體論設計指南.md`](本體論設計指南.md) | 詳細手冊：判斷準則、YAML 格式、檢查工具 |
| [`Domain設計心法.md`](Domain設計心法.md)、[`Domain設計心法_精華版.md`](Domain設計心法_精華版.md) | 每個階段的目的 |
| `團隊開發流程.html`、`Domain設計心法.html`、`Domain設計心法_精華版.html` | 上面三個網頁的原始檔 |

衝突時：內容以精簡版為準，格式以輸入輸出規範為準，平台決定以平台架構約定為準。

### 修改流程時

1. 改正本，並檢查其他文件有沒有衝突。
2. 在 [`團隊開發流程_對抗性審查.md`](團隊開發流程_對抗性審查.md) 記下改了什麼、為什麼。
3. 在 `domain-design-kit/` 執行 `python3 build_kit.py`，重建規範副本與範本的檢查清單（`domain-design-kit/docs/` 是副本，不要直接改）。
4. 改到 `.html` 的，重新發布網頁。
5. 已經在使用的設計 repo 不會自動更新，需要手動複製新版工具包檔案。

### 研究與紀錄

| 文件 | 內容 |
|---|---|
| [`Ontology輸入輸出定義_依Sean原始材料.md`](Ontology輸入輸出定義_依Sean原始材料.md) | 依 Sean 原始材料整理的 Ontology 輸入與輸出 |
| [`Sean三層架構與八步八元素對照.md`](Sean三層架構與八步八元素對照.md) | Define／Preserve／Prove 三層、八個步驟、八元素的對照 |
| [`Entity判斷問題驗證.md`](Entity判斷問題驗證.md) | 第 ② 步判斷 Entity 的六問：40 個案例的驗證與修正過程 |
| [`DoubleDiamond研究.md`](DoubleDiamond研究.md) | Double Diamond 的版本演進與 Sean 的用法 |
| [`團隊開發流程_對抗性審查.md`](團隊開發流程_對抗性審查.md) | 流程的反方審查與所有修改的理由 |
| [`AI協作方式分析報告.md`](AI協作方式分析報告.md) | 研究過程中與 AI 協作方式的分析 |

### 原始材料

Sean 的會議逐字稿、簡報與對話紀錄（`Sean會議記錄/`、`sean_ontology_conversation/`、`SeanHRSystemWay/`）只放在本機，不納入本 repo（見 `.gitignore`）。引用 Sean 的說法時，一律指向原始材料的檔名與時間戳記。
