# Domain 設計工具包

讓 Claude Code 依團隊的 Domain 設計規範跑設計：AI 產出交付物、另開子代理挑錯、自評後停下來；人審查、決定、凍結。新的 session 不需要任何先前對話的記憶，規則由 `CLAUDE.md` 自動載入，狀態全部從檔案讀出。

## 開始一個新 repo

```bash
cp -r domain-design-kit/ ~/projects/hr-domain-design   # 複製工具包（含隱藏的 .claude/、.gitignore）
cd ~/projects/hr-domain-design
rm build_kit.py                                       # 只在研究資料夾使用
git init && git add . && git commit -m "Domain 設計工具包"
claude
```

把原始資料放進 `inputs/`：

```
inputs/
├── shared/                    法規與政策原文、既有系統資料（跨切片共用）
└── leave-backfill/            這條切片的訪談紀錄、既有 User Story
```

在 Claude Code 裡：

```
/domain-start leave-backfill 兼職急診補請假，餘額與扣薪正確
```

## 每一步的節奏

```
/domain-step N      AI：讀輸入 → 產出 → 子代理挑錯 → 處理反例 → 自評 → 停下來
        │
        ▼
人：審查者（非產出者）依「檢查紀錄」逐條打勾，填審查者、日期、結論
        │
        ▼
/domain-freeze N    AI：寫 CHANGELOG → commit → 打 tag → ②③④ 合併進 core/（候選）
        │
        ▼
/domain-step N+1
```

每次開新的 session，先執行 `/domain-status`。

## 指令

| 指令 | 用途 |
|---|---|
| `/domain-status [切片]` | 從檔案重建狀態：各步驟、tag、待回覆的專家問題、下一步 |
| `/domain-start <代號> <情境>` | 建立切片，開始第 ① 步 |
| `/domain-step <1-6> [切片]` | 執行一步，產出後停下等審查 |
| `/domain-freeze <1-6> [切片]` | 審查通過後凍結 |
| `/domain-expert-reply <EQ-nnn> <答覆>` | 處理專家回覆，必要時提出回頭方案 |
| `/domain-change <描述>` | 切片通過後發現特例或錯誤，判斷等級 0～3 |
| `/domain-check [切片]` | 轉出 YAML，跑檢查工具與引用檢查 |

## 人要做的事

| 時點 | 誰 | 做什麼 |
|---|---|---|
| 每一步產出後 | 非產出者的審查者 | 依「檢查紀錄」逐條打勾，填審查者、日期、結論 |
| 第 ①④⑥ 步（至少） | Domain 專家 | 回答 `questions.md` 的問題；確認範圍、規則、黃金案例 |
| 第 ④ 步 | 人 | 對照原文核對規則，把 `[未核對]` 換成核對紀錄 |
| 第 ⑤ 步 | 人 | 先確認對照表，AI 才產生 schema 與 API |
| 第 ⑥ 步 | 人 | 以獨立於系統的方式算出黃金案例的預期結果；執行者與簽核者分開 |
| `core/` 有修改時 | 核心負責人 | 審閱並核准 |

## 內容

| 路徑 | 內容 |
|---|---|
| `CLAUDE.md` | AI 的工作規則（自動載入） |
| `.claude/skills/` | 上面七個指令 |
| `docs/` | 規範文件（唯讀），從研究資料夾複製 |
| `templates/` | 交付物範本（唯讀） |
| `tools/` | `check.py`、`derive.py`、`impact.py` |
| `inputs/` | 原始輸入（唯讀） |

## 維護（在 OntologyResearch 內）

規範文件的正本在 OntologyResearch 根目錄。修改正本後，在 `domain-design-kit/` 執行：

```bash
python3 build_kit.py
```

它會把五份規範複製到 `docs/`，並把《團隊開發流程_精簡版》各步驟的完成標準重新寫進範本的「檢查紀錄」。已經開始跑的設計 repo 不會自動更新；要更新時，手動複製新的 `docs/`、`templates/`，並在該 repo 的 `core/CHANGELOG.md` 記一筆。
