#!/usr/bin/env python3
"""凍結時把切片 ②③④ 的內容同步進 core/（docs/02 第六節）。
用法：python3 tools/sync_core.py <切片代號> --steps 2,3,4 [--write] [--tags 2=<tag>,3=<tag>] [--root <repo 根目錄>]
  預設只列出差異，不寫檔；看過差異、確認後加 --write 寫入。
  --tags：這次凍結要打的 tag（預設取各步驟最新的 git tag 加一版）。
比對的是解析後的內容：表格逐列依編號（或名稱）對應，卡片與狀態機的內容逐行比對、不管順序，
空白不同、列的順序不同都不算改變；只有內容真的改變的項目才更新，並把「出處」改成新的 tag。
切片的 Q、UC、US-D 編號寫進 core/ 時加上切片前綴（<切片>:Q01）。
不刪除 core/ 的項目：切片裡已經沒有的、出處是別的切片的，只列出來，由人決定。
同步的範圍：② 新增的 Entity 卡、關係、詞彙對照表新增，引用的 Entity 的「被引用」；
③ 狀態機、事件、更正方式、詞彙對照表新增；④ 規則、守恆式、分類值、詞彙對照表新增。
其他章節（例：③ 的推導的狀態、決策流程，④ 的參數、決策表）不同步，會列出來。"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2build as mb

STEP_MARK = {2: '②', 3: '③', 4: '④'}
STATUS_RE = re.compile(r'\s*\[(?:候選|已驗證|已驗證（暫代）|已取代: [^\]]+|已停用: [^\]]+)\]')
MANAGED_COLS = ('狀態', '出處', '被引用', '連鎖')
MANAGED_LINE = re.compile(r'^- (出處|層|被引用)[：:]')
PREFIX_RE = r'(?<![\w:-])(Q\d{2,}|UC-\d+|US-D\d+)(?![\w-])'

# (步驟, 切片檔, 切片的 ## 章節, 種類, core 檔, core 的 ## 章節（{s} 換成切片代號；None＝整份檔的表格或卡片）)
SPEC = [
    (2, '02_entities.md', '新增', 'card', 'entities.md', None),
    (2, '02_entities.md', '關係', 'row', 'relations.md', None),
    (2, '02_entities.md', '詞彙對照表新增', 'row', 'glossary.md', None),
    (3, '03_flows.md', '狀態機', 'card', 'flows.md', '狀態機（{s}）'),
    (3, '03_flows.md', '事件', 'row', 'flows.md', '事件（{s}）'),
    (3, '03_flows.md', '更正方式', 'row', 'flows.md', '更正方式（{s}）'),
    (3, '03_flows.md', '詞彙對照表新增', 'row', 'glossary.md', None),
    (4, '04_rules.md', '規則', 'row', 'rules.md', '規則'),
    (4, '04_rules.md', '守恆式', 'row', 'rules.md', '守恆式'),
    (4, '04_rules.md', '分類值', 'row', 'rules.md', '分類值'),
    (4, '04_rules.md', '詞彙對照表新增', 'row', 'glossary.md', None),
]
SYNCED_H2 = {f: {sec for _, ff, sec, *_ in SPEC if ff == f} for f in {x[1] for x in SPEC}}
SKIP_H2 = {'引用', '不是 Entity', '變更提案', '決定與理由', '檢查紀錄', '回填紀錄', '參數'}
# 每種表格的第一欄（判斷是不是這種表）與對應的鍵
FIRST_COL = {'關係': '從', '詞彙對照表新增': 'ID', '事件': '事件', '更正方式': '對象', '規則': '編號', '守恆式': '編號', '分類值': '代碼'}
EXTRA_COLS = {'relations.md': ['狀態', '出處', '被引用'], 'flows.md:事件': ['狀態', '出處', '被引用'], 'default': ['狀態', '出處']}

def norm(text):
    return re.sub(r'\s+', ' ', (text or '').replace('　', ' ')).strip()

def key_cell(cell):
    m = re.match(r'\s*`?([^\s`（(|]+)', cell or '')
    return m.group(1) if m else ''

def row_key(sec, header, cells):
    get = lambda name: cells[header.index(name)] if name in header else ''
    if sec == '關係':
        return (key_cell(get('從')), key_cell(get('關係')), key_cell(get('到')))
    if sec == '更正方式':
        return (key_cell(get('對象')), key_cell(get('更正事件')))
    return key_cell(cells[0])

def card_key(heading):
    return key_cell(re.sub(r'^#+\s*', '', heading))

class File:
    """以行為單位讀寫一份 Markdown，略過 HTML 註解中的內容。"""
    def __init__(self, path):
        self.path = path
        self.lines = open(path, encoding='utf-8').read().split('\n') if os.path.exists(path) else []

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.lines))

    def comment_mask(self):
        mask, inside = [], False
        for l in self.lines:
            starts = '<!--' in l
            mask.append(inside or starts)
            if starts and '-->' not in l.split('<!--', 1)[1]: inside = True
            elif inside and '-->' in l: inside = False
        return mask

    def h2_range(self, title):
        """## title 的範圍 (開始行, 結束行)；title 為 None 時是整份檔。找不到回傳 None。"""
        if title is None:
            return (0, len(self.lines))
        mask = self.comment_mask()
        for i, l in enumerate(self.lines):
            if not mask[i] and re.match(r'^##\s+' + re.escape(title) + r'\s*$', l):
                j = i + 1
                while j < len(self.lines) and not (self.lines[j].startswith('## ') and not mask[j]):
                    j += 1
                return (i, j)
        return None

    def tables(self, start, end):
        """範圍內的表格：[(表頭行, 表頭, [(行, 儲存格)])]。"""
        mask, out, i = self.comment_mask(), [], start
        while i < end - 1:
            l, nxt = self.lines[i], self.lines[i + 1]
            if not mask[i] and l.strip().startswith('|') and re.match(r'^\s*\|[\s:|-]+\|\s*$', nxt) and '-' in nxt:
                header, rows, j = mb.split_row(l), [], i + 2
                while j < end and self.lines[j].strip().startswith('|'):
                    rows.append((j, mb.split_row(self.lines[j]))); j += 1
                out.append((i, header, rows)); i = j
            else:
                i += 1
        return out

    def cards(self, start, end):
        """範圍內的 ### 卡片：[(開始行, 結束行, 標題行)]。"""
        mask, heads = self.comment_mask(), []
        for i in range(start, end):
            if not mask[i] and self.lines[i].startswith('### '): heads.append(i)
        return [(h, heads[k + 1] if k + 1 < len(heads) else end, self.lines[h]) for k, h in enumerate(heads)]

