---
name: domain-check
description: 從 Markdown 交付物轉出 .build/ 的 YAML，跑檢查工具與引用檢查。使用者說「檢查一下」「有沒有漏」「有沒有衝突」時使用；第 ②～④ 步自評前也會自動使用。
argument-hint: "[切片代號]"
---

# 檢查

1. **轉出 YAML**：讀 `docs/05` 2.1 的對照表與各階段的 YAML 格式，把 `core/` 與目前切片的 Markdown 合併轉成：
   `.build/cq.yaml`、`.build/entities.yaml`、`.build/relations.yaml`、`.build/glossary.yaml`、`.build/flows.yaml`、`.build/rules.yaml`、`.build/mappings.yaml`（只轉已有內容的）。
   - 只轉換，不補內容。Markdown 沒寫的欄位就不寫；需要推測的欄位（例：驗收問題的 `subject`、`answer_type`），在回報中列出你的推測，請人確認。
   - 不修改任何 Markdown。
2. **執行工具**：
   ```bash
   python3 tools/check.py --step <目前的步驟>
   python3 tools/derive.py > .build/invariants.derived.yaml
   ```
3. **引用檢查**：逐條執行 `docs/02` 第七節的表，只檢查目前已存在的交付物。表中「方式」欄標「程式」的項目目前還沒有程式，由你逐條比對；標「AI 判斷」的要讀內容判斷。
4. **回報**：
   - 結果寫成「結構檢查：紅燈 n 項、未檢查 m 項」，不要只寫「紅燈 0 項」或「通過」。
   - 每項紅燈：哪個檔案、哪一項、建議怎麼修。
   - 每項「未檢查」：缺哪個檔案或沒有資料，是本來就不需要（例：還沒到那一步、沒有子類），還是轉換漏了。
   - 第七節：哪幾項比對過、結果；哪幾項不適用。
   - **這個檢查沒有涵蓋的範圍**：規則條件是否正確、是否與法條原文相符、狀態機是否漏了轉換、屬性能不能撐住多次發生、決定的來源是否寫對。這些要靠挑錯與審查。
   - 推導出的結構不變量數量；有沒有「必要但推不出來」的約束。
   - 轉換時做的推測。
   - `.build/` 不提交。
