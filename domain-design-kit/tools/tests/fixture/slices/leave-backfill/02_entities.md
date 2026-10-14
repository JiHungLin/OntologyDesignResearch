# leave-backfill ② 名詞盤點

## 引用

| Entity | core 狀態 | 本切片怎麼用 |
|---|---|---|
| Person | [候選] [引用候選] | 請假的人 |

## 新增

### Employment（僱傭關係）
- 定義：一個人與雇主之間的一段僱傭關係
- 身分：由系統指定編號
- 何時開始：到職日
- 何時結束：離職日
- 不是什麼：不是人
- 不能跟誰合併：Person —— 回任時是新的一段
- 主要屬性：
  - `start_date`（到職日）
- 對應驗收問題：Q01

### LeaveOccurrence（請假事實）
- 定義：員工在某個已排定的班次實際沒有出勤，且屬於某種假別
- 身分：由系統指定編號；同一個人在同一個班次只有一筆
- 何時開始：該班次時段實際未出勤
- 何時結束：不結束（歷史事實），只能被更正
- 不是什麼：不是請假申請（LeaveRequest）；不是剩餘天數
- 不能跟誰合併：LeaveRequest —— 可以沒有申請就發生（急診）
- 主要屬性：
  - `hours`（時數）
  - `leave_type`（假別，分類值 LEAVE_TYPE）
  - `balance_after`（扣除後餘額）[推導]
- 對應驗收問題：Q01、Q02

### LeaveRequest（請假申請）
- 定義：員工提出、等待核准的請假
- 身分：由系統指定編號
- 何時開始：員工送出
- 何時結束：核准、駁回或撤回
- 不是什麼：不是請假事實
- 不能跟誰合併：LeaveOccurrence —— 申請可以被駁回
- 主要屬性：
  - `requested_hours`（申請時數）
- 對應驗收問題：Q02、Q03

## 關係

| 從 | 關係 | 到 | 幾對幾 | 有無期間 | 為什麼 |
|---|---|---|---|---|---|
| LeaveOccurrence | requestedVia（由…申請） | LeaveRequest | 0..1 | 無 | 急診可以沒有事前申請 |
| LeaveOccurrence | of（屬於） | Employment | 1 | 無 | 請假屬於一段僱傭關係 |

## 不是 Entity

| 名稱 | 其實是 | 理由 |
|---|---|---|
| 剩餘天數 | 推導值 | 刪掉後可由取得、使用、調整還原 |

## 詞彙對照表新增

| ID | 種類 | 定義 | zh-TW | 對照備註 |
|---|---|---|---|---|
| Employment | Entity | 一段僱傭關係 | 僱傭關係 | |
| LeaveOccurrence | Entity | 員工在已排定班次實際未出勤 | 請假事實 | |
| LeaveRequest | Entity | 等待核准的請假 | 請假申請 | |
| Employment.start_date | 屬性 | 到職日 | 到職日 | |
| LeaveOccurrence.hours | 屬性 | 請假時數 | 時數 | |
| LeaveOccurrence.leave_type | 屬性 | 假別 | 假別 | |
| LeaveOccurrence.balance_after | 屬性 | 扣除後餘額 | 扣除後餘額 | |
| LeaveRequest.requested_hours | 屬性 | 申請時數 | 申請時數 | |
| requestedVia | 關係 | 請假事實由哪張申請提出 | 由…申請 | |
| of | 關係 | 屬於 | 屬於 | |