def fmt_row(cells):
    return '| ' + ' | '.join(c.replace('|', '\\|') for c in cells) + ' |'

class Sync:
    def __init__(self, root, slice_name, steps, tags):
        self.root, self.slice, self.steps = root, slice_name, steps
        self.dir = os.path.join(root, 'slices', slice_name)
        self.tags = tags
        self.files = {}
        self.report = []           # (類別, 文字)
        self.changed = set()

    # ---------- 共用 ----------
    def core(self, name):
        if name not in self.files:
            self.files[name] = File(os.path.join(self.root, 'core', name))
        return self.files[name]

    def prefix(self, text):
        return re.sub(PREFIX_RE, lambda m: f'{self.slice}:{m.group(1)}', text)

    def source(self, step):
        return f'{self.slice}（{STEP_MARK[step]} @ {self.tags[step]}）'

    def mine(self, src):
        return src.strip().startswith(self.slice + '（') or src.strip().startswith(self.slice + '(')

    def new_source(self, old, step):
        """把出處中本切片那一段換成新的 tag，後面的說明保留。"""
        pat = re.compile(re.escape(self.slice) + r'（[^）]*）')
        return pat.sub(self.source(step), old, count=1) if pat.search(old) else self.source(step)

    def say(self, kind, text):
        self.report.append((kind, text))

    def layer(self, name):
        path = os.path.join(self.root, 'slices', 'ENTITY_SKETCH.md')
        if os.path.exists(path):
            f = File(path)
            for _, header, rows in f.tables(0, len(f.lines)):
                if header[:1] == ['名詞'] and '層' in header:
                    for _, c in rows:
                        if key_cell(c[0]) == name: return c[header.index('層')]
        self.say('提醒', f'{name} 不在全局名詞草圖，「層」先寫 domain，請確認')
        return 'domain'

    # ---------- 表格 ----------
    def sync_rows(self, step, sfile, sec, cname, csec):
        f, label = File(os.path.join(self.dir, sfile)), f'{sfile}「{sec}」'
        rng = f.h2_range(sec)
        if not rng: return
        want = []
        for hi, header, rows in f.tables(*rng):
            if header[0] != FIRST_COL[sec]:
                self.say('未同步', f'{sfile}:{hi + 1} 「{sec}」裡表頭為「{header[0]}…」的表格（core/ 沒有對應的位置）')
                continue
            want += [(header, c, no) for no, c in rows if any(x.strip() for x in c)]
        if not want: return
        cf = self.core(cname)
        target = csec.format(s=self.slice) if csec else None
        crng = cf.h2_range(target)
        ctables = [t for t in (cf.tables(*crng) if crng else []) if t[1][0] == FIRST_COL[sec]]
        if crng is None or not ctables:
            # core 還沒有這張表：建一張（表頭沿用 core 中同種表格，沒有就用切片的表頭加管理欄）
            same = [t for t in cf.tables(0, len(cf.lines)) if t[1][0] == FIRST_COL[sec]]
            extra = EXTRA_COLS.get(cname) or EXTRA_COLS.get(f'{cname}:{sec}') or EXTRA_COLS['default']
            header = same[0][1] if same else want[0][0] + extra
            block = ['', fmt_row(header), '|' + '---|' * len(header)]
            if crng is None:
                cf.lines += ['', f'## {target}'] + block
            else:
                cf.lines[crng[1]:crng[1]] = block + ['']
            self.changed.add(cname)
            crng = cf.h2_range(target)
            ctables = [t for t in cf.tables(*crng) if t[1][0] == FIRST_COL[sec]]
        # core 中現有的列（這個章節的所有同種表格）
        existing = {}
        for hi, header, rows in ctables:
            for no, c in rows:
                existing[row_key(sec, header, c)] = (no, header, c)
        seen, added, updated, same_n = set(), [], [], 0
        for sh, sc, sno in want:
            key = row_key(sec, sh, sc)
            seen.add(key)
            kname = '／'.join(key) if isinstance(key, tuple) else key
            if key in existing:
                no, ch, cc = existing[key]
                if '出處' in ch and not self.mine(cc[ch.index('出處')]):
                    self.say('衝突', f'core/{cname}:{no + 1} {kname} 的出處是「{cc[ch.index("出處")]}」，不是本切片；沒有改（{sfile}:{sno + 1}）')
                    continue
                diff, new = [], list(cc)
                for k, name in enumerate(ch):
                    if name in MANAGED_COLS: continue
                    if name not in sh:
                        continue
                    val = self.prefix(sc[sh.index(name)])
                    if norm(val) != norm(cc[k]):
                        diff.append(name); new[k] = val
                if diff:
                    if '出處' in ch:
                        new[ch.index('出處')] = self.new_source(cc[ch.index('出處')], step)
                    cf.lines[no] = fmt_row(new)
                    updated.append(f'{kname}（{"、".join(diff)}）')
                else:
                    same_n += 1
            else:
                ch = ctables[-1][1]
                cells = []
                for name in ch:
                    if name == '狀態': cells.append('[候選]')
                    elif name == '出處': cells.append(self.source(step))
                    elif name in MANAGED_COLS: cells.append('')
                    else: cells.append(self.prefix(sc[sh.index(name)]) if name in sh else '')
                missing = [n for n in sh if n not in ch]
                if missing:
                    self.say('提醒', f'{label} 的欄位 {"、".join(missing)} 在 core/{cname} 沒有對應的欄，沒有寫入')
                last = max(r[0] for t in ctables for r in t[2]) if any(t[2] for t in ctables) else ctables[-1][0] + 1
                cf.lines.insert(last + 1, fmt_row(cells))
                ctables = [t for t in cf.tables(*cf.h2_range(target)) if t[1][0] == FIRST_COL[sec]]
                added.append(kname)
        if added or updated: self.changed.add(cname)
        gone = []
        for key, (no, ch, cc) in existing.items():
            if key in seen or '出處' not in ch: continue
            src = cc[ch.index('出處')]
            if self.mine(src) and STEP_MARK[step] in src:
                gone.append('／'.join(key) if isinstance(key, tuple) else key)
        self.summary(f'core/{cname}' + (f'「{target}」' if target else '') + f' ← {label}', added, updated, same_n, gone)

    # ---------- 卡片 ----------
    def body(self, lines):
        return sorted(norm(l) for l in lines if l.strip() and not MANAGED_LINE.match(l.strip()))

    def sync_cards(self, step, sfile, sec, cname, csec):
        f = File(os.path.join(self.dir, sfile))
        rng = f.h2_range(sec)
        if not rng: return
        cards = f.cards(*rng)
        if not cards: return
        cf = self.core(cname)
        target = csec.format(s=self.slice) if csec else None
        intro = [self.prefix(l) for l in f.lines[rng[0] + 1:cards[0][0]] if l.strip() and not l.strip().startswith('<!--')]
        crng0 = cf.h2_range(target) if target else None
        if intro and crng0:
            ccards = cf.cards(*crng0)
            cintro = cf.lines[crng0[0] + 1:ccards[0][0] if ccards else crng0[1]]
            cintro = [l for l in cintro if l.strip() and not l.strip().startswith('<!--')]
            if self.body(intro) != self.body(cintro):
                self.say('未同步', f'{sfile}「{sec}」開頭的說明文字和 core/{cname}「{target}」不同；要不要跟著改請人工比對')
        if target and cf.h2_range(target) is None:
            cf.lines += ['', f'## {target}']
            self.changed.add(cname)
        crng = cf.h2_range(target)
        existing = {card_key(h): (a, b, h) for a, b, h in cf.cards(*crng)}
        everywhere = {card_key(h): (a, b, h) for a, b, h in cf.cards(0, len(cf.lines))}
        seen, added, updated, same_n = set(), [], [], 0
        edits = []                                     # (開始, 結束, 新的行)：最後由下往上套用
        for a, b, h in cards:
            key = card_key(h)
            if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', key):
                self.say('未同步', f'{sfile}:{a + 1}「{h[4:].strip()}」（不是以英文識別名稱開頭的項目）')
                continue
            seen.add(key)
            lines = [self.prefix(l) for l in f.lines[a + 1:b]]
            while lines and not lines[-1].strip(): lines.pop()
            head = self.prefix(h)
            hit = existing.get(key) or (everywhere.get(key) if target is None else None)
            if hit:
                ca, cb, chd = hit
                old = cf.lines[ca + 1:cb]
                src = next((l for l in old if re.match(r'^- 出處[：:]', l.strip())), '')
                if src and not self.mine(src.split('：', 1)[-1]):
                    self.say('衝突', f'core/{cname}:{ca + 1} {key} 的出處是別的切片；沒有改（{sfile}:{a + 1}）')
                    continue
                if re.sub(r'\s+', '', STATUS_RE.sub('', chd)) == re.sub(r'\s+', '', STATUS_RE.sub('', head)) \
                        and self.body(old) == self.body(lines):
                    same_n += 1; continue
                marks = ''.join(STATUS_RE.findall(chd)) or ' [候選]'
                first = [l for l in old if MANAGED_LINE.match(l.strip())]
                pos = {l: k for k, l in enumerate(old)}
                body_start = next((k for k, l in enumerate(old) if l.strip() and not MANAGED_LINE.match(l.strip())), len(old))
                before = [l if not l.strip().startswith('- 出處') else '- 出處：' + self.new_source(l.split('：', 1)[-1], step)
                          for l in first if pos[l] < body_start]
                after = [l for l in first if pos[l] >= body_start]
                if not any(l.strip().startswith('- 出處') for l in before + after):
                    before.insert(0, f'- 出處：{self.source(step)}')
                trailing = []
                k = len(old)
                while k > 0 and not old[k - 1].strip(): k -= 1; trailing.append('')
                edits.append((ca, cb, [self.insert_mark(STATUS_RE.sub('', head), marks)] + before + lines + after + trailing))
                old_set, new_set = set(self.body(old)), set(self.body(lines))
                updated.append(f'{key}（增 {len(new_set - old_set)} 行、減 {len(old_set - new_set)} 行）')
            else:
                new = [self.insert_mark(head, ' [候選]'), f'- 出處：{self.source(step)}']
                if cname == 'entities.md':
                    new += [f'- 層：{self.layer(key)}'] + lines + ['- 被引用：']
                else:
                    new += ['- 層：domain', '- 被引用：（無）'] + lines
                edits.append((crng[1], crng[1], new + ['']))
                added.append(key)
        for a, b, new in sorted(edits, key=lambda e: -e[0]):
            if a == b and a > 0 and cf.lines[a - 1].strip():
                new = [''] + new
            cf.lines[a:b] = new
        if added or updated: self.changed.add(cname)
        gone = []
        for key, (a, b, h) in existing.items():
            src = next((l for l in cf.lines[a + 1:b] if l.strip().startswith('- 出處')), '') if key not in seen else ''
            if src and self.mine(src.split('：', 1)[-1]) and STEP_MARK[step] in src and key not in seen:
                gone.append(key)
        self.summary(f'core/{cname}' + (f'「{target}」' if target else '') + f' ← {sfile}「{sec}」', added, updated, same_n, gone)

    @staticmethod
    def insert_mark(heading, marks):
        """狀態標記放在「名稱（中文）」後面。"""
        m = re.match(r'^(###\s+[^（(\s]+(?:（[^）]*）|\([^)]*\))?)(.*)$', heading)
        return (m.group(1) + marks + m.group(2)) if m else heading + marks

    # ---------- 被引用 ----------
    def sync_referenced(self):
        path = os.path.join(self.dir, '02_entities.md')
        if not os.path.exists(path): return
        saved = list(mb.problems)
        refs = mb.parse_refs(mb.Doc(path))
        mb.problems[:] = saved
        cf = self.core('entities.md')
        done = []
        for name in refs:
            for a, b, h in cf.cards(0, len(cf.lines)):
                if card_key(h) != name: continue
                block = cf.lines[a + 1:b]
                src = next((l for l in block if l.strip().startswith('- 出處')), '')
                if self.mine(src.split('：', 1)[-1]): break
                k = next((i for i, l in enumerate(block) if re.match(r'^- 被引用[：:]', l.strip())), None)
                if k is None:
                    end = len(block)
                    while end > 0 and not block[end - 1].strip(): end -= 1
                    cf.lines.insert(a + 1 + end, f'- 被引用：{self.slice}')
                    done.append(name)
                else:
                    val = re.split(r'[：:]', block[k], 1)[1].strip()
                    names = [x.strip() for x in re.split(r'[、,，]', val) if x.strip() and x.strip() not in ('（無）', '無', '—')]
                    if not any(n.startswith(self.slice) for n in names):
                        cf.lines[a + 1 + k] = '- 被引用：' + '、'.join(names + [self.slice])
                        done.append(name)
                break
        if done:
            self.changed.add('entities.md')
            self.say('被引用', f'core/entities.md 的 {"、".join(done)} 加上被引用：{self.slice}')

    # ---------- 回報 ----------
    def summary(self, where, added, updated, same_n, gone):
        if not (added or updated or gone):
            self.say('沒變', f'{where}：{same_n} 項都沒變'); return
        parts = []
        if added: parts.append(f'新增 {len(added)}：{"、".join(added)}')
        if updated: parts.append(f'更新 {len(updated)}（出處改成新 tag）：{"、".join(updated)}')
        if same_n: parts.append(f'沒變 {same_n}')
        self.say('差異', f'{where}：' + '；'.join(parts))
        if gone:
            self.say('切片已沒有', f'{where}：{"、".join(gone)}（不刪除；改名或拆合的，請人決定標 [已取代: …] 或 [已停用: …]）')

    def run(self):
        for step, sfile, sec, kind, cname, csec in SPEC:
            if step not in self.steps or not os.path.exists(os.path.join(self.dir, sfile)): continue
            (self.sync_cards if kind == 'card' else self.sync_rows)(step, sfile, sec, cname, csec)
        if 2 in self.steps: self.sync_referenced()
        for step in self.steps:
            sfile = {2: '02_entities.md', 3: '03_flows.md', 4: '04_rules.md'}[step]
            f = File(os.path.join(self.dir, sfile))
            mask = f.comment_mask()
            for i, l in enumerate(f.lines):
                m = re.match(r'^##\s+(.+?)\s*$', l)
                if m and not mask[i] and m.group(1) not in SYNCED_H2[sfile] and m.group(1) not in SKIP_H2 \
                        and not m.group(1).startswith(('詞彙對照表', '六問')):
                    self.say('未同步', f'{sfile}:{i + 1}「{m.group(1)}」（不在同步範圍；core/ 要不要放請人決定）')
        return self.report

