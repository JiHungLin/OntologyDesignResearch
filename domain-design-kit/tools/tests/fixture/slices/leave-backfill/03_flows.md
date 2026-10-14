# leave-backfill ③ 流程與狀態

## 狀態機

### LeaveRequest（請假申請）（歷史需求：需要軌跡，依 Q03）
狀態：Pending（待審）→ Approved（已核准）／Rejected（已駁回）
終態：Approved、Rejected

| 從 | 到 | 觸發事件 | 誰可以做 | 前提條件 | 規則 |
|---|---|---|---|---|---|
| （無） | Pending | SubmitLeaveRequest | 員工 | — | |
| Pending | Approved | ApproveLeave | 該店店長 | 額度足夠 | R01 |
| Pending | Rejected | RejectLeave | 該店店長 | — | |

## 事件

| 事件 | 觸發來源 | 層 | 主體 | 改變什麼 | 證據 | 能否撤銷 | 有意義的時間 |
|---|---|---|---|---|---|---|---|
| SubmitLeaveRequest（提出請假） | 人的動作 | 要求 | LeaveRequest | （無）→ Pending | — | 可撤回 | 發生、得知 |
| ApproveLeave（核准請假） | 人的動作 | 決定 | LeaveRequest | Pending → Approved | — | 不可撤銷 | 發生、得知 |
| RejectLeave（駁回請假） | 人的動作 | 決定 | LeaveRequest | Pending → Rejected | 駁回理由 | 不可撤銷 | 發生、得知 |
| ProposeLeaveTiming（產生休假建議） | 時間或條件到達 | 建議 | LeaveRequest | 不改變狀態 | 剩餘天數 | 可作廢 | 得知 |

## 更正方式

| 對象 | 更正事件 | 誰發現 | 誰核准 | 與原紀錄的關係 |
|---|---|---|---|---|
| LeaveOccurrence | CorrectLeaveOccurrence | 員工或人資 | 人資主管 | 原紀錄保留並標為已更正 |
