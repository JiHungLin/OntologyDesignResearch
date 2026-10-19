#!/usr/bin/env python3
"""引用檢查：docs/02 第七節中可以用程式比對的項目，加上改名後的殘留與已取消項目的引用。
直接讀 Markdown（用 md2build.py 的解析），不需要先轉 YAML。
用法：python tools/lint.py <切片代號> [--root <repo 根目錄>] [--freeze] [--baseline <目錄>]
  --freeze：準備凍結時使用，「提出／同意」有「待確認」就亮紅燈（平常只列出）。
  --baseline：上一版的切片資料夾（預設取各步驟最新的 git tag），用來找被刪除或改名的名稱。
只檢查引用與結構對不對得起來，不代表內容正確。"""
import os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2build as mb

STEP_FILES = {2: '02_entities.md', 3: '03_flows.md', 4: '04_rules.md'}
ALL_FILES = ['01_scope.md', '02_entities.md', '03_flows.md', '03_use_cases.md', '04_rules.md', '05_mapping.md']
HISTORY_H2 = {'決定與理由', '檢查紀錄', '回填紀錄'}
HISTORY_H3 = {'反例處理', '六問判斷紀錄'}
MARKERS = [r'候選', r'已驗證', r'已驗證（暫代）', r'已取代: .+，.+', r'已停用: .+', r'引用候選',
           r'待專家確認: EQ-\d+', r'暫代', r'未核對', r'推導', r'性質: .+', r'靜態替代', r'技術', r'未執行',
           r'解讀: .+', r'已取消: .+']
MARKER_RE = re.compile(r'^(?:' + '|'.join(MARKERS) + r')$')

QUALIFIED_RE = re.compile(r'(?:\b0\d(?:_[a-z_]+)?(?:\.md)?|PLAN(?:\.md)?|ENTITY_SKETCH(?:\.md)?)\s*'
                          r'(?:D-\d+\s*[、，,～]\s*)*$')

def targets(text):
    """套用對象中的識別名稱、規則編號（展開 R22～R28）、UC 編號。
    `Entity.attribute` 算 Entity；括號裡的說明文字只取其中的規則與 UC 編號。"""
    text = text or ''
    inner = ' '.join(re.findall(r'[（(]([^）)]*)[）)]', text))
    outer = re.sub(r'[（(][^）)]*[）)]', ' ', text)
    out = []
    pat = r'R(\d+)～R(\d+)|UC-\d+|R\d+|([A-Za-z][A-Za-z0-9_]*)(?:\.[a-z][A-Za-z0-9_]*)?'
    for src, ids_only in ((outer, False), (inner, True)):
        for m in re.finditer(pat, src):
            if m.group(1):
                out += [f'R{i:02d}' for i in range(int(m.group(1)), int(m.group(2)) + 1)]
            elif m.group(3):
                if not ids_only: out.append(m.group(3))
            else:
                out.append(m.group(0))
    return out

def word(name):
    return re.compile(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])')

