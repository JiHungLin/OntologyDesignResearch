#!/usr/bin/env python3
"""工具測試：python3 tools/tests/test_tools.py
用 tools/tests/fixture/（範例切片 leave-backfill）當測試資料：原樣要全部通過；
每個測試改壞一處，確認工具抓得到。"""
import os, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, 'fixture')
SLICE = 'leave-backfill'

def run(tool, *args, cwd):
    p = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args],
                       cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copytree(FIXTURE, self.dir, dirs_exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def edit(self, rel, old, new):
        p = os.path.join(self.dir, rel)
        with open(p, encoding='utf-8') as f:
            s = f.read()
        self.assertIn(old, s, f'測試資料裡找不到要改的文字：{old}')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(s.replace(old, new, 1))

    def build(self):
        return run('md2build.py', SLICE, cwd=self.dir)

    def slice_file(self, name):
        return f'slices/{SLICE}/{name}'

class TestMd2build(Base):
    def test_fixture_converts_cleanly(self):
        code, out = self.build()
        self.assertEqual(code, 0, out)
        self.assertIn('驗收問題 3；Entity 4（本切片新增 3）、屬性 6；關係 3', out)
        self.assertIn('狀態機 1、事件 4、更正方式 1；規則 3', out)

    def test_several_codes_in_one_row(self):
        self.edit(self.slice_file('04_rules.md'), '| LEAVE_TYPE.SICK_TW |',
                  '| LEAVE_TYPE.SICK_TW～LEAVE_TYPE.FAMILY_TW |')
        code, out = self.build()
        self.assertEqual(code, 2, out)
        self.assertIn('一列只寫一個代碼', out)

    def test_legacy_cancel_marker(self):
        self.edit(self.slice_file('04_rules.md'), '[已取消: X-04]', '〔已取消，X-04〕')
        code, out = self.build()
        self.assertEqual(code, 2, out)
        self.assertIn('[已取消: <依據>]', out)

    def test_option_outside_list(self):
        self.edit(self.slice_file('04_rules.md'), '| 可自動判斷 | 擋下 |', '| 自動 | 擋下 |')
        code, out = self.build()
        self.assertEqual(code, 2, out)
        self.assertIn('判斷方式「自動」不在固定選項內', out)

    def test_option_with_note_is_accepted(self):
        code, out = self.build()          # R02 寫「看條件（年齡）」
        self.assertEqual(code, 0, out)

    def test_rule_in_glossary_is_a_warning(self):
        self.edit(self.slice_file('04_rules.md'), '| ID | 種類 | 定義 | zh-TW | 對照備註 |\n|---|---|---|---|---|\n',
                  '| ID | 種類 | 定義 | zh-TW | 對照備註 |\n|---|---|---|---|---|\n| R01 | 規則 | 事假一年上限 | 事假上限 | |\n')
        code, out = self.build()
        self.assertEqual(code, 0, out)
        self.assertIn('規則不登錄在詞彙對照表', out)

    def test_column_count_mismatch(self):
        self.edit(self.slice_file('02_entities.md'), '| 0..1 | 無 | 急診可以沒有事前申請 |',
                  '| 0..1 | 急診可以沒有事前申請 |')
        code, out = self.build()
        self.assertEqual(code, 2, out)
        self.assertIn('欄數不對', out)

    def test_attribute_without_identifier(self):
        self.edit(self.slice_file('02_entities.md'), '  - `hours`（時數）', '  - 時數')
        code, out = self.build()
        self.assertEqual(code, 2, out)
        self.assertIn('屬性沒有用 `英文識別名稱` 開頭', out)

class TestCheck(Base):
    def check(self, *args):
        return run('check.py', *args, cwd=self.dir)

    def test_fixture_passes(self):
        self.build()
        code, out = self.check('--step', '4')
        self.assertEqual(code, 0, out)
        self.assertIn('結構檢查：紅燈 0 項', out)
        self.assertIn('檢查了 3 個屬性引用', out)

    def test_rule_refers_to_missing_attribute(self):
        self.edit(self.slice_file('04_rules.md'), '`LeaveOccurrence.hours`', '`LeaveOccurrence.minutes`')
        self.build()
        code, out = self.check('--step', '4')
        self.assertEqual(code, 1, out)
        self.assertIn('R01 判別 LeaveOccurrence.minutes', out)

    def test_missing_file_is_not_a_pass(self):
        self.build()
        os.remove(os.path.join(self.dir, '.build', 'cq.yaml'))
        code, out = self.check()
        self.assertIn('未檢查（缺 .build/cq.yaml', out)
        code, out = self.check('--step', '4')
        self.assertEqual(code, 1, out)
        self.assertIn('✗ 缺 .build/cq.yaml', out)

    def test_cancelled_rule_is_not_checked_for_attributes(self):
        self.edit(self.slice_file('04_rules.md'), '[已取消: X-04] 事假須於前一日申請',
                  '[已取消: X-04] `LeaveOccurrence.gone` 須於前一日申請')
        self.build()
        code, out = self.check('--step', '4')
        self.assertEqual(code, 0, out)

class TestLint(Base):
    def lint(self, *args):
        return run('lint.py', SLICE, *args, cwd=self.dir)

    def test_fixture_passes(self):
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('引用檢查：紅燈 0 項', out)

    def test_cancelled_rule_still_referenced(self):
        self.edit(self.slice_file('03_flows.md'), '| 額度足夠 | R01 |', '| 額度足夠 | R01、R03 |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('R03 已取消，仍被引用：03_flows.md', out)

    def test_cancelled_decision_still_referenced(self):
        self.edit(self.slice_file('01_scope.md'), '| Q03 | 這次請假是誰核准的？',
                  '| Q03 | 這次請假是誰核准的？（見 D-02）')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('01_scope.md 的 D-02 已取消', out)

    def test_decision_of_another_file_is_not_confused(self):
        self.edit(self.slice_file('01_scope.md'), '| Q03 | 這次請假是誰核准的？',
                  '| Q03 | 這次請假是誰核准的？（見 PLAN.md D-02）')
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_use_case_uses_undeclared_event(self):
        self.edit(self.slice_file('03_use_cases.md'), '- 用到的事件：SubmitLeaveRequest、ApproveLeave',
                  '- 用到的事件：SubmitLeaveRequest、ApproveLeave、CancelLeave')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('UC-01 用到的事件 CancelLeave 沒有宣告', out)

    def test_missing_expert_question(self):
        self.edit(self.slice_file('01_scope.md'), '[待專家確認: EQ-001]', '[待專家確認: EQ-009]')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('EQ-009 不在 questions.md', out)

    def test_term_missing_from_glossary(self):
        self.edit(self.slice_file('03_flows.md'), '| RejectLeave | 事件 | 駁回請假 | 駁回請假 | |\n', '')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('事件 1 個不在詞彙對照表：RejectLeave', out)

    def test_unknown_marker(self):
        self.edit(self.slice_file('02_entities.md'), '| Person | [候選] [引用候選] |', '| Person | [候選] [待確認] |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('「[待確認]」不是規定的標記', out)

    def test_missing_input_file(self):
        os.remove(os.path.join(self.dir, 'inputs', SLICE, '訪談_0930.md'))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('訪談_0930.md 不存在', out)

    def test_proposal_event_changes_state(self):
        self.edit(self.slice_file('03_flows.md'), '| 建議 | LeaveRequest | 不改變狀態 |', '| 建議 | LeaveRequest | Pending → Approved |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('ProposeLeaveTiming 是建議層，卻改變狀態', out)

    def test_renamed_attribute_left_behind(self):
        base = os.path.join(self.dir, 'baseline')
        shutil.copytree(os.path.join(self.dir, 'slices', SLICE), base)
        p = os.path.join(base, '02_entities.md')
        with open(p, encoding='utf-8') as f:
            s = f.read()
        with open(p, 'w', encoding='utf-8') as f:
            f.write(s.replace('`hours`（時數）', '`minutes`（分鐘數）'))
        self.edit(self.slice_file('03_flows.md'), '| 額度足夠 |', '| 額度足夠（看 minutes） |')
        code, out = self.lint('--baseline', base)
        self.assertEqual(code, 1, out)
        self.assertIn('屬性 LeaveOccurrence.minutes 已不在目前的定義中，仍出現在 03_flows.md', out)

    def test_extra_table_column_is_red(self):
        self.edit(self.slice_file('01_scope.md'), '| Q01 | ', '| Q01 | | ')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('欄數不對', out)
        self.assertNotIn('引用檢查：紅燈 0 項', out)

    def test_pending_decision_blocks_freeze(self):
        self.edit(self.slice_file('01_scope.md'), 'AI／○○（2026-10-06） |\n| D-02', 'AI／待確認 |\n| D-02')
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('D-01 待確認', out)
        code, out = self.lint('--freeze')
        self.assertEqual(code, 1, out)

    def write(self, rel, text):
        p = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)

    def test_placeholder_left_in_slice(self):
        self.edit(self.slice_file('01_scope.md'), '## 驗收問題', '## 驗收問題\n\n{{切片}} 的問題')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('還有範本的佔位符', out)

    def test_expert_question_impact_not_backfilled(self):
        self.edit(self.slice_file('questions.md'), '| 01_scope Q02 |', '| 02_entities Employment |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('01_scope.md:14 的 EQ-001 在 Q02，questions.md 的「影響」沒有列出', out)

    def test_impact_range_counts(self):
        self.edit(self.slice_file('questions.md'), '| 01_scope Q02 |', '| 01_scope Q01～Q03；內文未標：02_entities Employment |')
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_table_broken_by_blank_line(self):
        self.edit(self.slice_file('01_scope.md'), '\n| Q02 |', '\n\n| Q02 |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('這列不屬於任何表格', out)

    def test_question_status_outside_options(self):
        self.edit(self.slice_file('questions.md'), '| 待問 |', '| 待回覆 |')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('「狀態」的值「待回覆」不在規定的選項', out)

    def test_out_of_scope_owner_must_be_on_map(self):
        self.write('slices/PLAN.md', '# 切片地圖\n\n## 切片\n\n| 切片 | 情境 | 狀態 |\n|---|---|---|\n'
                   '| annual-leave | 事前請特休 | 候選 |\n| leave-backfill | 事後補單 | 進行中 |\n')
        self.edit(self.slice_file('01_scope.md'), '## 草稿 User Story',
                  '## 範圍外但會用到\n\n| 會用到的東西 | 歸屬的切片 | 目前狀態 | 本切片怎麼處理 |\n|---|---|---|---|\n'
                  '| 人 | annual-leave | 候選 | 直接引用 |\n| 薪資扣款 | monthly-payroll 的第 ④ 步 | — | [靜態替代] 扣日薪 |\n\n## 草稿 User Story')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('沒有寫切片地圖上的切片代號', out)
        self.assertEqual(out.count('沒有寫切片地圖上的切片代號'), 1, out)

    def test_parameter_storage_in_mapping(self):
        self.edit(self.slice_file('04_rules.md'), '## 分類值',
                  '## 參數\n\n| 參數 | 意義 | 資料類型 | 合理範圍 | 預設值 | 依什麼條件變化 | 用在 | 來源 | 核對 |\n'
                  '|---|---|---|---|---|---|---|---|---|\n'
                  '| `personal_leave_max_days` | 事假上限 | 天數 | 不少於 14 | 14 | 公司 | R01 | 勞工請假規則 §7 | [未核對] |\n'
                  '| notice_days | 告知期限 | 天數 | — | 30 | — | R01 | 業務需求 | — |\n\n## 分類值')
        mapping = ('# leave-backfill 對照表\n\n## 三、規則 → 落實位置\n\n| 規則 | 落實位置 | 說明 |\n|---|---|---|\n'
                   '| R01 | service | 跨表加總 |\n\n### 參數放在哪裡（P5）\n\n'
                   '| 參數 | 放在 | 沒有設定時的預設值 | 說明 |\n|---|---|---|---|\n'
                   '| `personal_leave_max_days` | 公司規定的版本 | 規則版本（R01）的參數 | 依公司 |\n')
        self.write(self.slice_file('05_mapping.md'), mapping)
        code, out = self.lint()
        self.assertIn('參數 notice_days 沒有列在 05_mapping.md', out)
        self.assertNotIn('參數 personal_leave_max_days 沒有列在', out)
        self.write(self.slice_file('05_mapping.md'), mapping.split('### 參數')[0])
        code, out = self.lint()
        self.assertIn('05_mapping.md 沒有「參數放在哪裡」表（④ 參數表有 2 個參數）', out)

    LATE = ('## 事後才到的輸入\n\n| 已判定或已交出的結果 | 之後才到的輸入 | 案例 | 沒挑的理由 |\n|---|---|---|---|\n'
            '| LeaveRequest.Approved | CorrectRecord：請假起訖 | {} | {} |\n\n')
    GC = ('# leave-backfill 黃金案例\n\n' + LATE.format('GC02', '') +
          '## GC01 正常流程\n- 驗證：Q01\n- 情境：…\n- 紙上判定：{}\n- 判定：{}\n\n'
          '## GC02 候選\n- 驗證：Q02\n- 紙上判定：一致（2026-10-21）\n- 判定：[未執行]\n')

    def test_golden_case_not_adopted(self):
        self.write(self.slice_file('06_evidence/golden_cases.md'), self.GC.format('不採用', '不採用'))
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), self.GC.format('不採用', '[未執行]'))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('GC01 只有一欄寫「不採用」', out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), self.GC.format('沒挑', '沒挑'))
        code, out = self.lint()
        self.assertIn('GC01 的「紙上判定」是「沒挑」', out)

    def test_late_inputs_coverage(self):
        gc = self.GC.format('不採用', '不採用')
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace('| GC02 |  |', '| GC01 | |'))
        code, out = self.lint()
        self.assertIn('GC01 是「不採用」，不算涵蓋', out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace('| GC02 |  |', '| — | |'))
        code, out = self.lint()
        self.assertIn('沒有案例，也沒寫沒挑的理由', out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace('| GC02 |  |', '| — | 同 GC02 的路徑 |'))
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.split('## GC01')[0].replace(self.LATE.format('GC02', ''), '') +
                   '## GC01' + gc.split('## GC01')[1])
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('沒有「事後才到的輸入」表', out)

    CORE_FLOWS = ('# 共用核心：狀態機、事件、更正方式\n\n## 事件（hire-employee）\n\n'
                  '| 事件 | 觸發來源 | 層 | 主體 | 改變什麼 | 證據 | 能否撤銷 | 有意義的時間 | 狀態 | 出處 | 被引用 | 連鎖 |\n'
                  '|---|---|---|---|---|---|---|---|---|---|---|---|\n'
                  '| StartEmployment（到職） | 人的動作 | 發生 | Employment | （無）→ Active | — | 只能更正 | 發生 | [候選] | '
                  'hire-employee（③ @ hire-employee/03-v1） | leave-backfill | {} |\n')
    MAPPING = ('# leave-backfill 對照表\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | {} |\n\n## 二、事件 → API\n\n'
               '### 其他切片事件的連鎖\n\n| 上游事件 | 條件 | 本切片做什麼 | 時機 |\n|---|---|---|---|\n'
               '| StartEmployment | 到職日在過去 | SubmitLeaveRequest | {} |\n')

    def test_chain_written_to_core(self):
        self.write('core/flows.md', self.CORE_FLOWS.format('leave-backfill（SubmitLeaveRequest；同一交易）'))
        self.write(self.slice_file('05_mapping.md'), self.MAPPING.format('已凍結', '同一交易'))
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('檢查了 1 個上游事件', out)
        self.write('core/flows.md', self.CORE_FLOWS.format(''))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('StartEmployment 的「連鎖」沒有 leave-backfill', out)
        self.write(self.slice_file('05_mapping.md'), self.MAPPING.format('待檢查', '馬上'))
        code, out = self.lint()
        self.assertIn('（⑤ 凍結時寫入）', out)
        self.assertIn('「時機」是「馬上」', out)

    def test_core_question_without_slice_prefix(self):
        self.edit('core/entities.md', '- 對應驗收問題：annual-leave:Q01', '- 對應驗收問題：Q01')
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('Q01 沒有切片前綴', out)
        code, out = self.lint('--freeze')
        self.assertEqual(code, 1, out)

    def test_core_referenced_by_missing(self):
        self.edit('core/entities.md', '- 被引用：leave-backfill', '- 被引用：（無）')
        code, out = self.lint()
        self.assertIn('Person 被本切片引用，「被引用」沒有 leave-backfill', out)
        code, out = self.lint('--freeze')
        self.assertEqual(code, 1, out)

    def test_rule_applies_only_to_other_slice_use_case(self):
        self.edit(self.slice_file('04_rules.md'), '| 前提條件 | ApproveLeave | 看條件（年齡）',
                  '| 前提條件 | 查看個資（hire-employee:UC-14、hire-employee:UC-15） | 看條件（年齡）')
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.edit(self.slice_file('04_rules.md'), '查看個資（hire-employee:UC-14、hire-employee:UC-15）', '查看個資')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('R02 的套用對象「查看個資」沒有寫', out)

    # ---------- 審查頁、挑錯、黃金案例自給自足（2026-10-27） ----------
    FLOWS_TAIL = ('\n## 決定與理由\n\n| # | 決定 | 考慮過的替代做法 | 理由 | 依據 | 提出／同意 |\n|---|---|---|---|---|---|\n'
                  '| D-01 | 駁回不可撤銷 | 可撤銷 | 使用者同意 | — | {who} |\n\n### 反例處理\n\n'
                  '| # | 反例 | 來源 | 處理 | 理由或去向 |\n|---|---|---|---|---|\n'
                  '| X-01 | 店長駁回後又想改 | {src} | 拒絕 | 另提一筆 |\n\n## 檢查紀錄\n\n### 完成標準（AI 自評）\n\n'
                  '| 完成標準 | 類 | AI 自評 |\n|---|---|---|\n| 「核准」和「發生」是分開的兩件事 | 品質檢查 | ✓ |\n'
                  '| 有寫更正方式，且沒有任何一步是直接改舊紀錄 | 品質檢查 | 部分：只有一種 |\n\n- 審查頁：reviews/2026-10-27_03.md\n')
    REVIEW = ('# leave-backfill 審查頁：③（2026-10-27）\n\n| 項目 | 內容 |\n|---|---|\n| 這輪的挑錯 | ③ {xs} |\n\n'
              '## 一、要你回答的問題\n\n### 問題 1（③ D-01）\n- 背景：設計目前不可撤銷\n- 問題：駁回之後可以撤銷嗎？\n'
              '- A（建議）：不可以 → D-01 維持\n{b}- 其他：（寫一句）\n- 你的回答：{ans}\n\n'
              '## 二、要你確認的內容\n\n| # | 步驟 | 要看的 | 原文 | 在哪裡 | 確認 |\n|---|---|---|---|---|---|\n'
              '| 1 | ③ | {look} | 「{quote}」 | `03_flows.md:{line}` | {ok} |\n\n'
              '## 四、抽查\n\n| 抽查了哪幾條 | 結果 |\n|---|---|\n| {spot} | |\n\n'
              '## 結論\n\n| 步驟 | 審查者（非產出者） | 日期 | 結論 |\n|---|---|---|---|\n| ③ | {rev} | {date} | {verdict} |\n')

    def setup_review(self, who='AI／待確認', src='AI 挑錯（時間與帳務）', **kw):
        self.edit(self.slice_file('03_flows.md'), '# leave-backfill ③ 流程與狀態\n',
                  '# leave-backfill ③ 流程與狀態\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 待檢查 |\n')
        p = os.path.join(self.dir, self.slice_file('03_flows.md'))
        with open(p, 'a', encoding='utf-8') as f:
            f.write(self.FLOWS_TAIL.format(who=who, src=src))
        line = next(i for i, l in enumerate(open(p, encoding='utf-8').read().split('\n'), 1) if l.startswith('| RejectLeave（駁回請假）'))
        v = dict(xs='X-01', b='- B：可以 → RejectLeave 改成可撤銷\n', ans='', ok='', spot='', rev='', date='', verdict='',
                 look='自評「部分」：有寫更正方式，且沒有任何一步是直接改舊紀錄', quote='RejectLeave（駁回請假） \\| 人的動作', line=line)
        v.update(kw)
        self.write(self.slice_file('reviews/2026-10-27_03.md'), self.REVIEW.format(**v))

    def test_review_page_answered_before_freeze(self):
        self.setup_review()
        code, out = self.lint()
        self.assertNotIn('    ✗', out.split('[審查頁]')[1].split('\n[')[0], out)
        self.assertIn('還有 4 處沒作答', out)
        code, out = self.lint('--freeze')
        self.assertEqual(code, 1, out)
        self.assertIn('還沒作答', out)
        self.setup_review_filled()

    def setup_review_filled(self):
        self.write(self.slice_file('reviews/2026-10-27_03.md'), open(os.path.join(self.dir, self.slice_file('reviews/2026-10-27_03.md')),
                   encoding='utf-8').read().replace('- 你的回答：\n', '- 你的回答：A\n').replace('| 03_flows', '| 03_flows')
                   .replace('` |  |\n', '` | ✓ |\n').replace('|  | |\n', '| 第 1 條 | 符合 |\n').replace('| ③ |  |  |  |', '| ③ | 審查者甲 | 2026-10-27 | 通過 |'))
        self.edit(self.slice_file('03_flows.md'), '| AI／待確認 |', '| AI／審查者甲（2026-10-27） |')
        code, out = self.lint('--freeze')
        self.assertNotIn('還沒作答', out)
        self.assertNotIn('    ✗', out.split('[審查頁]')[1].split('\n[')[0], out)

    def test_review_excerpt_must_match_line(self):
        self.setup_review(quote='CorrectLeaveOccurrence')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('前後 2 行找不到', out)

    def test_review_question_needs_options(self):
        self.setup_review(b='')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('至少還要一個選項', out)

    def test_review_lists_partial_self_check(self):
        self.setup_review(look='更正方式')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('的完成標準沒有列在 reviews/2026-10-27_03.md', out)

    def test_challenge_rows_required(self):
        self.setup_review(src='審查者')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('沒有來源為「AI 挑錯」的反例', out)
        self.setup_review(xs='X-09')
        code, out = self.lint()
        self.assertIn('X-09 不在任何一步的「反例處理」', out)

    def test_user_agreement_reminder(self):
        self.setup_review()
        code, out = self.lint()
        self.assertIn('寫了使用者同意或決定，沒有引用原話', out)

    def test_golden_case_must_be_self_contained(self):
        gc = self.GC.format('[未執行]', '[未執行]').replace('- 情境：…', '- 情境：同 GC02，但改成週末')
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace('| GC02 |  |', '| GC01 | |'))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('GC01 寫了「同 GC02」', out)

    def test_question_status_temporarily_following_user(self):
        self.edit(self.slice_file('questions.md'), '| 待問 | | |', '| 暫依整理 | inputs/leave-backfill/訪談_0930.md（使用者整理，非專家答覆） | |')
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    # ---------- 跨切片修改（2026-10-27） ----------
    OTHER = ('# other ③\n\n## 決定與理由\n\n| # | 決定 | 考慮過的替代做法 | 理由 | 依據 | 提出／同意 |\n|---|---|---|---|---|---|\n'
             '| D-04 | 到職後重新判定 | — | — | — | AI／○○（2026-11-03） |\n')
    LOG = ('# leave-backfill 變更紀錄\n\n{newer}'
           '## 2026-11-03　（未處理）　③ 流程與狀態　其他切片要求\n- 要改什麼：加一個轉換\n- 依據：{ref}\n- 同意者：○○（2026-11-03）\n')

    def test_cross_slice_reference_must_exist(self):
        self.write('slices/other/03_flows.md', self.OTHER)
        self.write(self.slice_file('CHANGELOG.md'), self.LOG.format(newer='', ref='other/03_flows D-04'))
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('檢查了 1 個跨切片引用', out)
        self.write(self.slice_file('CHANGELOG.md'), self.LOG.format(newer='', ref='other/03_flows D-09'))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('03_flows.md 沒有 D-09', out)

    def test_request_from_other_slice_pending_until_handled(self):
        self.write('slices/other/03_flows.md', self.OTHER)
        self.write(self.slice_file('CHANGELOG.md'), self.LOG.format(newer='', ref='other/03_flows D-04'))
        code, out = self.lint()
        self.assertIn('還沒處理：2026-11-03', out)
        newer = '## 2026-11-05　leave-backfill/03-v2　③ 流程與狀態　凍結\n- 改了什麼：加轉換\n- 依據：other/03_flows D-04\n\n'
        self.write(self.slice_file('CHANGELOG.md'), self.LOG.format(newer=newer, ref='other/03_flows D-04'))
        code, out = self.lint()
        self.assertIn('1 件都已處理', out)