def next_tags(root, slice_name, steps, given):
    tags = dict(given)
    for step in steps:
        if step in tags: continue
        try:
            out = subprocess.run(['git', '-C', root, 'tag', '--list', f'{slice_name}/0{step}-v*'],
                                 capture_output=True, text=True).stdout.split()
        except FileNotFoundError:
            out = []
        vers = [int(t.rsplit('-v', 1)[1]) for t in out if re.search(r'-v\d+$', t)]
        tags[step] = f'{slice_name}/0{step}-v{max(vers, default=0) + 1}'
    return tags

def main():
    args = sys.argv[1:]
    if not args or '--help' in args:
        print(__doc__); return 0
    root, steps, given, write = '.', [2, 3, 4], {}, '--write' in args
    args = [a for a in args if a != '--write']
    for opt in ('--root', '--steps', '--tags'):
        if opt in args:
            i = args.index(opt); val = args[i + 1]; del args[i:i + 2]
            if opt == '--root': root = val
            elif opt == '--steps': steps = [int(x) for x in re.split(r'[,，、]', val) if x.strip()]
            else: given = {int(k): v for k, v in (x.split('=', 1) for x in val.split(','))}
    if any(s not in STEP_MARK for s in steps):
        print('--steps 只能是 2、3、4'); return 1
    if not os.path.isdir(os.path.join(root, 'slices', args[0])):
        print(f'找不到 slices/{args[0]}/'); return 1
    if not os.path.isdir(os.path.join(root, 'core')):
        print('找不到 core/'); return 1
    tags = next_tags(root, args[0], steps, given)
    s = Sync(root, args[0], steps, tags)
    report = s.run()
    print(f"同步 {args[0]} 的 {'、'.join(STEP_MARK[x] for x in steps)} 進 core/（出處：{'、'.join(tags[x] for x in steps)}）")
    order = ['差異', '被引用', '切片已沒有', '衝突', '未同步', '提醒', '沒變']
    for kind in order:
        items = [t for k, t in report if k == kind]
        if items:
            print(f'\n[{kind}]')
            for t in items: print(f'  • {t}')
    if write and s.changed:
        for name in sorted(s.changed): s.files[name].save()
        print(f"\n已寫入：{'、'.join('core/' + n for n in sorted(s.changed))}。接著執行 lint.py <切片> --freeze，並在 core/CHANGELOG.md 記一筆。")
    elif s.changed:
        print('\n（只列出差異，沒有寫檔；確認後加 --write）')
    else:
        print('\ncore/ 不用改。')
    return 0

if __name__ == '__main__':
    sys.exit(main())
