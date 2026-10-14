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

if __name__ == '__main__':
    unittest.main(verbosity=2)