class TestSyncCore(Base):
    def sync(self, *args, tags=None):
        return run('sync_core.py', SLICE, '--tags', tags or f'2={SLICE}/02-v1,3={SLICE}/03-v1,4={SLICE}/04-v1', *args, cwd=self.dir)

    def test_first_sync_then_nothing_changes(self):
        code, out = self.sync('--write')
        self.assertEqual(code, 0, out)
        self.assertIn('新增 3：Employment、LeaveOccurrence、LeaveRequest', out)
        core = open(os.path.join(self.dir, 'core/entities.md'), encoding='utf-8').read()
        self.assertIn('### LeaveRequest（請假申請） [候選]', core)
        self.assertIn(f'- 出處：{SLICE}（② @ {SLICE}/02-v1）', core)
        self.assertIn(f'{SLICE}:Q', core)
        self.assertTrue(os.path.exists(os.path.join(self.dir, 'core/rules.md')))
        code, out = self.sync()
        self.assertIn('core/ 不用改', out)

    def test_order_and_spaces_are_not_changes(self):
        self.sync('--write')
        p = os.path.join(self.dir, self.slice_file('03_flows.md'))
        lines = open(p, encoding='utf-8').read().split('\n')
        i = next(k for k, l in enumerate(lines) if l.startswith('| SubmitLeaveRequest'))
        lines[i], lines[i + 1] = lines[i + 1].replace(' | ', '  |  '), lines[i]
        open(p, 'w', encoding='utf-8').write('\n'.join(lines))
        code, out = self.sync()
        self.assertIn('core/ 不用改', out)

    def test_changed_rule_updates_source(self):
        self.sync('--write')
        p = os.path.join(self.dir, self.slice_file('04_rules.md'))
        t = open(p, encoding='utf-8').read()
        i = t.index('| R01 | ') + len('| R01 | ')
        open(p, 'w', encoding='utf-8').write(t[:i] + '（改）' + t[i:])
        code, out = self.sync('--write', tags=f'2={SLICE}/02-v1,3={SLICE}/03-v1,4={SLICE}/04-v2')
        self.assertIn('更新 1（出處改成新 tag）：R01（規則）', out)
        self.assertIn(f'{SLICE}（④ @ {SLICE}/04-v2）', open(os.path.join(self.dir, 'core/rules.md'), encoding='utf-8').read())

class TestTable(Base):
    def test_empty_cells_are_not_merged(self):
        self.edit(self.slice_file('questions.md'), '| 待問 | | |', '| 待問 | | 2026-10-21 |')
        code, out = run('table.py', self.slice_file('questions.md'), '--row', 'EQ-001',
                        '--col', '答覆', '--col', '答覆日', '--col', '影響', cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn('答覆：（空）', out)
        self.assertIn('答覆日：2026-10-21', out)
        self.assertIn('影響：01_scope Q02', out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
