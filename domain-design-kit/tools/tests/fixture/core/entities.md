# 共用核心：Entity

### Person（人） [候選]
- 出處：annual-leave（② @ annual-leave/02-v1）
- 層：core
- 定義：一個真實的人
- 身分：由系統指定編號
- 何時開始：第一次被登錄
- 何時結束：不結束
- 不是什麼：不是員工
- 不能跟誰合併：Employment —— 離職後人還在
- 主要屬性：
  - `birth_date`（出生日）
- 對應驗收問題：annual-leave:Q01
- 被引用：leave-backfill