class Lint:
    def __init__(self, root, slice_name, freeze, baseline):
        self.root, self.slice, self.freeze, self.baseline = root, slice_name, freeze, baseline
        self.dir = os.path.join(root, 'slices', slice_name)
        self.docs = {f: mb.Doc(os.path.join(self.dir, f)) for f in ALL_FILES
                     if os.path.exists(os.path.join(self.dir, f))}
        self.data = mb.build(root, slice_name)
        self.parse_problems = list(mb.problems)
        self.fails, self.skipped = [], []

    # ---------- 共用 ----------
    def rel(self, path):
        return os.path.relpath(path, self.root)

    def lines(self, files=None, history=False):
        """切片 Markdown 的每一行：(檔案, 行號, h2, h3, 文字)。預設略過「決定與理由」等歷史描述。"""
        for f, d in self.docs.items():
            if files and f not in files: continue
            for no, h2, h3, line in d.items:
                text = h3 if line is None else line
                if not history and ((h2 or '') in HISTORY_H2 or (h3 or '') in HISTORY_H3):
                    continue
                yield f, no, h2, h3, text

    def red(self, code, msg):
        print(f"    ✗ {msg}"); self.fails.append(code)

    def done(self, code, count, unit, skipped=None):
        if skipped:
            print(f"    – 未檢查（{skipped}）"); self.skipped.append(code)
        elif count == 0:
            print("    – 未檢查（沒有資料）"); self.skipped.append(code)
        elif code not in self.fails:
            print(f"    ✓ 通過（檢查了 {count} {unit}）")
        else:
            print(f"    （檢查了 {count} {unit}）")

    def git(self, *args):
        try:
            p = subprocess.run(['git', '-C', self.root, *args], capture_output=True, text=True)
            return p.stdout if p.returncode == 0 else None
        except FileNotFoundError:
            return None

    def tags(self):
        out = self.git('tag', '--list', f'{self.slice}/*')
        if out is None: return None
        def key(t):
            m = re.search(r'/0?(\d)-v(\d+)$', t)
            return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        return sorted([t for t in out.split() if t], key=key)

    def latest_tag(self, step, tags):
        cand = [t for t in tags if re.search(rf'/0{step}-v\d+$', t)]
        return cand[-1] if cand else None

    # ---------- 解析 ----------
    def slice_defs(self, folder):
        """一個切片資料夾中 ②③④ 定義的名稱。"""
        defs = {'entity': set(), 'attribute': set(), 'relation': set(), 'event': set(),
                'state': set(), 'code': set()}
        p = lambda f: os.path.join(folder, f)
        saved = list(mb.problems)
        if os.path.exists(p('02_entities.md')):
            d = mb.Doc(p('02_entities.md'))
            for e in mb.parse_cards(d, 'new', only_h2='新增'):
                defs['entity'].add(e['name'])
                for a in e['attributes']: defs['attribute'].add((e['name'], a['name']))
            for r in mb.parse_relations(d): defs['relation'].add(r['name'])
        if os.path.exists(p('03_flows.md')):
            sms, evts, _ = mb.parse_flows(mb.Doc(p('03_flows.md')))
            for sm in sms:
                for s in sm['states']: defs['state'].add((sm['entity'], s))
            for e in evts: defs['event'].add(e['name'])
        if os.path.exists(p('04_rules.md')):
            _, _, codes = mb.parse_rules(mb.Doc(p('04_rules.md')))
            for c in codes: defs['code'].add(c['id'])
        mb.problems[:] = saved
        return defs

    def use_cases(self):
        d = self.docs.get('03_use_cases.md')
        ucs, cover = [], []
        if not d: return ucs, cover
        cur = None
        for no, h2, h3, line in d.items:
            if line is None: continue
            if (h2 or '').startswith('UC-') and (cur is None or cur['id'] != h2.split()[0]):
                cur = {'id': h2.split()[0], 'entities': [], 'events': [], 'rules': [], 'line': no}
                ucs.append(cur)
            if cur and (h2 or '').startswith('UC-'):
                m = re.match(r'^- (用到的 Entity|用到的事件|規則)[：:]\s*(.*)$', line)
                if m:
                    key = {'用到的 Entity': 'entities', '用到的事件': 'events', '規則': 'rules'}[m.group(1)]
                    val = m.group(2)
                    cur[key] = (mb.RULE_ID_RE.findall(val) if key == 'rules'
                                else [x for x in (mb.lead_id(p) for p in re.split(r'[、,]', val)) if x])
                    cur[key + '_line'] = no
        for h2, h3, header, rows in d.tables():
            if header[:2] == ['草稿 US', '涵蓋它的 UC']:
                cover += [(no, c[0], re.findall(r'UC-\d+', c[1])) for no, c in rows]
        return ucs, cover

    # ---------- 檢查 ----------
    def check_residue(self):
        print("[殘留] 被刪除或改名的名稱，不能還留在 01～05（歷史描述除外）")
        base = self.baseline
        tmp = None
        if not base:
            tags = self.tags()
            if tags is None:
                return self.done('殘留', 0, '', skipped='不是 git repo，也沒有指定 --baseline')
            tmp = tempfile.mkdtemp()
            found = False
            for step, f in STEP_FILES.items():
                t = self.latest_tag(step, tags)
                if not t: continue
                content = self.git('show', f'{t}:slices/{self.slice}/{f}')
                if content is None: continue
                with open(os.path.join(tmp, f), 'w', encoding='utf-8') as out:
                    out.write(content)
                found = True
            if not found:
                return self.done('殘留', 0, '', skipped='還沒有凍結過的版本可以比對')
            base = tmp
        old, new = self.slice_defs(base), self.slice_defs(self.dir)
        removed = []
        for e in old['entity'] - new['entity']: removed.append(('Entity', e, e))
        new_attr_names = {a for _, a in new['attribute']}
        for ent, a in old['attribute'] - new['attribute']:
            if a not in new_attr_names:          # 屬性名稱完全不再使用
                removed.append(('屬性', f'{ent}.{a}', a))
        for kind, key in (('關係', 'relation'), ('事件', 'event')):
            for x in old[key] - new[key]: removed.append((kind, x, x))
        new_states = {s for _, s in new['state']}
        for ent, s in old['state'] - new['state']:
            if s not in new_states: removed.append(('狀態', f'{ent}.{s}', s))
        for c in old['code'] - new['code']: removed.append(('分類值', c, c))
        hits = 0
        for kind, label, name in sorted(removed):
            pat = word(name)
            for f, no, h2, h3, text in self.lines():
                if pat.search(text or ''):
                    hits += 1
                    self.red('殘留', f"{kind} {label} 已不在目前的定義中，仍出現在 {f}:{no}")
        if not removed:
            print("    ✓ 通過（上一版的名稱都還在）")
        else:
            self.done('殘留', len(removed), '個被刪除或改名的名稱')

    def check_cancelled(self):
        print("\n[已取消] 取消的規則、決定，與 core/ 中已取代、已停用的項目，不能再被引用")
        rules = (self.data.get('rules') or {}).get('rules', [])
        cancelled = [r['id'] for r in rules if r.get('status') == 'cancelled']
        n = 0
        for rid in cancelled:
            pat = word(rid)
            for f, no, h2, h3, text in self.lines():
                if not pat.search(text or ''): continue
                if f == '04_rules.md' and re.match(rf'^\|\s*{rid}\s*\|', text): continue   # 規則本身那一列
                n += 1
                self.red('已取消', f"{rid} 已取消，仍被引用：{f}:{no}")
        for f, d in self.docs.items():
            dead = []
            for h2, h3, header, rows in d.tables():
                if h2 == '決定與理由' and header[:2] == ['#', '決定']:
                    dead += [c[0] for no, c in rows if mb.cancelled(c[1])]
            for did in dead:
                pat = word(did)
                for f2, no, h2, h3, text in self.lines(files=[f]):
                    for m in pat.finditer(text or ''):
                        if QUALIFIED_RE.search(text[max(0, m.start() - 40):m.start()]):
                            continue              # 「03_flows.md D-13」「PLAN.md D-02」指的是別份文件
                        self.red('已取消', f"{f} 的 {did} 已取消，仍被引用：{f2}:{no}")
                        break
            cancelled += dead
        gone = [x for k in ('entities', 'relations') for x in (self.data.get(k) or [])
                if x.get('status') in ('superseded', 'retired')]
        for x in gone:
            pat = word(x['name'])
            for f, no, h2, h3, text in self.lines():
                if pat.search(text or ''):
                    self.red('已取消', f"core/ 的 {x['name']} 已{'取代' if x['status'] == 'superseded' else '停用'}，"
                                     f"仍被引用：{f}:{no}")
        if not cancelled and not gone:
            print("    ✓ 通過（沒有取消或停用的項目）")
        else:
            self.done('已取消', len(cancelled) + len(gone), '個取消或停用的項目')

    def check_ids(self):
        print("\n[編號存在] 引用的驗收問題、規則、Entity、事件、EQ、草稿 US 都存在")
        cq_ids = {q['id'] for q in self.data.get('cq') or []}
        ents = {e['name'] for e in self.data.get('entities') or []}
        flows = self.data.get('flows') or {}
        events = {e['name'] for e in flows.get('events', [])}
        rules = (self.data.get('rules') or {}).get('rules', [])
        live_rules = {r['id'] for r in rules if r.get('status') != 'cancelled'}
        all_rules = {r['id'] for r in rules}
        n = 0
        new_ents = [e for e in self.data.get('entities') or [] if e.get('origin') == 'new']
        for e in new_ents:
            for q in e.get('required_by_cq') or []:
                n += 1
                if ':' not in q and q not in cq_ids:
                    self.red('編號', f"{e['name']} 的對應驗收問題 {q} 不在 01_scope.md")
        for sm in flows.get('state_machines', []):
            for t in sm['transitions']:
                for r in t.get('rules') or []:
                    n += 1
                    if r not in all_rules:
                        self.red('編號', f"{sm['entity']} {t['from']}→{t['to']} 的規則 {r} 不存在")
        ucs, cover = self.use_cases()
        for uc in ucs:
            for kind, pool, label in (('entities', ents, 'Entity'), ('events', events, '事件'),
                                      ('rules', all_rules, '規則')):
                for x in uc[kind]:
                    n += 1
                    if x not in pool:
                        self.red('編號', f"{uc['id']} 用到的{label} {x} 沒有宣告"
                                        f"（03_use_cases.md:{uc.get(kind + '_line', uc['line'])}）")
        uc_ids_all = {u['id'] for u in self.use_cases()[0]}
        for r in rules:
            if r.get('status') == 'cancelled' or not r.get('applies_to_text'): continue
            ts = targets(r['applies_to_text'])
            if not ts:
                self.red('編號', f"{r['id']} 的套用對象「{r['applies_to_text']}」沒有寫 Entity、事件、規則或 UC 的編號")
            for a in ts:
                n += 1
                if a not in ents and a not in events and a not in all_rules and a not in uc_ids_all:
                    self.red('編號', f"{r['id']} 的套用對象 {a} 不是已宣告的 Entity、事件、規則或 UC")
        qpath = os.path.join(self.dir, 'questions.md')
        eqs = set()
        if os.path.exists(qpath):
            with open(qpath, encoding='utf-8') as f:
                for line in f:
                    m = re.match(r'^(?:\|\s*|#+\s*)(EQ-\d+)', line)
                    if m: eqs.add(m.group(1))
        for f, no, h2, h3, text in self.lines(history=True):
            for eq in re.findall(r'\[待專家確認[:：]\s*(EQ-\d+)\]', text or ''):
                n += 1
                if eq not in eqs:
                    self.red('編號', f"{f}:{no} 的 {eq} 不在 questions.md")
        us_ids = []
        d01 = self.docs.get('01_scope.md')
        if d01:
            for h2, h3, header, rows in d01.tables():
                if h2 == '草稿 User Story' and header[0] == '編號':
                    us_ids += [c[0] for no, c in rows]
        uc_ids = {u['id'] for u in ucs}
        covered = {us: ids for no, us, ids in cover}
        if us_ids and ucs:
            for us in us_ids:
                n += 1
                if not covered.get(us):
                    self.red('編號', f"草稿 {us} 沒有被任何 UC 涵蓋（03_use_cases.md 的草稿涵蓋檢查）")
                else:
                    for u in covered[us]:
                        if u not in uc_ids: self.red('編號', f"草稿 {us} 的涵蓋 {u} 不存在")
        self.done('編號', n, '個引用')

    def check_glossary(self):
        print("\n[詞彙對照表] 本切片定義的 Entity、屬性、關係、事件、狀態、分類值都在詞彙對照表")
        terms = {t['id'] for t in self.data.get('glossary') or []}
        defs = self.slice_defs(self.dir)
        want = ([('Entity', e) for e in defs['entity']] +
                [('屬性', f'{e}.{a}') for e, a in defs['attribute']] +
                [('關係', r) for r in defs['relation']] + [('事件', e) for e in defs['event']] +
                [('狀態', f'{e}.{s}') for e, s in defs['state']] +
                [('分類值', c) for c in defs['code']])
        missing = {}
        for kind, i in want:
            if i not in terms: missing.setdefault(kind, []).append(i)
        for kind, ids in missing.items():
            shown = '、'.join(sorted(ids)[:8]) + ('…' if len(ids) > 8 else '')
            self.red('詞彙', f"{kind} {len(ids)} 個不在詞彙對照表：{shown}")
        self.done('詞彙', len(want), '個名稱')

    def check_proposal(self):
        print("\n[建議層] 「建議」層的事件不改變狀態")
        evts = (self.data.get('flows') or {}).get('events', [])
        props = [e for e in evts if e.get('layer') == 'proposal']
        for e in props:
            if e.get('changes') not in (None, 'none'):
                self.red('建議層', f"{e['name']} 是建議層，卻改變狀態：{e['changes']}")
        self.done('建議層', len(props), '個建議層事件')

    def check_markers(self):
        print("\n[標記] 只用 docs/02 第三節的寫法")
        n = 0
        for f, no, h2, h3, text in self.lines(history=True):
            for m in re.finditer(r'(?<!`)\[([^\[\]]+)\](?!\()', text or ''):
                inner = m.group(1).strip()
                if inner in ('', ' ', 'x', 'X') or inner.startswith('#') or inner.startswith('<'): continue
                n += 1
                if not MARKER_RE.match(inner):
                    self.red('標記', f"{f}:{no} 的「[{inner}]」不是規定的標記")
        self.done('標記', n, '個標記')

    def check_paths(self):
        print("\n[路徑] 引用的 inputs/ 檔案都存在")
        files = [os.path.join(self.dir, f) for f in self.docs] + \
                [os.path.join(self.root, 'slices', f) for f in ('PLAN.md', 'ENTITY_SKETCH.md')]
        n = 0
        for path in files:
            if not os.path.exists(path): continue
            with open(path, encoding='utf-8') as fh:
                for no, line in enumerate(fh, 1):
                    for p in re.findall(r'inputs/[^\s，、；：:（）()「」|`*\[\]<>]+', line):
                        p = p.split('#')[0].rstrip('.。')
                        n += 1
                        if not os.path.exists(os.path.join(self.root, p)):
                            self.red('路徑', f"{self.rel(path)}:{no} 引用的 {p} 不存在")
        self.done('路徑', n, '個路徑')

    def check_versions(self):
        print("\n[版本] 未凍結交付物的「讀取的輸入」是上游最新的 tag；每個 tag 在 CHANGELOG 都有一筆")
        tags = self.tags()
        if tags is None:
            return self.done('版本', 0, '', skipped='不是 git repo')
        n = 0
        for f, d in self.docs.items():
            status = inputs = None
            for h2, h3, header, rows in d.tables():
                if header[:2] == ['項目', '內容']:
                    for no, c in rows:
                        if c[0] == '狀態': status = c[1]
                        if c[0] == '讀取的輸入': inputs = (no, c[1])
                    break
            if not inputs or status == '已凍結': continue
            for step, ver in re.findall(rf'{re.escape(self.slice)}/0(\d)-v(\d+)', inputs[1]):
                n += 1
                latest = self.latest_tag(int(step), tags)
                if latest and int(latest.split('-v')[-1]) > int(ver):
                    self.red('版本', f"{f}:{inputs[0]} 讀取的輸入寫 0{step}-v{ver}，最新是 {latest}")
        log = os.path.join(self.dir, 'CHANGELOG.md')
        text = open(log, encoding='utf-8').read() if os.path.exists(log) else ''
        for t in tags:
            n += 1
            if t not in text: self.red('版本', f"tag {t} 在 CHANGELOG.md 沒有對應的一筆")
        self.done('版本', n, '個版本引用與 tag')

    def check_pending(self):
        print("\n[提出／同意] 「決定與理由」沒有「待確認」" + ("（準備凍結）" if self.freeze else "（凍結前要清空）"))
        n, pend, old = 0, 0, []
        for f, d in self.docs.items():
            for h2, h3, header, rows in d.tables():
                if h2 != '決定與理由' or header[:2] != ['#', '決定']: continue
                k = mb.col(header, '提出')
                if k is None:
                    old.append(f); continue
                for no, c in rows:
                    n += 1
                    if '待確認' in c[k]:
                        pend += 1
                        msg = f"{f}:{no} {c[0]} 待確認"
                        if self.freeze: self.red('待確認', msg)
                        else: print(f"    • {msg}")
        if old:
            print(f"    – 舊格式（沒有「提出／同意」欄）：{'、'.join(sorted(set(old)))}")
        self.done('待確認', n, '個決定', skipped=None if n else ('都是舊格式' if old else None))

    def check_parse(self):
        print("[格式] 每一列都看得懂（md2build 的解析：表格欄數、固定選項、卡片結構）")
        for path, no, msg in self.parse_problems:
            self.red("格式", f"{os.path.normpath(self.rel(path) if os.path.isabs(path) else path)}:{no} {msg}")
        if self.parse_problems:
            print("    看不懂的列沒有納入以下檢查。")
        else:
            print("    ✓ 通過")
        print()

    def run(self):
        self.check_parse()
        self.check_residue(); self.check_cancelled(); self.check_ids(); self.check_glossary()
        self.check_proposal(); self.check_markers(); self.check_paths(); self.check_versions()
        self.check_pending()
        print(f"\n{'='*40}")
        print(f"引用檢查：紅燈 {len(self.fails)} 項、未檢查 {len(self.skipped)} 項")
        print("只代表引用與結構對得起來，不代表內容正確；docs/02 第七節標「AI 判斷」的項目要另外判斷。")
        return 1 if self.fails else 0

def main():
    args = sys.argv[1:]
    if not args or '--help' in args:
        print(__doc__); return 0
    root, baseline = '.', None
    for opt in ('--root', '--baseline'):
        if opt in args:
            i = args.index(opt)
            if opt == '--root': root = args[i + 1]
            else: baseline = args[i + 1]
            del args[i:i + 2]
    freeze = '--freeze' in args
    args = [a for a in args if a != '--freeze']
    if not os.path.isdir(os.path.join(root, 'slices', args[0])):
        print(f'找不到 slices/{args[0]}/'); return 1
    return Lint(root, args[0], freeze, baseline).run()

if __name__ == '__main__':
    sys.exit(main())
