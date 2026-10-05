---
name: domain-check
description: 從 Markdown 交付物轉出 .build/ 的 YAML，執行 tools/ 的檢查與推導，並逐條執行輸入輸出規範第七節的引用檢查。
argument-hint: "[切片代號]"
---

# 檢查

1. **轉出 YAML**：讀 `docs/05` 2.1 的對照表與各階段的 YAML 格式，把 `core/` 與目前切片的 Markdown 合併轉成：
   `.build/cq.yaml`、`.build/entities.yaml`、`.build/relations.yaml`、`.build/glossary.yaml`、`.build/flows.yaml`、`.build/rules.yaml`、`.build/mappings.yaml`（只轉已有內容的）。
   - 只轉換，不補內容。Markdown 沒寫的欄位就不寫；需要推測的欄位（例：驗收問題的 `subject`、`answer_type`），在回報中列出你的推測，請人確認。
   - 不修改任何 Markdown。
2. **執行工具**：
   ```bash
   python3 tools/check.py
   python3 tools/derive.py > .build/invariants.derived.yaml
   ```
3. **引用檢查**：逐條執行 `docs/02` 第七節的表，只檢查目前已存在的交付物。
4. **回報**：
   - 每項紅燈：哪個檔案、哪一項、建議怎麼修。
   - 推導出的結構不變量數量；有沒有「必要但推不出來」的約束。
   - 轉換時做的推測。
   - `.build/` 不提交。
