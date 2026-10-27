#!/usr/bin/env python3
"""引用檢查：docs/02 第七節中可以用程式比對的項目，加上改名後的殘留與已取消項目的引用。
直接讀 Markdown（用 md2build.py 的解析），不需要先轉 YAML。
用法：python tools/lint.py <切片代號> [--root <repo 根目錄>] [--freeze] [--baseline <目錄>]
  --freeze：準備凍結時使用，「提出／同意」有「待確認」就亮紅燈（平常只列出）。
  --baseline：上一版的切片資料夾（預設取各步驟最新的 git tag），用來找被刪除或改名的名稱。
  表格、EQ 影響、範圍外、佔位符、黃金案例（含事後才到的輸入）、連鎖、core 前綴（--freeze 時亮紅燈）、被引用也在這裡檢查；
  審查頁（--freeze 時沒作答的亮紅燈）、挑錯反例、黃金案例自給自足也在這裡檢查；
  「用在」「舊版上游」「使用者同意」只列提醒，不算紅燈。
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

OTHER_SLICE_ID = r'[a-z][a-z0-9-]*:(?:UC-\d+|US-D\d+|Q\d+)'   # 其他切片的編號（hire-employee:UC-14）

def targets(text):
    """套用對象中的識別名稱、規則編號（展開 R22～R28）、UC 編號。
    `Entity.attribute` 算 Entity；括號裡的說明文字只取其中的規則與 UC 編號。"""
    text = re.sub(OTHER_SLICE_ID, ' ', text or '')   # 其他切片的編號不在本切片比對
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
            if not ts and not re.search(OTHER_SLICE_ID, r['applies_to_text']):
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

    # ---------- 2026-10-21 新增（流程待處理清單 #1、#2、#11～#18） ----------
    def md_files(self):
        """表格檢查的範圍：本切片、slices/ 根目錄、core/、inputs/ 的所有 Markdown。"""
        out = []
        for base, recursive in ((self.dir, True), (os.path.join(self.root, 'slices'), False),
                                (os.path.join(self.root, 'core'), True), (os.path.join(self.root, 'inputs'), True)):
            if not os.path.isdir(base): continue
            if recursive:
                for d, _, fs in os.walk(base):
                    out += [os.path.join(d, f) for f in sorted(fs) if f.endswith('.md')]
            else:
                out += [os.path.join(base, f) for f in sorted(os.listdir(base)) if f.endswith('.md')]
        return out

    def quiet_tables(self, path):
        """讀表格但不把問題記進 md2build 的全域清單：回傳 (表格, 欄數不對的列)。"""
        saved = list(mb.problems)
        doc = mb.Doc(path)
        tables = doc.tables()
        bad = [(no, msg) for p, no, msg in mb.problems[len(saved):]]
        mb.problems[:] = saved
        # 不屬於任何表格的「| …」列（例：表格中間多一行空行，後面的列就斷開了）
        lines = [(no, l) for no, h2, h3, l in doc.items if l is not None]
        inside = set()
        for i, (no, l) in enumerate(lines):
            nxt = lines[i + 1][1] if i + 1 < len(lines) else ''
            if l.strip().startswith('|') and re.match(r'^\s*\|[\s:|-]+\|\s*$', nxt) and '-' in nxt:
                j = i
                while j < len(lines) and lines[j][1].strip().startswith('|'):
                    inside.add(lines[j][0]); j += 1
        for no, l in lines:
            if l.strip().startswith('|') and l.strip().endswith('|') and no not in inside:
                bad.append((no, '這列不屬於任何表格（前面可能多了空行，或少了表頭與分隔列）'))
        return tables, bad

    OPTIONS = {   # (檔名, h2, 欄名) → 允許的值（開頭符合，後面可接括號說明）
        ('questions.md', None, '狀態'): ['待問', '已問', '暫依整理', '已回覆'],
        ('PLAN.md', '現實資料盤點', '狀態'): ['已有', '已蒐集', '推想草稿', '待提供', '找不到'],
        ('PLAN.md', '切片', '大小估計'): ['太小', '剛好', '太大'],
        ('PLAN.md', '切片', '狀態'): ['候選', '進行中', '設計完成（待驗證）', '完成', '擱置', '已拆分', '已合併'],
        ('ENTITY_SKETCH.md', '名詞', '層'): ['core', 'shared', 'domain'],
        ('ENTITY_SKETCH.md', '名詞', '狀態'): ['草圖', '已定義', '已取消'],
    }

    def check_tables(self):
        print("\n[表格] slices/、core/、inputs/ 所有表格的欄數等於表頭；固定選項欄位只用規定的值")
        seen = {(os.path.normpath(p if os.path.isabs(p) else os.path.join(self.root, p)), no)
                for p, no, _ in self.parse_problems}
        n = 0
        for path in self.md_files():
            tables, bad = self.quiet_tables(path)
            for no, msg in bad:
                if (os.path.normpath(path), no) in seen: continue      # 「格式」已列過
                self.red('表格', f"{self.rel(path)}:{no} {msg}")
            name = os.path.basename(path)
            for h2, h3, header, rows in tables:
                n += len(rows) + 1
                for (fname, sec, colname), allowed in self.OPTIONS.items():
                    if fname != name or (sec and h2 != sec): continue
                    if fname == 'questions.md' and header[0] != '編號': continue
                    k = header.index(colname) if colname in header else None
                    if k is None: continue
                    for no, c in rows:
                        v = c[k].strip()
                        if v in allowed or any(v.startswith(a) and v[len(a):len(a) + 1] in '（(；; ' for a in allowed):
                            continue
                        self.red('表格', f"{self.rel(path)}:{no} 「{colname}」的值「{v}」不在規定的選項（{'、'.join(allowed)}）")
        self.done('表格', n, '列')

    def check_placeholders(self):
        print("\n[佔位符] 切片檔案沒有殘留範本的 {{切片}}")
        n = 0
        for d, _, fs in os.walk(self.dir):
            for f in sorted(fs):
                if not f.endswith(('.md', '.yaml', '.sql')): continue
                path = os.path.join(d, f)
                n += 1
                with open(path, encoding='utf-8') as fh:
                    for no, line in enumerate(fh, 1):
                        if re.search(r'\{\{?切片\}?\}', line):
                            self.red('佔位符', f"{self.rel(path)}:{no} 還有範本的佔位符：{line.strip()[:60]}")
        self.done('佔位符', n, '個檔案')

    ID_RE = r'(?<![A-Za-z0-9_-])((?:US-D|UC-|D-|X-|GC|Q|R)\d+|[A-Z][a-z]+(?:[A-Z][a-z0-9]*)+)(?![A-Za-z0-9_])'
    ITEM_RE = re.compile(r'\s*`?((?:US-D|UC-|EQ-|CR-|D-|X-|P-|GC|Q|R|C)\d+|[A-Za-z][A-Za-z0-9_]*)')

    @staticmethod
    def expand(text):
        """「R65～R67」「Q01～Q14」展開成每個編號，其餘照原樣。"""
        def rep(m):
            p, a, b = m.group(1), m.group(2), m.group(4)
            w = len(a)
            return '、'.join(f'{p}{i:0{w}d}' for i in range(int(a), int(b) + 1)) if int(b) - int(a) < 200 else m.group(0)
        return re.sub(r'((?:US-D|UC-|EQ-|D-|X-|GC|Q|R|C))(\d+)～(\1)?(\d+)', rep, text)

    def check_eq_impact(self):
        print("\n[EQ 影響] 每個 [待專家確認: EQ-nnn] 所在的項目，都列在該 EQ 的「影響」")
        qpath = os.path.join(self.dir, 'questions.md')
        if not os.path.exists(qpath):
            return self.done('EQ影響', 0, '')
        impact = {}
        for h2, h3, header, rows in self.quiet_tables(qpath)[0]:
            k = header.index('影響') if '影響' in header else None
            if header[0] != '編號' or k is None: continue
            for no, c in rows:
                segs = {}
                for seg in re.split(r'[；;]', self.expand(c[k])):
                    seg = re.sub(r'^\s*內文未標[：:]\s*', '', seg.strip())
                    m = re.match(r'(0\d(?:_[a-z_]+)?)(?:\.md)?\s*(.*)$', seg)
                    if m: segs.setdefault(m.group(1)[:2] + ('u' if 'use_cases' in m.group(1) else ''), []).append(m.group(2))
                impact[c[0]] = segs
        if not impact:
            return self.done('EQ影響', 0, '', skipped='questions.md 沒有「影響」欄')
        n = 0
        for f, d in self.docs.items():
            fkey = f[:2] + ('u' if 'use_cases' in f else '')
            for no, h2, h3, line in d.items:
                text = h3 if line is None else line
                eqs = re.findall(r'\[待專家確認[:：]\s*(EQ-\d+)\]', text or '')
                if not eqs or (h2 or '') in ('檢查紀錄', '回填紀錄'): continue
                cands, label = [], None                      # 項目：這一列的編號與英文名稱、所屬標題
                if line is not None and line.strip().startswith('|'):
                    cells = mb.split_row(line)
                    m = self.ITEM_RE.match(cells[0])
                    if m: cands.append(m.group(1)); label = m.group(1)
                    cands += re.findall(self.ID_RE, line)
                for h in (h3, h2):
                    if h:
                        m = self.ITEM_RE.match(h); cands += [m.group(1)] if m else []
                        cands += re.findall(self.ID_RE, h)
                        cands.append(re.sub(r'[（(].*$', '', h).strip())
                        label = label or (m.group(1) if m else cands[-1])
                for eq in sorted(set(eqs)):
                    if eq not in impact: continue            # 不存在的 EQ 由 [編號存在] 檢查
                    n += 1
                    seg = ' '.join(impact[eq].get(fkey, []))
                    if not any(c and word(c).search(seg) for c in cands):
                        self.red('EQ影響', f"{f}:{no} 的 {eq} 在 {label}，questions.md 的「影響」沒有列出（{f[:-3]} {label}）")
        self.done('EQ影響', n, '個標記')

    def plan_slices(self):
        path = os.path.join(self.root, 'slices', 'PLAN.md')
        if not os.path.exists(path): return None
        out = set()
        for h2, h3, header, rows in self.quiet_tables(path)[0]:
            if h2 == '切片' and header[0] == '切片':
                out |= {c[0].strip('` ') for no, c in rows}
        return out

    def check_out_of_scope(self):
        print("\n[範圍外] ①「範圍外但會用到」的歸屬切片存在於切片地圖")
        d = self.docs.get('01_scope.md')
        plan = self.plan_slices()
        if d is None:
            return self.done('範圍外', 0, '')
        if plan is None:
            return self.done('範圍外', 0, '', skipped='沒有 slices/PLAN.md')
        n = 0
        for h2, h3, header, rows in d.tables():
            if h2 != '範圍外但會用到': continue
            k = mb.col(header, '歸屬')
            if k is None: continue
            for no, c in rows:
                words = re.findall(r'(?<![\w/.-])([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![\w.-])', c[k])
                n += 1
                if not [w for w in words if w in plan]:
                    self.red('範圍外', f"01_scope.md:{no} 歸屬「{c[k]}」沒有寫切片地圖上的切片代號")
        self.done('範圍外', n, '列')

    def check_param_storage(self):
        print("\n[參數存放] ⑤「參數放在哪裡」列出 ④ 參數表的每個參數")
        d4, d5 = self.docs.get('04_rules.md'), self.docs.get('05_mapping.md')
        if d4 is None or d5 is None:
            return self.done('參數存放', 0, '')
        names = []
        for h2, h3, header, rows in d4.tables():
            k = mb.col(header, '參數')
            if h2 != '參數' or h3 or k is None: continue
            names += [(no, c[k].strip().strip('`')) for no, c in rows if c[k].strip().strip('`')]
        text = '\n'.join('｜'.join(c) for h2, h3, header, rows in d5.tables()
                         if '參數放在哪裡' in (h3 or h2 or '') for _, c in rows)
        if names and not text:
            self.red('參數存放', f"05_mapping.md 沒有「參數放在哪裡」表（④ 參數表有 {len(names)} 個參數）")
        else:
            for no, name in names:
                if not word(name).search(text):
                    self.red('參數存放', f"04_rules.md:{no} 參數 {name} 沒有列在 05_mapping.md「參數放在哪裡」")
        self.done('參數存放', len(names), '個參數')

    GC_VALUES = {'紙上判定': ['一致', '不一致', '[未執行]', '不採用'], '判定': ['通過', '失敗', '[未執行]', '不採用']}

    def check_golden(self):
        print("\n[黃金案例] 「紙上判定」「判定」只用規定的值；不採用的兩欄一致")
        path = os.path.join(self.dir, '06_evidence', 'golden_cases.md')
        if not os.path.exists(path):
            return self.done('黃金案例', 0, '')
        cases = self.golden_cases(path)
        for gc in cases:
            for key, allowed in self.GC_VALUES.items():
                if key not in gc:
                    self.red('黃金案例', f"golden_cases.md {gc['id']} 沒有「{key}」"); continue
                no, v = gc[key]
                if not any(v == a or (v.startswith(a) and v[len(a):len(a) + 1] in '（(；;。，: ') for a in allowed):
                    self.red('黃金案例', f"golden_cases.md:{no} {gc['id']} 的「{key}」是「{v}」，只能是 {'、'.join(allowed)}")
            vals = [gc[k][1] for k in self.GC_VALUES if k in gc]
            if any(v.startswith('不採用') for v in vals) and not all(v.startswith('不採用') for v in vals):
                self.red('黃金案例', f"golden_cases.md {gc['id']} 只有一欄寫「不採用」，兩欄要一致")
        self.done('黃金案例', len(cases), '個案例')

    def doc_status(self, d):
        for h2, h3, header, rows in d.tables():
            if header[:2] == ['項目', '內容']:
                return next((c[1] for no, c in rows if c[0] == '狀態'), None)

    def golden_cases(self, path):
        """golden_cases.md 的案例：[{'id', 'no', '紙上判定': (行號, 值), '判定': (行號, 值)}]。"""
        cases, cur = [], None
        for no, h2, h3, line in mb.Doc(path).items:
            if h3 is None and h2 and re.match(r'GC\d+', h2) and (cur is None or cur['id'] != h2.split()[0]):
                cur = {'id': h2.split()[0], 'no': no}; cases.append(cur)
            m = re.match(r'^- (紙上判定|判定)[：:]\s*(.*)$', line or '')
            if cur and m: cur[m.group(1)] = (no, m.group(2).strip())
        return cases

    def check_late_inputs(self):
        print("\n[事後輸入] 黃金案例的「事後才到的輸入」每一列有案例或沒挑的理由")
        path = os.path.join(self.dir, '06_evidence', 'golden_cases.md')
        if not os.path.exists(path):
            return self.done('事後輸入', 0, '')
        cases = self.golden_cases(path)
        adopted = {gc['id'] for gc in cases if not gc.get('紙上判定', (0, ''))[1].startswith('不採用')}
        table = next(((header, rows) for h2, h3, header, rows in mb.Doc(path).tables()
                      if h2 == '事後才到的輸入' and not h3), None)
        if table is None:
            if not adopted:
                return self.done('事後輸入', 0, '')
            msg = "golden_cases.md 沒有「事後才到的輸入」表（docs/02 ⑥）"
            tags = self.tags()
            if tags and self.latest_tag(5, tags):
                print(f"    • {msg}；⑤ 在這項規定之前凍結過，不回頭補，回頭修改 ⑤ 時可以補上")
                return self.done('事後輸入', 0, '', skipped='⑤ 已凍結過，只提醒')
            self.red('事後輸入', msg)
            return self.done('事後輸入', 1, '張表')
        header, rows = table
        k, r = mb.col(header, '案例'), mb.col(header, '沒挑的理由')
        if k is None or r is None:
            self.red('事後輸入', "golden_cases.md「事後才到的輸入」表要有「案例」「沒挑的理由」兩欄")
            return self.done('事後輸入', 1, '張表')
        known = {gc['id'] for gc in cases}
        for no, c in rows:
            ids = re.findall(r'GC\d+', c[k])
            for gid in ids:
                if gid not in known:
                    self.red('事後輸入', f"golden_cases.md:{no} 的 {gid} 不存在")
                elif gid not in adopted:
                    self.red('事後輸入', f"golden_cases.md:{no} 的 {gid} 是「不採用」，不算涵蓋；改挑它或寫沒挑的理由")
            if not ids and not c[r].strip():
                self.red('事後輸入', f"golden_cases.md:{no} 沒有案例，也沒寫沒挑的理由")
        self.done('事後輸入', len(rows), '種輸入')

    def core_events(self):
        """core/flows.md 的事件：{名稱: (行號, 出處, 連鎖 或 None)}；沒有「連鎖」欄時為 None。"""
        path = os.path.join(self.root, 'core', 'flows.md')
        if not os.path.exists(path): return {}
        out = {}
        for h2, h3, header, rows in mb.Doc(path).tables():
            if not header or header[0] != '事件' or mb.col(header, '出處') is None: continue
            src, chain = mb.col(header, '出處'), mb.col(header, '連鎖')
            for no, c in rows:
                name = re.split(r'[（(\s]', c[0].strip().strip('`'), 1)[0]
                out[name] = (no, c[src], None if chain is None else c[chain])
        return out

    CHAIN_TIMING = ['同一交易', '之後']

    def check_chain(self):
        print("\n[連鎖] ⑤「其他切片事件的連鎖」的上游事件，core/flows.md「連鎖」欄有本切片")
        d5 = self.docs.get('05_mapping.md')
        if d5 is None:
            return self.done('連鎖', 0, '')
        frozen = self.doc_status(d5) == '已凍結'
        core, own = self.core_events(), self.slice_defs(self.dir)['event']
        n = 0
        for h2, h3, header, rows in d5.tables():
            k = mb.col(header, '上游事件')
            if k is None or '連鎖' not in (h3 or h2 or ''): continue
            t = mb.col(header, '時機')
            for no, c in rows:
                if t is not None and c[t].strip() not in self.CHAIN_TIMING:
                    self.red('連鎖', f"05_mapping.md:{no} 的「時機」是「{c[t]}」，只能是 {'、'.join(self.CHAIN_TIMING)}")
                for name in dict.fromkeys(re.findall(r'(?<![A-Za-z0-9_.])[A-Z][A-Za-z0-9]+(?![A-Za-z0-9_])', c[k])):
                    if name in own: continue
                    if name not in core:
                        print(f"    • 05_mapping.md:{no} 的上游事件 {name} 不在 core/flows.md"); continue
                    cno, src, chain = core[name]
                    if src.strip().startswith(self.slice): continue
                    n += 1
                    if chain is not None and word(self.slice).search(chain): continue
                    msg = (f"core/flows.md 的事件表沒有「連鎖」欄（{name}）" if chain is None else
                           f"core/flows.md:{cno} {name} 的「連鎖」沒有 {self.slice}（05_mapping.md:{no}）")
                    if frozen: self.red('連鎖', msg)
                    else: print(f"    • {msg}（⑤ 凍結時寫入）")
        self.done('連鎖', n, '個上游事件')

    def check_core_prefix(self):
        print("\n[core 前綴] core/ 中沒有不帶切片前綴的 Qnn、US-Dnn、UC-nn" + ("（準備凍結）" if self.freeze else "（凍結時要清空）"))
        base = os.path.join(self.root, 'core')
        if not os.path.isdir(base):
            return self.done('core前綴', 0, '')
        n = 0
        for d, _, fs in os.walk(base):
            for f in sorted(fs):
                if not f.endswith('.md') or f == 'CHANGELOG.md': continue
                path = os.path.join(d, f)
                n += 1
                with open(path, encoding='utf-8') as fh:
                    in_comment = False
                    for no, line in enumerate(fh, 1):
                        if '<!--' in line: in_comment = '-->' not in line; continue
                        if in_comment:
                            in_comment = '-->' not in line; continue
                        for m in re.finditer(r'(?<![\w:-])(US-D\d+|UC-\d+|Q\d{2,})(?![\w-])', line):
                            msg = f"{self.rel(path)}:{no} 的 {m.group(1)} 沒有切片前綴（寫成 <切片>:{m.group(1)}）"
                            if self.freeze: self.red('core前綴', msg)
                            else: print(f"    • {msg}")
        self.done('core前綴', n, '個檔案')

    def check_referenced_by(self):
        print("\n[被引用] 本切片引用的 core/ Entity，「被引用」有列出本切片")
        d = self.docs.get('02_entities.md')
        if d is None:
            return self.done('被引用', 0, '')
        status = None
        for h2, h3, header, rows in d.tables():
            if header[:2] == ['項目', '內容']:
                status = next((c[1] for no, c in rows if c[0] == '狀態'), None); break
        saved = list(mb.problems)
        refs = mb.parse_refs(d)
        mb.problems[:] = saved
        core = {e['name']: e for e in self.data.get('entities') or [] if 'source' in e}
        n = 0
        for name in refs:
            e = core.get(name)
            if not e or (e.get('source') or '').startswith(self.slice): continue
            n += 1
            if not any(x.startswith(self.slice) for x in e.get('referenced_by') or []):
                msg = f"core/entities.md 的 {name} 被本切片引用，「被引用」沒有 {self.slice}"
                if status == '已凍結' or self.freeze: self.red('被引用', msg)
                else: print(f"    • {msg}（② 凍結時補上）")
        self.done('被引用', n, '個引用（目前只比對 Entity）')

    def check_used_in(self):
        print("\n[用在] 本切片引用的 research 條目，「用在」有寫本切片（提醒，不算紅燈）")
        rdir = os.path.join(self.root, 'inputs', 'research')
        if not os.path.isdir(rdir):
            return self.done('用在', 0, '')
        topics = {f[:-3] for f in os.listdir(rdir) if f.endswith('.md') and f != 'INDEX.md'}
        cited = set()
        for f, no, h2, h3, text in self.lines(history=True):
            for t, num in re.findall(r'([^\s（(「」、，；：:|`*]+)#(\d+)', text or ''):
                if t in topics: cited.add((t, num))
        used = {}
        for t in topics:
            cur = None
            with open(os.path.join(rdir, t + '.md'), encoding='utf-8') as fh:
                for line in fh:
                    m = re.match(rf'^#+\s*{re.escape(t)}#(\d+)', line)
                    if m: cur = m.group(1)
                    m = re.match(r'^- 用在[：:]\s*(.*)$', line)
                    if m and cur: used[(t, cur)] = m.group(1)
        miss = sorted(k for k in cited if k in used and self.slice not in used[k])
        for t, num in miss:
            print(f"    • {t}#{num} 的「用在」沒有 {self.slice}（只可追加，INDEX.md 一起改）")
        if cited and not miss:
            print(f"    ✓ 通過（檢查了 {len(cited)} 個條目）")
        elif not cited:
            self.done('用在', 0, '')
        else:
            print(f"    （檢查了 {len(cited)} 個條目，{len(miss)} 個要追加）")

    def check_stale_frozen(self):
        print("\n[舊版上游] 已凍結交付物讀的是舊版上游時列出來，作為回歸判斷的清單（提醒，不擋凍結）")
        tags = self.tags()
        if tags is None:
            return self.done('舊版上游', 0, '', skipped='不是 git repo')
        log = os.path.join(self.dir, 'CHANGELOG.md')
        heads = [l.strip() for l in open(log, encoding='utf-8')] if os.path.exists(log) else []
        heads = [h for h in heads if h.startswith('## ')]
        n = hits = 0
        for f, d in self.docs.items():
            status = inputs = None
            for h2, h3, header, rows in d.tables():
                if header[:2] == ['項目', '內容']:
                    for no, c in rows:
                        if c[0] == '狀態': status = c[1]
                        if c[0] == '讀取的輸入': inputs = (no, c[1])
                    break
            if not inputs or status != '已凍結': continue
            for step, ver in re.findall(rf'{re.escape(self.slice)}/0(\d)-v(\d+)', inputs[1]):
                n += 1
                latest = self.latest_tag(int(step), tags)
                if not latest or int(latest.split('-v')[-1]) <= int(ver): continue
                hits += 1
                print(f"    • {f}（已凍結）讀 0{step}-v{ver}，上游最新是 {latest}；上游之後的紀錄：")
                newer = [f'{self.slice}/0{step}-v{v}' for v in range(int(ver) + 1, int(latest.split('-v')[-1]) + 1)]
                for h in heads:
                    if any(t in h for t in newer): print(f"        {h[3:]}")
        if n == 0:
            self.done('舊版上游', 0, '')
        elif hits == 0:
            print(f"    ✓ 通過（檢查了 {n} 個版本引用）")
        else:
            print(f"    （{hits} 處；依 docs/01 0.9 回歸範圍判斷要不要回頭，不用回頭的不必改）")


    # ---------- 2026-10-27 新增（流程待處理清單 #19～#38） ----------
    STEP_OF = {'01_scope.md': 1, '02_entities.md': 2, '03_flows.md': 3, '04_rules.md': 4, '05_mapping.md': 5}

    def review_refs(self):
        """各步檔案檢查紀錄的「審查頁」行：{檔名: (行號, [reviews/…])}；沒有這一行的是舊格式，不列入。"""
        out = {}
        for f, d in self.docs.items():
            if f not in self.STEP_OF: continue
            for no, h2, h3, line in d.items:
                m = re.match(r'^- 審查頁[：:]\s*(.*)$', line or '')
                if m and (h2 or '') == '檢查紀錄':
                    out[f] = (no, re.findall(r'reviews/[^\s、，,；;）)]+\.md', m.group(1)))
        return out

    @staticmethod
    def parse_review(path):
        """審查頁：問題、確認列、抽查、結論、黃金案例、這輪的挑錯。"""
        lines = open(path, encoding='utf-8').read().split('\n')
        r = {'questions': [], 'confirms': [], 'spot': None, 'verdicts': [], 'cases': [], 'x_ids': [], 'lines': lines}
        h2 = h3 = None
        inside = False
        for i, l in enumerate(lines, 1):
            if '<!--' in l:
                inside = '-->' not in l.split('<!--', 1)[1]; continue
            if inside:
                inside = '-->' not in l; continue
            if l.startswith('## '):
                h2, h3 = l[3:].strip(), None; continue
            if l.startswith('### '):
                h3 = l[4:].strip()
                if h3.startswith('問題'):
                    r['questions'].append({'no': i, 'title': h3, 'fields': {}, 'options': 0})
                elif re.match(r'GC\d+', h3) and h2 and h2.startswith('三'):
                    r['cases'].append({'no': i, 'id': h3.split()[0], 'fields': {}})
                continue
            m = re.match(r'^- ([^：:]+)[：:]\s*(.*)$', l)
            if m and h3:
                k, v = m.group(1).strip(), m.group(2).strip()
                if r['questions'] and h3 == r['questions'][-1]['title'] and h3.startswith('問題'):
                    q = r['questions'][-1]
                    q['fields'][k] = (i, v)
                    if re.match(r'^[A-Z]（建議）$', k) or re.match(r'^[A-Z]$', k): q['options'] += 1
                elif r['cases'] and h3.split()[0] == r['cases'][-1]['id']:
                    r['cases'][-1]['fields'][k] = (i, v)
        for h2_, h3_, header, rows in mb.Doc(path).tables():
            if header[:2] == ['項目', '內容']:
                for no, c in rows:
                    if c[0] == '這輪的挑錯': r['x_ids'] = Lint.expand_ids(c[1])
            elif '原文' in header and '在哪裡' in header and '確認' in header:
                r['confirms'] += [(no, dict(zip(header, c))) for no, c in rows]
            elif header[:1] == ['抽查了哪幾條']:
                r['spot'] = [(no, c) for no, c in rows]
            elif header[:1] == ['步驟'] and '結論' in header:
                r['verdicts'] += [(no, dict(zip(header, c))) for no, c in rows if c[0].strip()]
        return r

    @staticmethod
    def expand_ids(text):
        out = []
        for m in re.finditer(r'X-(\d+)(?:\s*～\s*X?-?(\d+))?', text or ''):
            a, b = int(m.group(1)), int(m.group(2) or m.group(1))
            w = len(m.group(1))
            out += [f'X-{i:0{w}d}' for i in range(a, b + 1)] if b - a < 200 else [f'X-{m.group(1)}']
        return out

    def check_reviews(self):
        print("\n[審查頁] 送審的步驟有審查頁；問題附選項、原文對得上行號、自評部分與 ✗ 都在頁上" +
              ("（準備凍結：每一列都要已作答）" if self.freeze else "；列出還沒作答的"))
        refs = self.review_refs()
        if not refs:
            return self.done('審查頁', 0, '', skipped='沒有新格式（檢查紀錄有「審查頁」行）的交付物')
        n = 0
        pending = {}                                      # 審查頁 → [送審中的步驟檔]
        for f, (no, paths) in refs.items():
            status = self.doc_status(self.docs[f])
            if status != '待檢查': continue
            n += 1
            if not paths:
                self.red('審查頁', f"{f}:{no} 狀態是「待檢查」，檢查紀錄沒有寫審查頁（docs/02「審查頁」）"); continue
            path = os.path.join(self.dir, paths[-1])
            if not os.path.exists(path):
                self.red('審查頁', f"{f}:{no} 的 {paths[-1]} 不存在"); continue
            pending.setdefault(paths[-1], []).append(f)
        for rel, files in pending.items():
            path = os.path.join(self.dir, rel)
            r = self.parse_review(path)
            text = '\n'.join(r['lines'])
            unanswered = []
            for q in r['questions']:
                n += 1
                fl = q['fields']
                for need in ('問題', '你的回答'):
                    if need not in fl:
                        self.red('審查頁', f"{rel}:{q['no']} {q['title']} 沒有「{need}」")
                if not any(re.match(r'^[A-Z]（建議）$', k) for k in fl):
                    self.red('審查頁', f"{rel}:{q['no']} {q['title']} 沒有建議答案（A（建議））")
                if q['options'] < 2:
                    self.red('審查頁', f"{rel}:{q['no']} {q['title']} 除了建議答案，至少還要一個選項（B…）")
                if '你的回答' in fl and not fl['你的回答'][1]:
                    unanswered.append(f"{rel}:{fl['你的回答'][0]} {q['title']}")
            for no, c in r['confirms']:
                n += 1
                if not c.get('確認', '').strip():
                    unanswered.append(f"{rel}:{no} 確認第 {c.get('#', '?')} 列")
                self.check_excerpt(rel, no, c)
            if r['spot'] is None:
                self.red('審查頁', f"{rel} 沒有「抽查」表")
            elif not any(c[0].strip() for no, c in r['spot']):
                unanswered.append(f"{rel} 抽查")
            for no, c in r['verdicts']:
                miss = [k for k in c if k != '步驟' and not c[k].strip()]
                if miss: unanswered.append(f"{rel}:{no} 結論（{c['步驟']}）")
                elif self.freeze and not c.get('結論', '').strip().startswith('通過'):
                    self.red('審查頁', f"{rel}:{no} {c['步驟']} 的結論是「{c.get('結論')}」，不是「通過」")
            if not r['verdicts']:
                self.red('審查頁', f"{rel} 沒有「結論」表")
            for gc in r['cases']:
                for k in ('預期結果', '計算過程', '計算者'):
                    if not gc['fields'].get(k, (0, ''))[1]:
                        unanswered.append(f"{rel}:{gc['no']} {gc['id']} 的「{k}」"); break
            self.check_case_copies(rel, r)
            # 自評「部分」或 ✗ 的完成標準要在審查頁
            for f in files:
                for h2, h3, header, rows in self.docs[f].tables():
                    k = mb.col(header, 'AI 自評')
                    if h2 != '檢查紀錄' or k is None: continue
                    for no, c in rows:
                        v = c[k].strip()
                        if (v.startswith('部分') or v.startswith('✗')) and re.sub(r'\s+', '', c[0]) not in re.sub(r'\s+', '', text):
                            self.red('審查頁', f"{f}:{no} 自評「{v[:6]}」的完成標準沒有列在 {rel}（照抄完成標準原文）")
            for msg in unanswered:
                if self.freeze: self.red('審查頁', f"{msg} 還沒作答")
            if unanswered and not self.freeze:
                print(f"    • {rel}：還有 {len(unanswered)} 處沒作答（等審查者填；凍結前要填完）")
        self.done('審查頁', n, '個送審的步驟與題目')

    def check_excerpt(self, rel, no, c):
        where, quote = c.get('在哪裡', ''), c.get('原文', '')
        m = re.search(r'([\w./-]+\.(?:md|yaml|sql)):(\d+)', where)
        if not m:
            self.red('審查頁', f"{rel}:{no} 「在哪裡」要寫 `檔名:行號`（現在是「{where}」）"); return
        frags = [x for part in re.findall(r'「([^」]*)」', quote) for x in part.split('…') if len(x.strip()) >= 2]
        if not frags:
            self.red('審查頁', f"{rel}:{no} 「原文」要用「」照抄檔案中的文字"); return
        target = os.path.join(self.dir, m.group(1))
        if not os.path.exists(target):
            self.red('審查頁', f"{rel}:{no} 的 {m.group(1)} 不存在"); return
        lines = open(target, encoding='utf-8').read().split('\n')
        line = int(m.group(2))
        window = re.sub(r'\s+', '', ''.join(lines[max(0, line - 3):line + 2]))
        missing = [x for x in frags if re.sub(r'\s+', '', x) not in window]
        if missing:
            self.red('審查頁', f"{rel}:{no} 的原文「{missing[0][:30]}」在 {m.group(1)}:{line} 前後 2 行找不到（設計改了，或行號過期）")

    def check_case_copies(self, rel, r):
        path = os.path.join(self.dir, '06_evidence', 'golden_cases.md')
        if not r['cases'] or not os.path.exists(path): return
        gold, cur = {}, None
        for no, h2, h3, line in mb.Doc(path).items:
            if h3 is None and h2 and re.match(r'GC\d+', h2): cur = h2.split()[0]; gold[cur] = {}
            m = re.match(r'^- (預期結果|計算過程|計算者)[：:]\s*(.*)$', line or '')
            if cur and m: gold[cur][m.group(1)] = m.group(2).strip()
        for gc in r['cases']:
            for k in ('預期結果', '計算過程', '計算者'):
                v = gc['fields'].get(k, (0, ''))[1]
                if not v: continue
                g = gold.get(gc['id'], {}).get(k, '')
                if re.sub(r'\s+', '', g) != re.sub(r'\s+', '', v):
                    self.red('審查頁', f"{rel} {gc['id']} 的「{k}」和 golden_cases.md 不同（人填在審查頁的要逐字抄回）")

    def check_challenge(self):
        print("\n[挑錯] 送審的 ①～⑤ 有「AI 挑錯」的反例；審查頁「這輪的挑錯」列的 X-nn 存在")
        refs = self.review_refs()
        n = 0
        for f, (no, paths) in refs.items():
            d = self.docs[f]
            if self.doc_status(d) != '待檢查': continue
            n += 1
            xs, ai = set(), 0
            for h2, h3, header, rows in d.tables():
                if h3 == '反例處理' and header[:2] == ['#', '反例']:
                    k = mb.col(header, '來源')
                    for rno, c in rows:
                        xs.add(c[0].strip())
                        if k is not None and c[k].strip().startswith('AI 挑錯'): ai += 1
            if not ai:
                self.red('挑錯', f"{f} 送審了，「反例處理」沒有來源為「AI 挑錯」的反例（docs/01 該步完成標準）")
            if paths and os.path.exists(os.path.join(self.dir, paths[-1])):
                listed = self.parse_review(os.path.join(self.dir, paths[-1]))['x_ids']
                for x in listed:
                    if not any(x in self.x_ids(g) for g in self.docs if g in self.STEP_OF):
                        self.red('挑錯', f"{paths[-1]}「這輪的挑錯」的 {x} 不在任何一步的「反例處理」"); break
        self.done('挑錯', n, '個送審的交付物', skipped=None if n else ('沒有送審中的新格式交付物' if refs else None))

    def x_ids(self, f):
        out = set()
        for h2, h3, header, rows in self.docs[f].tables():
            if h3 == '反例處理' and header[:2] == ['#', '反例']:
                out |= {c[0].strip() for no, c in rows}
        return out

    def check_golden_selfcontained(self):
        print("\n[黃金案例自給自足] 採用的案例不寫「同 GCnn」「同上一個案例」")
        path = os.path.join(self.dir, '06_evidence', 'golden_cases.md')
        if not os.path.exists(path):
            return self.done('案例自足', 0, '')
        cases, cur = [], None
        for no, h2, h3, line in mb.Doc(path).items:
            if h3 is None and h2 and re.match(r'GC\d+', h2) and (cur is None or cur['id'] != h2.split()[0]):
                cur = {'id': h2.split()[0], 'lines': [], 'adopted': True}; cases.append(cur)
            if cur and line is not None:
                cur['lines'].append((no, line))
                m = re.match(r'^- 紙上判定[：:]\s*(.*)$', line)
                if m and m.group(1).strip().startswith('不採用'): cur['adopted'] = False
        n = 0
        for gc in cases:
            if not gc['adopted']: continue
            n += 1
            for no, line in gc['lines']:
                m = re.search(r'同\s*GC\d+|同(?:上|前)一?個?案例', line)
                if m:
                    self.red('案例自足', f"golden_cases.md:{no} {gc['id']} 寫了「{m.group(0)}」，把引用的內容寫進這個案例"); break
        self.done('案例自足', n, '個採用的案例')

    def check_user_agreement(self):
        print("\n[使用者同意] 寫「使用者同意／決定」的，同一格有原話（「」）或 inputs/ 檔（提醒，不算紅燈）")
        n = hits = 0
        for f, d in self.docs.items():
            for h2, h3, header, rows in d.tables():
                if h2 != '決定與理由' or header[:2] != ['#', '決定']: continue
                for no, c in rows:
                    for cell in c[1:]:
                        if re.search(r'使用者[^，。；]{0,6}(同意|決定|選)', cell):
                            n += 1
                            if '「' not in cell and 'inputs/' not in cell and '選項' not in cell:
                                hits += 1
                                print(f"    • {f}:{no} {c[0]} 寫了使用者同意或決定，沒有引用原話、選項或 inputs/ 檔（docs/02 第四節）")
        if n and not hits:
            print(f"    ✓ 通過（檢查了 {n} 格）")
        elif not n:
            self.done('使用者同意', 0, '')

    def run(self):
        self.check_parse()
        self.check_residue(); self.check_cancelled(); self.check_ids(); self.check_glossary()
        self.check_proposal(); self.check_markers(); self.check_paths(); self.check_versions()
        self.check_pending()
        self.check_tables(); self.check_placeholders(); self.check_eq_impact(); self.check_out_of_scope()
        self.check_golden(); self.check_late_inputs(); self.check_param_storage(); self.check_chain(); self.check_core_prefix(); self.check_referenced_by()
        self.check_reviews(); self.check_challenge(); self.check_golden_selfcontained(); self.check_user_agreement()
        self.check_used_in(); self.check_stale_frozen()
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
