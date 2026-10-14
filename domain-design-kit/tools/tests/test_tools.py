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

    def test_pending_decision_blocks_freeze(self):
        self.edit(self.slice_file('01_scope.md'), 'AI／○○（2026-10-06） |\n| D-02', 'AI／待確認 |\n| D-02')
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn('D-01 待確認', out)
        code, out = self.lint('--freeze')
        self.assertEqual(code, 1, out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
