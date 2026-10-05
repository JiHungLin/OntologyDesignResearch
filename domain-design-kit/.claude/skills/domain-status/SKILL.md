---
name: domain-status
description: 從檔案重建 Domain 設計的目前狀態（各切片各步驟的狀態、tag、待回覆的專家問題、下一步）。每次新 session 開始工作前先執行。
argument-hint: "[切片代號]"
---

# 重建目前狀態

你沒有之前對話的記憶，所有狀態都從檔案讀出。不要猜。

1. 列出 `slices/` 下的切片；有指定 `$ARGUMENTS` 就只看那一條。
2. 對每條切片：
   - 讀每份交付物開頭區的「狀態」「版本」（`01_scope.md`～`05_mapping.md`、`06_evidence/signoff.md`）。檔案不存在＝尚未開始。
   - `git tag --list '<切片>/*'`：對照開頭區的版本；兩者不一致時報告出來。
   - 讀 `CHANGELOG.md` 最上面三筆。
   - 讀 `questions.md`：列出狀態為「待問」「已問」的問題。
   - 搜尋 `[待專家確認`、`[未核對]`、`[未執行]` 的數量。
   - `git status --short slices/<切片>`：有沒有未提交的修改。
3. 讀 `core/` 各檔，統計 `[候選]`、`[已驗證]`、`[已驗證（暫代）]` 的數量。
4. 判斷下一步：
   - 有步驟是「待檢查」→ 等人審查，提醒審查後執行 `/domain-freeze <步驟>`。
   - 有步驟是「草稿」→ 那一步還沒完成，可用 `/domain-step <步驟>` 繼續。
   - 最後一個已凍結的是第 N 步 → 下一步是 `/domain-step <N+1>`。
   - 有已回覆但未處理的專家問題（狀態「已回覆」但「處理」欄空白）→ 先執行 `/domain-expert-reply`。

## 回報格式

```
切片 leave-backfill（模式：完整）
  ① 已凍結 leave-backfill/01-v1
  ② 待檢查 —— 等人審查
  ③～⑥ 未開始
  專家問題：EQ-002 已問（兼職跨店特休）
  標記：[待專家確認] 2、[未核對] 0
  未提交的修改：無
core/：候選 6、已驗證 0
下一步：審查 02_entities.md 後執行 /domain-freeze 2
```
