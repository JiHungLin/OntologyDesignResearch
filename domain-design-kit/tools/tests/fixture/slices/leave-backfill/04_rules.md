# leave-backfill ④ 規則與限制

## 規則

| 編號 | 規則 | 種類 | 套用對象 | 判斷方式 | 違反時 | 來源 | 版本／生效日 | 核對 |
|---|---|---|---|---|---|---|---|---|
| R01 | 同一人一年內 `LeaveOccurrence.leave_type` 為事假的 `LeaveOccurrence.hours` 合計不超過 14 日 | 前提條件 | ApproveLeave | 可自動判斷 | 擋下 | 勞工請假規則 §7 | 2024-01-01 起 | ○○，對照原文，2026-09-30 |
| R02 | 依 `Person.birth_date` 算出未滿 16 歲者不能請假 [解讀: 童工另依特別規定] | 前提條件 | ApproveLeave | 看條件（年齡） | 提醒 | 業務需求 | — | [未核對] |
| R03 | [已取消: X-04] 事假須於前一日申請 | — | — | — | — | — | — | — |

## 詞彙對照表新增

| ID | 種類 | 定義 | zh-TW | 對照備註 |
|---|---|---|---|---|

## 分類值

| 代碼 | 屬於 | 管轄區 | zh-TW | 對照備註 |
|---|---|---|---|---|
| LEAVE_TYPE.PERSONAL_TW | LEAVE_TYPE | TW | 事假 | |
| LEAVE_TYPE.SICK_TW | LEAVE_TYPE | TW | 病假 | |
