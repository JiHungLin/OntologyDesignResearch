#!/usr/bin/env python3
"""工具測試：python3 tools/tests/test_tools.py
用 tools/tests/fixture/（範例切片 leave-backfill）當測試資料：原樣要全部通過；
每個測試改壞一處，確認工具抓得到。"""
import os, re, shutil, subprocess, sys, tempfile, unittest

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

    def test_frozen_without_tag(self):
        # 檔頭改了「已凍結」但 tag 還沒打：凍結做到一半，亮紅燈；打了 tag 就沒有
        git = lambda *a: subprocess.run(['git', *a], cwd=self.dir, capture_output=True, text=True, check=True)
        git('init', '-q')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x')
        self.edit(self.slice_file('03_flows.md'), '# leave-backfill ③ 流程與狀態\n',
                  '# leave-backfill ③ 流程與狀態\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 已凍結 |\n| 版本 | leave-backfill/03-v1 |\n')
        code, out = self.lint()
        self.assertIn('03_flows.md 檔頭是「已凍結」，但沒有 tag leave-backfill/03-v1', out)
        git('tag', 'leave-backfill/03-v1')
        code, out = self.lint()
        self.assertNotIn('檔頭是「已凍結」', out)

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

    def test_old_checklist_while_submitted(self):
        # 送審中（待檢查）的交付物還是舊格式的檢查紀錄：紅燈；已凍結的不管
        old = '\n## 檢查紀錄\n\n| 完成標準 | AI 自評 | 審查者確認 |\n|---|---|---|\n| 每個事件都有觸發者 | ✓ | ✓（甲） |\n'
        self.edit(self.slice_file('03_flows.md'), '# leave-backfill ③ 流程與狀態\n',
                  '# leave-backfill ③ 流程與狀態\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 待檢查 |\n')
        with open(os.path.join(self.dir, self.slice_file('03_flows.md')), 'a', encoding='utf-8') as f:
            f.write(old)
        code, out = self.lint()
        self.assertIn('檢查紀錄還是舊格式', out)
        self.edit(self.slice_file('03_flows.md'), '| 狀態 | 待檢查 |', '| 狀態 | 已凍結 |')
        code, out = self.lint()
        self.assertNotIn('檢查紀錄還是舊格式', out)

    def test_review_golden_case_one_row(self):
        # ⑥ 一個黃金案例拆成「你算的／設計推出的／系統跑出的」三列：沒作答時紅燈，作答完的舊頁不管
        self.setup_review()
        rp = os.path.join(self.dir, self.slice_file('reviews/2026-10-27_03.md'))
        lines = open(rp, encoding='utf-8').read().split('\n')
        k = next(i for i, l in enumerate(lines) if l.startswith('| 1 |'))
        rows = [f'| {n} | ⑥ | GC01 {w} | 「x」 | `03_flows.md:1` | {{ok}} |' for n, w in ((2, '你算的'), (3, '設計推出的'), (4, '系統跑出的'))]
        self.write(self.slice_file('reviews/2026-10-27_03.md'), '\n'.join(lines[:k + 1] + [r.format(ok='') for r in rows] + lines[k + 1:]))
        code, out = self.lint()
        self.assertIn('GC01 拆成 3 列', out)
        self.write(self.slice_file('reviews/2026-10-27_03.md'), '\n'.join(lines[:k + 1] + [r.format(ok='✓') for r in rows] + lines[k + 1:]))
        code, out = self.lint()
        self.assertNotIn('拆成', out)

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

    def test_review_question_example_and_outcome(self):
        self.setup_review()
        old = os.path.join(self.dir, self.slice_file('reviews/2026-10-27_03.md'))
        text = open(old, encoding='utf-8').read().replace('- B：可以 → RejectLeave 改成可撤銷', '- B：可以')
        self.write(self.slice_file('reviews/2026-10-27_03.md'), text)
        code, out = self.lint()
        self.assertNotIn('沒有「例子」', out)
        self.assertNotIn('沒有用「→」', out)
        os.remove(old)
        self.edit(self.slice_file('03_flows.md'), '- 審查頁：reviews/2026-10-27_03.md', '- 審查頁：reviews/2026-10-28_03.md')
        self.write(self.slice_file('reviews/2026-10-28_03.md'), text)
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('沒有「例子」', out)
        self.assertIn('選項 B 沒有用「→」', out)
        self.write(self.slice_file('reviews/2026-10-28_03.md'), text.replace('- 問題：', '- 例子：小王 3/1 請假被駁回，3/2 店長想改成核准\n- 問題：')
                   .replace('- B：可以\n', '- B：可以 → RejectLeave 改成可撤銷\n'))
        code, out = self.lint()
        self.assertNotIn('沒有「例子」', out)
        self.assertNotIn('沒有用「→」', out)

    def test_golden_case_ask(self):
        # 2026-11-04 起的審查頁：黃金案例要有逐項的「要得出」（編號、最後括號寫格式），情境與要得出不寫 Rnn、D-nn
        self.setup_review()
        old = os.path.join(self.dir, self.slice_file('reviews/2026-10-27_03.md'))
        text = open(old, encoding='utf-8').read()
        os.remove(old)
        self.edit(self.slice_file('03_flows.md'), '- 審查頁：reviews/2026-10-27_03.md', '- 審查頁：reviews/2026-11-04_03.md')
        gc = ('## 三、要你得出結果的黃金案例\n\n### GC01 正常流程\n- 驗證：Q01；R01\n- 情境：小王 3/1 請假，依 R01 核准\n'
              '- 要得出：\n  - 2026-03-01 核准後：剩餘天數\n- 輸入：…\n- 預期結果：\n- 計算過程：\n- 計算者：\n\n')
        head, tail = text.split('## 結論', 1)
        self.write(self.slice_file('reviews/2026-11-04_03.md'), head + gc + '## 結論' + tail)
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('每一項要用 ①② 編號', out.replace('…', ''))
        self.assertIn('沒有在最後的括號寫格式', out)
        self.assertIn('的「情境」寫了 R01', out)
        good = gc.replace('依 R01 ', '').replace('  - 2026-03-01 核准後：剩餘天數', '  - ① 2026-03-01 核准後：剩餘特休天數（日）\n  - ② 同一時點：會不會被擋下（擋下或允許）')
        self.write(self.slice_file('reviews/2026-11-04_03.md'), head + good + '## 結論' + tail)
        code, out = self.lint()
        self.assertNotIn('要得出', out)
        self.write(self.slice_file('reviews/2026-11-04_03.md'), head + good.replace('- 要得出：\n', '- 要算：\n') + '## 結論' + tail)
        code, out = self.lint()
        self.assertIn('沒有「要得出」', out)

    def test_golden_case_copies_multiline(self):
        # 審查頁的計算過程分好幾行寫：不算沒作答；golden_cases.md 逐字抄回後不報「不同」（原本每讀一行就清空，永遠報不同）
        self.setup_review()
        rv = self.slice_file('reviews/2026-10-27_03.md')
        text = open(os.path.join(self.dir, rv), encoding='utf-8').read()
        fields = '- 預期結果：① 6 日\n- 計算過程：\n  - 1. 10 - 4 = 6\n  - 2. 取整數\n- 計算者：○○\n'
        head, tail = text.split('## 結論', 1)
        self.write(rv, head + '## 三、要你算的黃金案例\n\n### GC01 正常流程\n- 驗證：Q01\n- 情境：…\n' + fields + '\n## 結論' + tail)
        gc = self.GC.format('[未執行]', '[未執行]').replace('- 情境：…\n', '- 情境：…\n' + fields).replace('| GC02 |  |', '| GC01 | |')
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc)
        code, out = self.lint()
        self.assertNotIn('和 golden_cases.md 不同', out)
        self.assertNotIn('GC01 的「計算過程」', out)
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace('  - 2. 取整數', '  - 2. 四捨五入'))
        code, out = self.lint()
        self.assertIn('GC01 的「計算過程」和 golden_cases.md 不同', out)

    def test_api_yaml_refs(self):
        # ⑤ 的 api.yaml：讀得進來、$ref 都指得到（AI 不必自己寫 python 驗證）
        api = ('openapi: 3.0.3\npaths:\n  /leaves:\n    post:\n      requestBody:\n        content:\n          application/json:\n'
               '            schema: {$ref: "#/components/schemas/Leave"}\ncomponents:\n  schemas:\n    Leave: {type: object}\n')
        self.write(self.slice_file('api.yaml'), api)
        code, out = self.lint()
        self.assertIn('檢查了 1 個 $ref', out)
        self.write(self.slice_file('api.yaml'), api.replace('schemas/Leave"', 'schemas/Leaves"'))
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('#/components/schemas/Leaves 指不到（沒有「Leaves」）', out)
        self.write(self.slice_file('api.yaml'), api + '  bad: [\n')
        code, out = self.lint()
        self.assertIn('不是合法的 YAML', out)

    # ---------- ⑥ 執行紀錄與審查頁（2026-11-04） ----------
    def run_evidence(self, name, *cmd, cwd=None):
        env = dict(os.environ, DESIGN_REPO=self.dir)
        p = subprocess.run([sys.executable, os.path.join(TOOLS, 'run_evidence.py'), SLICE, name, '--', *cmd],
                           cwd=cwd or self.dir, capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr

    def test_run_evidence_writes_log(self):
        code, out = self.run_evidence('golden', sys.executable, '-c', 'print("GC01 1.491"); raise SystemExit(3)')
        self.assertEqual(code, 3, out)
        rel = re.search(r'執行紀錄：(06_evidence/results/\S+\.log)', out).group(1)
        log = open(os.path.join(self.dir, self.slice_file(rel)), encoding='utf-8').read()
        self.assertTrue(log.startswith('# 執行紀錄（tools/run_evidence.py 產生，不手改）'), log)
        self.assertIn('- 結束碼：3', log)
        self.assertIn('GC01 1.491', log)
        self.assertIn('- 實作版本：', log)
        code, out = self.run_evidence('Bad Name', 'true')
        self.assertNotEqual(code, 0)
        self.assertIn('名稱只用英文小寫', out)

    def test_run_evidence_dirty_ignores_step6_outputs(self):
        # 設計和實作同一個 repo：改 06_evidence/、reviews/ 不算未 commit 的修改，改其他檔案才算
        g = lambda *a: subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd=self.dir, capture_output=True)
        self.write(self.slice_file('06_evidence/signoff.md'), '# 簽核\n')
        self.write(self.slice_file('reviews/2026-11-05_06.md'), '# 審查頁\n')
        g('init', '-q'); g('add', '-A'); g('commit', '-qm', 'init')
        ver = lambda: re.search(r'- 實作版本：(.*)', open(os.path.join(self.dir, self.slice_file(
            re.search(r'執行紀錄：(06_evidence/results/\S+\.log)', self.run_evidence('t', 'true')[1]).group(1))), encoding='utf-8').read()).group(1)
        self.assertIn('有未 commit 的修改：否', ver())
        self.edit(self.slice_file('06_evidence/signoff.md'), '簽核', '簽核 改')
        self.edit(self.slice_file('reviews/2026-11-05_06.md'), '審查頁', '審查頁 改')
        self.assertIn('有未 commit 的修改：否', ver())
        self.edit(self.slice_file('04_rules.md'), '|', '| ')
        self.assertIn('有未 commit 的修改：是', ver())

    def setup_evidence(self, header='# 執行紀錄（tools/run_evidence.py 產生，不手改）', ver='impl @ abc1234（有未 commit 的修改：否）',
                       want='abc1234', cite='（results/2026-11-05_101500_golden.log:12）',
                       env='compose.yaml：compose.yaml sha256:aaaa', chk='通過', env2=None):
        self.write(self.slice_file('reviews/2026-11-05_06.md'), '# 審查頁\n')
        self.write(self.slice_file('06_evidence/results/2026-11-05_101500_golden.log'),
                   f'{header}\n- 切片：{SLICE}\n- 名稱：golden\n- 指令：pytest\n- 執行目錄：/x\n- 實作版本：{ver}\n- 環境：{env}\n- 環境檢查：{chk}\n\n## 輸出\nGC01 6 日\n')
        self.write(self.slice_file('06_evidence/results/2026-11-05_101600_answers.log'),
                   f'{header}\n- 實作版本：{ver}\n- 環境：{env2 or env}\n- 環境檢查：通過\n\n## 輸出\nQ01 6 天\n')
        self.write(self.slice_file('06_evidence/answers.md'), '# answers\n\n| 驗收問題 | 能否回答 | 用哪個查詢或 API | 結果 | 判定 |\n|---|---|---|---|---|\n'
                   '| Q01 | 能 | GET /x | 6 天（results/2026-11-05_101600_answers.log:5） | 通過 |\n')
        self.write(self.slice_file('06_evidence/signoff.md'), f'# signoff\n\n- 實作版本：impl @ {want}（對應設計 tag：…）\n')
        gc = self.GC.format('一致', '通過').replace('- 判定：通過', f'- 系統結果：6 日{cite}\n- 判定：通過').replace('| GC02 |  |', '| GC01 | |')
        self.write(self.slice_file('06_evidence/golden_cases.md'), gc)
        code, out = self.lint()
        return out.split('[執行紀錄]')[1].split('\n[')[0]

    def test_evidence_log_citations(self):
        self.assertNotIn('✗', self.setup_evidence())
        self.assertIn('沒有寫依據的 log 位置', self.setup_evidence(cite=''))
        self.assertIn('不是 tools/run_evidence.py 產生的', self.setup_evidence(header='# 我自己寫的'))
        self.assertIn('有未 commit 的修改時跑的', self.setup_evidence(ver='impl @ abc1234（有未 commit 的修改：是）'))
        self.assertIn('和 signoff.md 的 def5678 不同', self.setup_evidence(want='def5678'))
        self.assertIn('驗證環境沒有通過檢查', self.setup_evidence(chk='未檢查（沒有環境定義檔）'))
        self.assertIn('不是在同一個驗證環境跑的', self.setup_evidence(env2='compose.yaml：compose.yaml sha256:bbbb'))

    def test_check_env(self):
        # ⑥ 的驗證環境：image 固定 digest、不和主機共用、不掛主機路徑與 docker.sock、port 只綁 127.0.0.1
        d = os.path.join(self.dir, 'impl')
        os.makedirs(d)
        good = ('services:\n  db:\n    image: postgres:15@sha256:' + 'a' * 64 + '\n    ports: ["127.0.0.1:55432:5432"]\n'
                '    volumes: ["pgdata:/var/lib/postgresql/data", "./schema.sql:/docker-entrypoint-initdb.d/1.sql:ro"]\n'
                '  app:\n    build: .\n    volumes: ["./src:/app/src"]\nvolumes:\n  pgdata: {}\n')
        with open(os.path.join(d, 'compose.yaml'), 'w', encoding='utf-8') as f: f.write(good)
        with open(os.path.join(d, 'Dockerfile'), 'w', encoding='utf-8') as f:
            f.write('FROM python:3.12-slim@sha256:' + 'b' * 64 + ' AS base\nFROM base\n')
        code, out = run('check_env.py', os.path.join(d, 'compose.yaml'), cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn('環境指紋：compose.yaml sha256:', out)
        x = ('  x:\n    image: busybox@sha256:' + 'c' * 64 + '\n    privileged: true\n    network_mode: host\n'
             '    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]\n')
        bad = good.replace('@sha256:' + 'a' * 64, '').replace('127.0.0.1:55432', '55432').replace('./src', '/home/x') \
                  .replace('volumes:\n  pgdata', x + 'volumes:\n  pgdata')
        with open(os.path.join(d, 'compose.yaml'), 'w', encoding='utf-8') as f: f.write(bad)
        code, out = run('check_env.py', os.path.join(d, 'compose.yaml'), cwd=self.dir)
        self.assertEqual(code, 1, out)
        for msg in ('沒有用 @sha256: 固定版本', '對外開放', 'repo 以外的主機路徑', 'privileged', 'network_mode 是 host', 'docker.sock'):
            self.assertIn(msg, out)
        # run_evidence 把環境與檢查結果寫進檔頭
        with open(os.path.join(d, 'compose.yaml'), 'w', encoding='utf-8') as f: f.write(good)
        code, out = self.run_evidence('golden', 'true', cwd=d)
        rel = re.search(r'執行紀錄：(06_evidence/results/\S+\.log)', out).group(1)
        log = open(os.path.join(self.dir, self.slice_file(rel)), encoding='utf-8').read()
        self.assertIn('- 環境：compose.yaml：compose.yaml sha256:', log)
        self.assertIn('- 環境檢查：通過', log)

    def test_evidence_skipped_without_step6_review(self):
        code, out = self.lint()
        self.assertIn('沒有 ⑥ 的審查頁', out.split('[執行紀錄]')[1].split('\n[')[0])

    def test_executor_is_not_signer(self):
        self.setup_review(verdict='')
        rv = self.slice_file('reviews/2026-10-27_03.md')
        text = open(os.path.join(self.dir, rv), encoding='utf-8').read()
        text = text.replace('| 步驟 | 審查者（非產出者） | 日期 | 結論 |\n|---|---|---|---|\n| ③ |  |  |  |',
                            '| 步驟 | 執行者 | 審查者（非產出者） | 日期 | 結論 |\n|---|---|---|---|---|\n| ③ | 甲 | 甲 | 2026-11-05 | 通過 |')
        self.assertIn('| ③ | 甲 | 甲 |', text)
        self.write(rv, text)
        code, out = self.lint()
        self.assertIn('執行者和審查者（簽核者）是同一人「甲」', out)
        self.write(rv, text.replace('| ③ | 甲 | 甲 |', '| ③ | 甲（一人團隊） | 甲 |'))
        code, out = self.lint()
        self.assertNotIn('的執行者和審查者（簽核者）是同一人', out)
        self.assertIn('執行者和簽核者是同一人「甲」（一人團隊）', out)

    def test_known_limit_needs_repro_test(self):
        # ⑥ 設計問題處理成「已知限制」（不擋簽核）：要有重現測試、寫出程式暫時的做法
        head = '# signoff\n\n## 實作時發現的設計問題\n\n| # | 問題 | 牽涉 | 實作暫時的做法 | 處理 |\n|---|---|---|---|---|\n'
        self.write(self.slice_file('06_evidence/signoff.md'), head + '| 1 | 兩人同時決定 | R25 |  | 已知限制（審查頁問題 1 選 C） |\n')
        code, out = self.lint()
        part = out.split('[已知限制]')[1].split('\n[')[0]
        self.assertIn('#1 處理為已知限制，但牽涉與處理都沒有重現測試', part)
        self.assertIn('「實作暫時的做法」沒寫', part)
        self.write(self.slice_file('06_evidence/signoff.md'), head + '| 1 | 兩人同時決定 | R25；tests/test_x.py test_dismiss_after_adopt | 照設計字面 | 已知限制（審查頁問題 1 選 C） |\n')
        code, out = self.lint()
        self.assertIn('✓ 通過（檢查了 1 個已知限制）', out.split('[已知限制]')[1].split('\n[')[0])

    def test_spot_hint_format(self):
        # 2026-11-05 起的審查頁：可挑的條目寫「③ 第 1、4 條」，不寫完成標準的文字（網頁對不回是哪幾條）
        self.setup_review()
        old = os.path.join(self.dir, self.slice_file('reviews/2026-10-27_03.md'))
        text = open(old, encoding='utf-8').read()
        os.remove(old)
        self.edit(self.slice_file('03_flows.md'), '- 審查頁：reviews/2026-10-27_03.md', '- 審查頁：reviews/2026-11-05_03.md')
        hint = lambda h: text.replace('## 四、抽查\n\n', f'## 四、抽查\n\n{h}\n\n')
        self.write(self.slice_file('reviews/2026-11-05_03.md'), hint('可挑的條目（AI 不預選）：完成標準中——每個狀態都有更正方式；每個事件都有觸發者'))
        code, out = self.lint()
        self.assertIn('可挑的條目要寫成', out)
        self.write(self.slice_file('reviews/2026-11-05_03.md'), hint('可挑的條目（AI 不預選）：③ 第 1、4 條'))
        code, out = self.lint()
        self.assertNotIn('可挑的條目要寫成', out)

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

    def test_step6_challenge_rows(self):
        # ⑥ 新範本有「反例處理」表：送審中要有 AI 挑錯的反例；舊的 signoff（沒有這張表）不檢查
        base = ('# signoff\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 待檢查 |\n\n## 決定與理由\n\n### 反例處理\n\n'
                '| # | 反例 | 來源 | 處理 | 理由或去向 |\n|---|---|---|---|---|\n{row}\n## 檢查紀錄\n\n- 審查頁：reviews/2026-11-07_06.md\n')
        so = self.slice_file('06_evidence/signoff.md')
        self.write(so, base.format(row=''))
        code, out = self.lint()
        self.assertIn('06_evidence/signoff.md 送審了，「反例處理」沒有來源為「AI 挑錯」的反例', out)
        self.write(so, base.format(row='| X-01 | 同一次公告分次登錄 | AI 挑錯（領域實務） | 轉為設計問題 | 設計問題 #1 |\n'))
        code, out = self.lint()
        self.assertNotIn('沒有來源為「AI 挑錯」的反例', out)
        self.write(so, base.format(row='').replace('## 決定與理由\n\n### 反例處理\n\n| # | 反例 | 來源 | 處理 | 理由或去向 |\n|---|---|---|---|---|\n', ''))
        code, out = self.lint()
        self.assertNotIn('signoff.md 送審了', out)

    def test_step5_stage1_review_does_not_freeze(self):
        # ⑤ 分兩段：頁首寫「⑤ 第一段」的審查頁答完也不能凍結；第二段才可以
        self.write(self.slice_file('05_mapping.md'), '# leave-backfill ⑤\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 待檢查 |\n\n'
                   '## 檢查紀錄\n\n- 審查頁：reviews/2026-11-07_05.md\n')
        page = ('# 審查頁\n\n| 項目 | 內容 |\n|---|---|\n| 這輪審查的步驟 | {stage} |\n\n## 一、要你回答的問題\n\n（這輪沒有問題）\n\n'
                '## 四、抽查\n\n| 抽查了哪幾條 | 結果 |\n|---|---|\n| ⑤ 第 1 條 | 符合 |\n\n'
                '## 結論\n\n| 步驟 | 審查者（非產出者） | 日期 | 結論 |\n|---|---|---|---|\n| ⑤ | 甲 | 2026-11-07 | 通過 |\n')
        self.write(self.slice_file('reviews/2026-11-07_05.md'), page.format(stage='⑤ 第一段'))
        code, out = self.lint('--freeze')
        self.assertIn('是 ⑤ 第一段的審查頁：答完不凍結', out)
        self.write(self.slice_file('reviews/2026-11-07_05.md'), page.format(stage='⑤ 第二段'))
        code, out = self.lint('--freeze')
        self.assertNotIn('第一段的審查頁', out)

    def test_ai_reviewer_only_in_auto_mode(self):
        # 審查者寫 AI（自動）：手動模式紅燈；切片地圖的執行模式改成全自動就可以
        self.setup_review(rev='AI（自動）', date='2026-11-07', verdict='通過')
        code, out = self.lint()
        self.assertIn('審查者是「AI（自動）」：手動模式的審查者是人', out)
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 已同意 |\n| 執行模式 | 全自動 |\n')
        code, out = self.lint()
        self.assertNotIn('審查者是「AI（自動）」', out)

    AUTO_PAGE = ('# leave-backfill 全自動事後審查頁（2026-11-09）\n\n| 項目 | 內容 |\n|---|---|\n| 這輪審查的步驟 | 全自動事後審查 |\n| 處理 | {done} |\n\n'
                 '## 一、要你回答的問題\n\n### 問題 1（④ D-01）\n- 來源：{src}\n- 背景：…\n- 例子：小明 2026-03-01 補登\n- 問題：要不要補登？\n'
                 '- A（建議）：可以補登 → 設計不變\n- B：不補登 → 改 D-01\n- 其他：（寫一句）\n- 影響：04_rules.md D-01\n- 你的回答：{ans}\n')

    def test_auto_review_page(self):
        # 全自動事後審查頁（docs/01 0.2「待人決定」）：格式；審查頁寫了「待人決定」要收進來；答完提醒處理
        self.write(self.slice_file('reviews/2026-11-09_04.md'),
                   '# x\n\n## 一、要你回答的問題\n\n### 問題 2（④ D-01）\n- 問題：…\n- A（建議）：a → b\n- B：c → d\n- 你的回答：A（待人決定：依據只有推論）\n')
        code, out = self.lint()
        self.assertIn('問題 2（④ D-01） 寫了「待人決定」，沒有收進全自動事後審查頁', out)
        self.write(self.slice_file('reviews/2026-11-09_auto.md'),
                   self.AUTO_PAGE.format(src='reviews/2026-11-09_04.md 問題 2', ans='', done=''))
        code, out = self.lint()
        self.assertNotIn('沒有收進全自動事後審查頁', out)
        self.assertIn('還有 1 題待人決定', out)
        self.write(self.slice_file('reviews/2026-11-09_auto.md'),
                   self.AUTO_PAGE.format(src='reviews/2026-11-09_04.md 問題 2', ans='B', done='').replace('- 影響：04_rules.md D-01\n', ''))
        code, out = self.lint()
        self.assertIn('沒有「影響」', out)
        self.assertIn('都答完了、還沒處理', out)
        self.write(self.slice_file('reviews/2026-11-09_auto.md'),
                   self.AUTO_PAGE.format(src='reviews/2026-11-09_04.md 問題 2', ans='B', done='2026-11-10 CHANGELOG 第一筆'))
        code, out = self.lint()
        self.assertNotIn('還沒處理', out)
        self.assertNotIn('[事後審查] 紅燈', out)

    def test_expected_result_change(self):
        # 改黃金案例的預期結果：寫種類與依據，依據不能是被驗證的設計；AI 改的（全自動）要收進事後審查頁
        gc = self.GC.format('一致', '[未執行]')
        line = '- 判定：[未執行]\n\n## GC02'
        def put(change):
            self.write(self.slice_file('06_evidence/golden_cases.md'), gc.replace(line, f'- 判定：[未執行]\n- 預期結果修改：{change}\n\n## GC02', 1))
            return self.lint()
        code, out = put('2026-11-09 王小明：③ 1996-08-01 → 2026-01-01；種類：算錯；依據：R12 的起算日')
        self.assertIn('依據指到被驗證的設計', out)
        code, out = put('2026-11-09 王小明：③ 不通過 → 資料不足；種類：設計；依據：inputs/shared/a.md')
        self.assertIn('只能是算錯、輸入補齊', out)
        code, out = put('改成 2026-01-01')
        self.assertIn('要寫成「<日期> <修改者>', out)
        code, out = put('2026-11-09 王小明：③ 1996-08-01 → 2026-01-01；種類：輸入補齊；依據：inputs/shared/範圍釐清_員工編號.md')
        self.assertNotIn('預期結果修改] 紅燈', out)
        self.assertNotIn('golden_cases.md:', out.split('[預期結果修改]')[1].split('[')[0])
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 已同意 |\n| 執行模式 | 全自動 |\n')
        code, out = put('2026-11-09 AI（自動）：③ 1996-08-01 → 2026-01-01；種類：輸入補齊；依據：inputs/shared/a.md')
        self.assertIn('沒有收進全自動事後審查頁', out)
        self.write(self.slice_file('reviews/2026-11-09_auto.md'), self.AUTO_PAGE.format(src='GC01 預期結果修改', ans='', done=''))
        code, out = put('2026-11-09 AI（自動）：③ 1996-08-01 → 2026-01-01；種類：輸入補齊；依據：inputs/shared/a.md')
        self.assertNotIn('沒有收進全自動事後審查頁', out)

    def test_challenge_angle_required(self):
        """這輪新增、來源是 AI 挑錯的反例要寫角度（2026-11-04 T27）"""
        self.setup_review()
        code, out = self.lint()
        self.assertNotIn('沒有寫挑錯角度', out)
        for bad in ('AI 挑錯', 'AI 挑錯（第二輪）'):
            self.setup_review(src=bad)
            code, out = self.lint()
            self.assertEqual(code, 1, out)
            self.assertIn('X-01 的來源「' + bad + '」沒有寫挑錯角度', out)
        self.setup_review(src='AI 挑錯', xs='')               # 不在這輪的舊反例不檢查
        code, out = self.lint()
        self.assertNotIn('沒有寫挑錯角度', out)

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

    PLAT = ''.join(f'| P{k} 約定 | 未定 | |\n' for k in range(1, 14))
    ADR = ('### ADR-001　主資料庫類型\n\n| 項目 | 內容 |\n|---|---|\n| 判斷 | {kind} |\n| 狀態 | {status} |\n'
           '| 背景與訊號 | {bg} |\n| 決定 | 關聯式 |\n| 沒採用的做法 | 文件型：跨 Entity 規則多 |\n'
           '| 代價 | 結構改版要遷移 |\n| 重新評估的觸發 | 出現多跳查詢 |\n| 資安影響 | 無 |\n'
           '| 提出／同意 | {who} |\n| 生效 | 2026-11-03 |\n| 受影響切片 | — |\n')

    def write_decisions(self, status='採用', bg='leave-backfill/04_rules.md R01', who='AI／○○（2026-11-03）', plat=None,
                        kind='S2'):
        self.write('architecture/DECISIONS.md',
                   '# 架構決定紀錄\n\n## 一、平台約定現況\n\n| 約定 | 現況 | 依據 |\n|---|---|---|\n'
                   + (self.PLAT if plat is None else plat) + '\n## 二、選型\n\n'
                   + self.ADR.format(status=status, bg=bg, who=who, kind=kind))

    def write_mapping(self, status='待檢查', inputs='04_rules.md @ leave-backfill/04-v1；architecture/DECISIONS.md @ abc1234',
                      rules=''):
        self.write(self.slice_file('05_mapping.md'),
                   f'# leave-backfill ⑤ 投影到實作\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | {status} |\n'
                   f'| 讀取的輸入 | {inputs} |\n'
                   + (f'\n## 三、規則 → 落實位置\n\n| 規則 | 落實位置 | 說明 |\n|---|---|---|\n{rules}' if rules else ''))

    def test_s1_rules_cite_adr_in_mapping(self):
        self.write_decisions(kind='S1', bg='other/04_rules.md R09；leave-backfill/04_rules.md R01～R02')
        self.write_mapping(rules='| R01 | service | 跨表檢查 |\n')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('R01 在 ADR-001（S1）裡', out)
        self.assertIn('第三區沒有 R02', out)
        self.assertNotIn('R09', out.split('[架構決定]')[1].split('\n[')[0])
        self.write_mapping(rules='| R01、R02 | service | 交易中先鎖同一人（ADR-001） |\n')
        code, out = self.lint()
        section = out.split('[架構決定]')[1].split('\n[')[0]
        self.assertNotIn('✗', section, out)
        self.write_mapping(status='已凍結', rules='| R01 | service | 跨表檢查 |\n')
        code, out = self.lint()
        self.assertNotIn('R01 在 ADR-001（S1）裡', out)

    def test_architecture_record_passes(self):
        self.write_decisions()
        self.write_mapping()
        code, out = self.lint()
        section = out.split('[架構決定]')[1].split('\n[')[0]
        self.assertNotIn('✗', section, out)
        self.assertIn('✓ 通過', section)

    def test_architecture_adr_fields_and_status(self):
        self.write_decisions(status='決定了', bg='大家都用這個')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('ADR-001 的狀態「決定了」不是', out)
        self.assertIn('ADR-001 的「背景與訊號」沒有寫交付物的檔名與編號', out)
        self.write_decisions(status='已取代: ADR-009', plat=self.PLAT.replace('| P7 約定 | 未定 | |\n', ''))
        code, out = self.lint()
        self.assertIn('引用的 ADR-009 不存在', out)
        self.assertIn('少了 P7', out)

    def test_mapping_must_read_decisions(self):
        self.write_decisions()
        self.write_mapping(inputs='04_rules.md @ leave-backfill/04-v1')
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn('「讀取的輸入」沒有 architecture/DECISIONS.md', out)
        self.write_mapping(status='已凍結', inputs='04_rules.md @ leave-backfill/04-v1')
        code, out = self.lint()
        self.assertNotIn('「讀取的輸入」沒有 architecture/DECISIONS.md', out)

    def test_pending_adr_blocks_mapping_freeze(self):
        self.write_decisions(who='AI／待確認')
        self.write_mapping()
        code, out = self.lint()
        self.assertIn('ADR-001 待確認', out)
        self.assertNotIn('還是待確認：⑤ 要凍結', out)
        code, out = self.lint('--freeze')
        self.assertIn('ADR-001 還是待確認：⑤ 要凍結', out)

    def data_nature(self, out):
        return out.split('[資料性質]')[1].split('\n[')[0]

    def test_data_nature_required_when_platform_handles_personal_data(self):
        # P11 資料性質（2026-11-04，T26）：沒有紀錄不檢查；未定時未凍結的 ② 亮紅燈；已採用時每個新增屬性都要標三種之一
        code, out = self.lint()
        self.assertIn('未檢查（沒有 architecture/DECISIONS.md）', self.data_nature(out))
        self.write_decisions()
        code, out = self.lint()
        self.assertIn('「P11 資料性質」還沒決定', self.data_nature(out))
        self.write_decisions(plat=self.PLAT + '| P11 資料性質 | 不同做法：不處理個資 | 只有匿名統計 |\n')
        code, out = self.lint()
        self.assertIn('未檢查（P11 資料性質：不處理個資）', self.data_nature(out))
        self.write_decisions(plat=self.PLAT + '| P11 資料性質 | 已採用 | 處理員工個資 |\n')
        code, out = self.lint()
        sec = self.data_nature(out)
        self.assertEqual(code, 1, out)
        self.assertIn('Employment.start_date 沒有標資料性質', sec)
        self.assertIn('LeaveOccurrence.balance_after 沒有標資料性質', sec)
        f = self.slice_file('02_entities.md')
        self.edit(f, '`start_date`（到職日）', '`start_date`（到職日）[性質: 可識別個人]')
        self.edit(f, '`hours`（時數）', '`hours`（時數）[性質: 敏感]')
        code, out = self.lint()
        sec = self.data_nature(out)
        self.assertNotIn('start_date 沒有標', sec)
        self.assertIn('「[性質: 敏感]」不是 不含個資／可識別個人／特種個資', sec)
        for old, new in [('`hours`（時數）[性質: 敏感]', '`hours`（時數）[性質: 可識別個人]'),
                         ('`leave_type`（假別，分類值 LEAVE_TYPE）', '`leave_type`（假別，分類值 LEAVE_TYPE）[性質: 不含個資]'),
                         ('`balance_after`（扣除後餘額）[推導]', '`balance_after`（扣除後餘額）[推導] [性質: 可識別個人]'),
                         ('`requested_hours`（申請時數）', '`requested_hours`（申請時數）[性質: 特種個資]')]:
            self.edit(f, old, new)
        code, out = self.lint()
        sec = self.data_nature(out)
        self.assertNotIn('✗', sec, out)
        self.assertIn('✓ 通過（檢查了 5 個屬性）', sec)

    def test_data_nature_needs_decisions_before_step2(self):
        # 還沒凍結的 ② 卻沒有 architecture/DECISIONS.md：② 開始前要先做 /domain-arch 初判（P11 資料性質）
        self.edit(self.slice_file('02_entities.md'), '# leave-backfill ② 名詞盤點\n', '# leave-backfill ② 名詞盤點\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 草稿 |\n')
        code, out = self.lint()
        self.assertIn('沒有 architecture/DECISIONS.md：② 開始前先做 /domain-arch 初判', out)

    def test_data_nature_frozen_entities_only_remind(self):
        self.write_decisions(plat=self.PLAT + '| P11 資料性質 | 已採用 | 處理員工個資 |\n')
        f = self.slice_file('02_entities.md')
        self.edit(f, '# leave-backfill ② 名詞盤點\n', '# leave-backfill ② 名詞盤點\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 已凍結 |\n')
        code, out = self.lint()
        sec = self.data_nature(out)
        self.assertNotIn('✗', sec, out)
        self.assertIn('② 已凍結，5 處要補標', sec)

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

class TestAuto(Base):
    """全自動模式（docs/01 0.2「全自動模式」）：auto_hook.py 放行並記錄、碰到禁止清單擋下；auto_run.py 一圈一個 session，照回報停下來。"""
    def hook(self, tool, ti, auto='1'):
        import json
        env = dict(os.environ, DOMAIN_AUTO=auto, DOMAIN_AUTO_REPO=self.dir)
        p = subprocess.run([sys.executable, os.path.join(TOOLS, 'auto_hook.py')], input=json.dumps({'tool_name': tool, 'tool_input': ti, 'cwd': self.dir}),
                           capture_output=True, text=True, env=env)
        return json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'] if p.stdout.strip() else None

    def test_hook_allows_and_blocks(self):
        self.assertEqual(self.hook('Bash', {'command': 'docker compose up -d && python3 tools/run_evidence.py s n -- pytest'}), 'allow')
        self.assertEqual(self.hook('Write', {'file_path': os.path.join(self.dir, 'slices/a.md')}), 'allow')
        for ti in ({'command': 'git push origin main'}, {'command': 'sudo apt install x'}, {'command': 'cat ~/.ssh/id_rsa'},
                   {'command': 'docker run -v /var/run/docker.sock:/s img'}, {'command': 'docker run --privileged img'},
                   {'command': 'rm -rf /etc/x'}, {'command': 'echo x > /etc/hosts'}):
            self.assertEqual(self.hook('Bash', ti), 'deny', ti)
        self.assertEqual(self.hook('Edit', {'file_path': os.path.expanduser('~/.bashrc')}), 'deny')
        self.assertEqual(self.hook('Read', {'file_path': os.path.expanduser('~/.ssh/config')}), 'deny')
        # Claude Code 把太長的工具輸出存在 ~/.claude/projects/<repo>/…/tool-results/，可以讀、不能寫
        import re as _re
        sd = os.path.join(os.path.expanduser('~/.claude/projects'), _re.sub(r'[^A-Za-z0-9]', '-', os.path.realpath(self.dir)), 's', 'tool-results', 'x.txt')
        self.assertEqual(self.hook('Read', {'file_path': sd}), 'allow')
        self.assertEqual(self.hook('Write', {'file_path': sd}), 'deny')
        self.assertEqual(self.hook('Read', {'file_path': os.path.expanduser('~/.claude/projects/other-repo/s/x.txt')}), 'deny')
        log = open(os.path.join(self.dir, '.domain-auto', 'commands.jsonl'), encoding='utf-8').read()
        self.assertIn('"allow": false', log)
        self.assertIsNone(self.hook('Bash', {'command': 'git push'}, auto=''))   # 不是全自動：不表示意見

    def fake_claude(self, replies):
        """假的 claude：每次被呼叫依序回一個 result，並在 repo 裡改一個檔（模擬有進展）。"""
        import json
        state = os.path.join(self.dir, '.fake_n')
        script = os.path.join(self.dir, 'fake_claude.py')
        with open(script, 'w', encoding='utf-8') as f:
            f.write('import json, os, sys\n'
                    f'replies = {json.dumps(replies, ensure_ascii=False)}\n'
                    f'st = {state!r}\n'
                    'n = int(open(st).read()) if os.path.exists(st) else 0\n'
                    'open(st, "w").write(str(n + 1))\n'
                    'open("progress.txt", "a").write(str(n))\n'
                    'assert os.environ.get("DOMAIN_AUTO") == "1" and "--settings" in sys.argv\n'
                    'print(json.dumps({"type": "result", "result": replies[min(n, len(replies) - 1)]}, ensure_ascii=False))\n')
        wrapper = os.path.join(self.dir, 'claude')
        with open(wrapper, 'w') as f:
            f.write(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
        os.chmod(wrapper, 0o755)
        subprocess.run(['git', 'init', '-q'], cwd=self.dir)
        return wrapper

    def test_runner_needs_auto_mode(self):
        code, out = run('auto_run.py', cwd=self.dir)
        self.assertNotEqual(code, 0)
        self.assertIn('不是「全自動」', out)

    def test_runner_stops_on_report(self):
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 已同意 |\n| 執行模式 | 全自動 |\n')
        claude = self.fake_claude(['做完 ①\n全自動：繼續', '凍結 ①\n全自動：需要人（docker 起不來）'])
        code, out = run('auto_run.py', '--claude', claude, cwd=self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn('第 1 圈：繼續', out)
        self.assertIn('第 2 圈：需要人（docker 起不來）', out)
        self.assertIn('第 2 圈：需要人', open(os.path.join(self.dir, '.domain-auto', 'runs.md'), encoding='utf-8').read())

    def test_runner_until_design_done(self):
        # --until-design-done：地圖上出現新的「設計完成（待驗證）」切片就停
        plan = '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 執行模式 | 全自動 |\n\n## 切片\n\n| 切片 | 狀態 |\n|---|---|\n| a | 進行中 |\n'
        self.write('slices/PLAN.md', plan)
        claude = self.fake_claude(['全自動：繼續'] * 5)
        with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
            f.write('if n == 1:\n    p = "slices/PLAN.md"; t = open(p).read(); open(p, "w").write(t.replace("| a | 進行中 |", "| a | 設計完成（待驗證） |"))\n')
        code, out = run('auto_run.py', '--claude', claude, '--until-design-done', cwd=self.dir)
        self.assertIn('第 2 圈：繼續', out)
        self.assertNotIn('第 3 圈', out)
        self.assertIn('a 設計完成（⑤ 凍結），照 --until-design-done 停下來', out)

    def test_runner_until_design_done_refreeze(self):
        # 已經設計完成的切片回頭修改後 ⑤ 重新凍結（多了 a/05-v2 tag）也停：地圖狀態沒變，看 tag
        git = lambda *a: subprocess.run(['git', *a], cwd=self.dir, capture_output=True, text=True, check=True)
        git('init', '-q')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x')
        git('tag', 'a/05-v1')
        plan = '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 執行模式 | 全自動 |\n\n## 切片\n\n| 切片 | 狀態 |\n|---|---|\n| a | 設計完成（待驗證） |\n'
        self.write('slices/PLAN.md', plan)
        claude = self.fake_claude(['全自動：繼續'] * 5)
        with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
            f.write('if n == 1:\n    import subprocess; subprocess.run(["git", "tag", "a/05-v2"], check=True)\n')
        code, out = run('auto_run.py', '--claude', claude, '--until-design-done', cwd=self.dir)
        self.assertIn('第 2 圈：繼續', out)
        self.assertNotIn('第 3 圈', out)
        self.assertIn('a 設計完成（⑤ 凍結），照 --until-design-done 停下來', out)

    def test_runner_stops_when_switched_to_manual(self):
        # 跑到一半改回手動：下一圈開始前檢查，停下來
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 執行模式 | 全自動 |\n')
        claude = self.fake_claude(['全自動：繼續'] * 5)
        with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
            f.write('p = "slices/PLAN.md"\nt = open(p).read()\nopen(p, "w").write(t.replace("全自動 |", "手動 |"))\n')
        code, out = run('auto_run.py', '--claude', claude, cwd=self.dir)
        self.assertIn('第 1 圈：繼續', out)
        self.assertNotIn('第 2 圈', out)
        self.assertIn('執行模式已改回手動', out)

    def test_runner_recovers_after_cut(self):
        # 上一次做到一半被切斷（網頁強制中斷；或舊紀錄 runs.md 最後一圈沒有回報結果，例：用量上限）：第一圈先收拾，留下的 index.lock 刪掉
        import json
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 執行模式 | 全自動 |\n')
        for prev, why in ((json.dumps({'running': False, 'interrupted': True, 'round': 4}), '網頁強制中斷'),
                          (None, "You've hit your limit")):
            for f in ('state.json', 'runs.md'):
                if os.path.exists(os.path.join(self.dir, '.domain-auto', f)):
                    os.remove(os.path.join(self.dir, '.domain-auto', f))
            if prev:
                self.write('.domain-auto/state.json', prev)
            else:
                self.write('.domain-auto/runs.md', "- x 第 13 圈：沒有回報結果　You've hit your limit　（runs/x_13.jsonl）\n")
            claude = self.fake_claude(['全自動：繼續', '全自動：需要人（停）'])
            with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
                f.write('open("prompts.txt", "a").write(sys.argv[2].replace("\\n", " ") + "\\n")\n')
            self.write('.git/index.lock', '')
            self.write('.fake_n', '0')
            if os.path.exists(os.path.join(self.dir, 'prompts.txt')):
                os.remove(os.path.join(self.dir, 'prompts.txt'))
            run('auto_run.py', '--claude', claude, cwd=self.dir)
            prompts = open(os.path.join(self.dir, 'prompts.txt'), encoding='utf-8').read().splitlines()
            self.assertTrue(prompts[0].startswith('上一次全自動在第'), prompts[0])
            self.assertIn(why, prompts[0])
            self.assertFalse(prompts[1].startswith('上一次'))
            self.assertFalse(os.path.exists(os.path.join(self.dir, '.git', 'index.lock')))
        # 正常停下來的（需要人）：下一次不用收拾
        claude = self.fake_claude(['全自動：需要人（停）'])
        with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
            f.write('open("prompts.txt", "a").write(sys.argv[2].replace("\\n", " ") + "\\n")\n')
        os.remove(os.path.join(self.dir, 'prompts.txt'))
        run('auto_run.py', '--claude', claude, cwd=self.dir)
        self.assertFalse(open(os.path.join(self.dir, 'prompts.txt'), encoding='utf-8').read().startswith('上一次'))

    def test_runner_stop_file_and_state(self):
        # 網頁的「停止」建立 .domain-auto/stop：這一圈做完就停，執行模式不變；state.json 記第幾圈、停下來的原因
        import json
        self.write('slices/PLAN.md', '# 切片地圖\n\n| 項目 | 內容 |\n|---|---|\n| 執行模式 | 全自動 |\n')
        claude = self.fake_claude(['全自動：繼續'] * 5)
        with open(os.path.join(self.dir, 'fake_claude.py'), 'a', encoding='utf-8') as f:
            f.write('import os\nos.makedirs(".domain-auto", exist_ok=True)\nopen(".domain-auto/stop", "w").close()\n')
        code, out = run('auto_run.py', '--claude', claude, cwd=self.dir)
        self.assertIn('第 1 圈：繼續', out)
        self.assertNotIn('第 2 圈', out)
        self.assertIn('有人按了停止', out)
        st = json.load(open(os.path.join(self.dir, '.domain-auto', 'state.json'), encoding='utf-8'))
        self.assertFalse(st['running'])
        self.assertEqual(st['round'], 1)
        self.assertIn('有人按了停止', st['reason'])
        self.assertTrue(st['log'].endswith('_1.jsonl'))
        self.assertFalse(os.path.exists(os.path.join(self.dir, '.domain-auto', 'stop')))
        self.assertIn('全自動 |', open(os.path.join(self.dir, 'slices', 'PLAN.md'), encoding='utf-8').read())

    def write(self, rel, text):
        p = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
