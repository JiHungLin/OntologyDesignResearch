"""抽查用的證據：人不用自己翻檔案找，網頁先把「這條完成標準要看的東西」拿出來。只讀不寫。

依序找（都是通用規則，不綁特定 domain 或切片）：
1. 完成標準用「」點名的項目：同名的清單項目或標題整段；是表格欄名的，看那一欄每列有沒有填。
2. 沒點名時：標題和完成標準（再不行就 AI 自評）有共同詞的段落，最多兩段。段落附上幾列、幾項，人不用自己數。
3. 標準說「沒有英文識別名稱、表名、欄位名」：掃過這些段落，列出像識別名稱的英文字。
4. AI 說某個檢查程式通過（lint.py「詞彙對照表」…）：網頁重跑 tools/lint.py，附上那一項的結果。
5. AI 自評裡寫的編號（D-01、X-03、Q08、R65、UC-02、EQ-002、US-D03、P-07、GC01）與「檔名:行號」：換成那一列或那一行。
前五張直接顯示，其餘收進「更多」。
"""
import os
import re
import subprocess
import sys

import kit

ID = re.compile(r'(?<![\w-])(US-D\d+|EQ-\d+|UC-\d+|[DXP]-\d+|GC\d+|Q\d+|R\d+)(?![\w-])')
FILE_LINE = re.compile(r'([\w./\-一-鿿]+\.md):(\d+)')
TERM = re.compile(r'「([^」]{1,12})」')
SLICE_FILES = ['01_scope.md', '02_entities.md', '03_flows.md', '03_use_cases.md', '04_rules.md', '05_mapping.md', 'questions.md']
SHOW = 5
MAX_LINES = 30

# 標題比對時不算數的兩字詞（太常見，什麼標題都對得上）
FUNC = set('的與和及或在是有第步了都也不沒這那用把被給到從對')
GENERIC = {'每個', '都有', '已經', '回頭', '修改', '需要', '檢查', '紀錄', '是否', '以及', '沒有', '可以', '這一', '一步',
           '本切', '切片', '審查', '重點', '處理', '結果', '對應', '標準', '完成', '寫明', '註明', '一條', '每條', '所有'}
CJK2 = re.compile(r'[一-鿿]{2}')


def _read_lines(path):
    with open(path, encoding='utf-8') as f:
        return f.read().split('\n')


def _tables(path):
    mb = kit.md2build()
    mb.problems.clear()
    out = list(mb.Doc(path).tables())
    mb.problems.clear()
    return out


def _fields(header, cells):
    return [[h.strip(), c.strip()] for h, c in zip(header, cells)]


def _row_by_id(path, rid):
    for h2, h3, header, rows in _tables(path):
        for no, cells in rows:
            if cells and cells[0].strip() == rid:
                return {'title': h3 or h2 or '', 'line': no, 'fields': _fields(header, cells)}
    return None


def _row_at(path, line):
    for h2, h3, header, rows in _tables(path):
        for no, cells in rows:
            if no == line:
                return {'title': h3 or h2 or '', 'fields': _fields(header, cells)}
    return None


def _count(text):
    """段落裡有幾列表格、幾個清單項目（最上層）。"""
    rows = [l for l in text.split('\n') if l.lstrip().startswith('|') and not re.match(r'^\s*\|[\s:|-]+\|\s*$', l)]
    items = [l for l in text.split('\n') if re.match(r'^[-*]\s', l)]
    if len(items) <= 1:   # 「- 做：」底下的子項目才是要數的；只有自己一行的不數
        items = [l for l in text.split('\n') if re.match(r'^\s+[-*]\s', l)]
    parts = []
    if len(rows) > 1:
        parts.append(f'表格 {len(rows) - 1} 列')
    if items:
        parts.append(f'{len(items)} 項')
    return '・'.join(parts)


def _section(path, i, lines, level=None, indent=None):
    """從第 i 行（0 起算）開始的一段：標題到下一個同級標題，或清單項目加上它底下縮排的子項目。"""
    block = []
    for nxt in lines[i + 1:]:
        if level is not None and re.match(r'^#{1,%d}\s' % level, nxt):
            break
        if indent is not None and nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
            break
        block.append(nxt)
    head = [] if level is not None else [lines[i]]
    text = re.sub(r'<!--.*?-->', '', '\n'.join(head + block), flags=re.S)   # 範本的說明註解不算內容
    if indent:
        text = '\n'.join(l[indent:] if l.startswith(' ' * indent) else l for l in text.split('\n'))
    return text.strip()


def _card(ref, path, line, text, title='交付物裡的這一段'):
    c = _count(text)
    body = text.split('\n')
    return {'ref': ref, 'file': kit.rel(path), 'line': line, 'title': title + (f'・{c}' if c else ''),
            'text': '\n'.join(body[:MAX_LINES]) + ('\n…（還有 %d 行，打開檔案看）' % (len(body) - MAX_LINES) if len(body) > MAX_LINES else ''),
            'body': text}


def _parent(lines, i):
    """第 i 行上面最近的 ###／#### 標題：(行號, 層級, 標題)。"""
    for k in range(i, -1, -1):
        m = re.match(r'^(#{3,4})\s+(.+?)\s*$', lines[k])
        if m:
            return k, len(m.group(1)), m.group(2)
    return None


def _every(term, path, lines, idxs):
    """同一個項目在好幾張卡裡都有（「每張新卡都有『不是什麼』」）：列出有的卡與同一節裡沒有的卡。"""
    have = {}
    for i in idxs:
        p = _parent(lines, i)
        if p:
            have.setdefault(p[0], p)
    if not have:
        return _card(f'「{term}」', path, idxs[0] + 1, '\n'.join(lines[i] for i in idxs))
    first = min(have)
    level = have[first][1]
    # 同一個 ## 節裡、同層級的卡
    start = next((k for k in range(first, -1, -1) if re.match(r'^##\s', lines[k])), 0)
    end = next((k for k in range(first + 1, len(lines)) if re.match(r'^##\s', lines[k])), len(lines))
    cards = [(k, re.sub(r'^#+\s+', '', lines[k]).strip()) for k in range(start, end) if re.match(r'^#{%d}\s' % level, lines[k])]
    missing = [t for k, t in cards if k not in have]
    text = f'{len(have)} 張卡有：' + '、'.join(t for _, _, t in have.values())
    if missing:
        text += f'\n**{len(missing)} 張沒有：**' + '、'.join(missing)
    elif len(cards) > 1:
        text += '\n同一節裡的卡都有。'
    return {'ref': f'「{term}」', 'file': kit.rel(path), 'line': idxs[0] + 1, 'title': '每張卡有沒有寫', 'text': text}


def _overlap(title, words):
    """標題和 words 有沒有共同詞：兩個中文字（不含虛詞、太常見的詞），或一個 3 個字母以上的英文字。"""
    grams = {title[k:k + 2] for k in range(len(title) - 1)}
    if any(CJK2.fullmatch(g) and not (set(g) & FUNC) and g not in GENERIC and g in words for g in grams):
        return True
    return any(w.lower() in words.lower() for w in re.findall(r'[A-Za-z]{3,}', title))


def _named(path, criterion):
    """「」點名的項目：同名清單項目或標題；不是的話，若是表格欄名，看那一欄有沒有填。"""
    lines = _read_lines(path)
    out = []
    for term in dict.fromkeys(TERM.findall(criterion)):
        pat = re.compile(r'^(\s*)(?:[-*]\s+|(#{2,4})\s+)' + re.escape(term) + r'(?:（[^）]*）)?\s*(?:[：:]|$)')
        found = [(i, m) for i, m in ((i, pat.match(l)) for i, l in enumerate(lines)) if m]
        bullets = [(i, m) for i, m in found if not m.group(2)]   # 卡片裡的清單項目才算「每張卡都要有」，標題不算
        if bullets and (len(bullets) > 1 or ('每' in criterion and _parent(lines, bullets[0][0]))):
            out.append(_every(term, path, lines, [i for i, _ in bullets]))
            continue
            out.append(_every(term, path, lines, [i for i, _ in found]))
            continue
        if found:
            i, m = found[0]
            out.append(_card(f'「{term}」', path, i + 1, _section(path, i, lines, level=len(m.group(2)) if m.group(2) else None,
                                                             indent=None if m.group(2) else len(m.group(1)))))
            continue
        tabs = [(h2, h3, header, rows) for h2, h3, header, rows in _tables(path)
                if term in [h.strip() for h in header] and rows]
        related = [t for t in tabs if _overlap(t[1] or t[0] or '', criterion)]
        for h2, h3, header, rows in (related or tabs)[:3]:
            hs = [h.strip() for h in header]
            k = hs.index(term)
            empty = [no for no, cells in rows if k >= len(cells) or cells[k].strip() in ('', '—', '-')]
            text = (f'{len(rows)} 列都有填。' if not empty else
                    f'{len(rows)} 列中 {len(rows) - len(empty)} 列有填，{len(empty)} 列空白（第 {"、".join(map(str, empty[:10]))} 行）。')
            out.append({'ref': f'「{term}」欄', 'file': kit.rel(path), 'line': rows[0][0], 'title': h3 or h2 or '', 'text': text})
    return out


def _headings(path, words, limit=2):
    """標題和 words 有共同詞的段落，依共同詞多寡取前幾段。"""
    lines = _read_lines(path)
    heads = [(i, m) for i, m in ((i, re.match(r'^(#{2,3})\s+(.+?)\s*$', l)) for i, l in enumerate(lines)) if m]
    freq = {}
    for _, m in heads:
        for g in {m.group(2)[k:k + 2] for k in range(len(m.group(2)) - 1)}:
            freq[g] = freq.get(g, 0) + 1
    common = {g for g, n in freq.items() if n > max(3, len(heads) // 4)}   # 這份檔案裡大多數標題都有的詞（例：規則檔的「規則」）
    scored = []
    for i, m in heads:
        title = m.group(2)
        grams = {title[k:k + 2] for k in range(len(title) - 1)}
        hit = {g for g in grams if CJK2.fullmatch(g) and not (set(g) & FUNC) and g not in GENERIC and g not in common and g in words}
        core = re.sub(r'（[^）]*）|\([^)]*\)|^[一二三四五六七八九十\d.]+[、.\s]*', '', title).strip()
        # 只在中間對上一個詞的長標題（例：「決策表：依規則給予法定特休」對上「規則」）太弱，不算
        # 中文標題的主詞通常在最後（「交給第 ② 步的觀察」「驗收問題」），對上的詞在結尾也算
        if hit and (len(hit) >= 2 or (core and core in words) or any(core.endswith(g) for g in hit)):
            text = _section(path, i, lines, level=len(m.group(1)))
            if text:
                scored.append((len(hit), -i, _card(title, path, i + 1, text)))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [c for _, _, c in scored[:limit]]


ASCII_WORD = re.compile(r'(?<![\w./-])([A-Za-z][A-Za-z0-9_]*(?:[A-Z_][A-Za-z0-9_]*)+|[a-z]+_[a-z0-9_]+)(?![\w./-])')
NOT_ID = {'AI', 'PLAN', 'CHANGELOG', 'ENTITY_SKETCH', 'EQ', 'US', 'PDF', 'Excel', 'GHG', 'ISO', 'LED', 'PR', 'CR', 'API', 'ID', 'UC'}


def _english(sections):
    """「沒有英文識別名稱、表名、欄位名」：把這幾段裡像識別名稱的英文字（駝峰、底線）列出來，人只要看這份清單。"""
    found = {}
    for sec in sections:
        for k, l in enumerate(sec['body'].split('\n')):
            for w in ASCII_WORD.findall(l):
                if w not in NOT_ID and not re.fullmatch(r'[A-Z]{1,3}\d*', w):
                    found.setdefault(w, f"{sec['ref']}（第 {sec['line'] + 1 + k} 行附近）")
    return {'ref': '網頁掃過這幾段的英文字', 'file': sections[0]['file'], 'line': sections[0]['line'], 'title': '',
            'text': ('找到這些，看是不是英文識別名稱、表名或欄位名：\n' + '\n'.join(f'- {w}　{where}' for w, where in found.items()))
            if found else '沒有找到駝峰或底線寫法的英文字（像 ElectricityBill、bill_id 這種）。'}


_lint_cache = {}


def _lint(slice_):
    """重跑 tools/lint.py <切片>（唯讀），切成 {檢查名稱: 結果文字}。依切片資料夾的修改時間快取。"""
    sdir = os.path.join(kit.repo(), 'slices', slice_)
    tool = os.path.join(kit.repo(), 'tools', 'lint.py')
    if not os.path.isfile(tool) or not os.path.isdir(sdir):
        return {}
    stamp = max((os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(sdir) for f in fs), default=0)
    if _lint_cache.get(slice_, (None,))[0] == stamp:
        return _lint_cache[slice_][1]
    try:
        r = subprocess.run([sys.executable, tool, slice_], cwd=kit.repo(), capture_output=True, text=True, timeout=60)
        out = r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return {}
    sections, cur = {}, None
    for l in out.split('\n'):
        m = re.match(r'^\[([^\]]+)\]', l)
        if m:
            cur = m.group(1)
            sections[cur] = [l]
        elif cur and l.strip():
            sections[cur].append(l.strip())
    res = {k: '\n'.join(v[:12]) + ('\n…' if len(v) > 12 else '') for k, v in sections.items()}
    _lint_cache[slice_] = (stamp, res)
    return res


def _lint_cards(own, text):
    """AI 說 lint.py 的某一項通過（寫成 lint.py「詞彙對照表」）：附上網頁重跑那一項的結果。"""
    if 'lint' not in text:
        return []
    parts = kit.rel(own).split(os.sep)
    if len(parts) < 3 or parts[0] != 'slices':
        return []
    res = _lint(parts[1])
    names = [n for n in res if f'「{n}」' in text]
    return [{'ref': f'網頁重跑 lint.py「{n}」', 'file': kit.rel(own), 'line': 1, 'title': '', 'text': res[n]} for n in names]


def find(text, file, criterion=''):
    """text：AI 自評；file：這條完成標準所在的交付物（相對路徑）；criterion：完成標準本身。
    回傳 [{ref, file, line, title, fields | text, more?}]。"""
    own = kit.resolve(file)
    if not own:
        return []
    sdir = os.path.dirname(own)
    out = _named(own, criterion) if criterion else []
    if criterion and not out:
        out = _headings(own, criterion) or _headings(own, text)   # 標準沒點名段落時，看 AI 自評提到哪一段（例：「驗收問題 15 條」）
        for o in out:
            o['fallback'], o['size'] = True, len(o.get('body', '').split('\n'))
    if out and re.search(r'英文|表名|欄位名|識別名稱', criterion):
        # 「沒有…」這種標準：掃描結果最有用，放第一張；整段內容收起來，需要時再看
        for o in out:
            o['more'] = True
        out.insert(0, _english([o for o in out if 'body' in o] or out))
    out = _lint_cards(own, text) + out
    for o in out:
        o.pop('body', None)

    order = [own] + [p for p in (os.path.join(sdir, f) for f in SLICE_FILES) if p != own and os.path.isfile(p)]
    order += [p for p in (os.path.join(kit.repo(), 'slices', f) for f in ('PLAN.md', 'ENTITY_SKETCH.md')) if os.path.isfile(p)]
    seen = set()
    for rid in ID.findall(text):
        if rid in seen:
            continue
        seen.add(rid)
        for p in order:
            hit = _row_by_id(p, rid)
            if hit:
                out.append({'ref': rid, 'file': kit.rel(p), **hit})
                break
    for name, ln in FILE_LINE.findall(text):
        key = f'{name}:{ln}'
        if key in seen:
            continue
        seen.add(key)
        p = kit.resolve(name, sdir)
        if not p:
            continue
        n = int(ln)
        hit = _row_at(p, n)
        if not hit:
            lines = _read_lines(p)
            hit = {'title': '', 'text': lines[n - 1].strip() if 0 < n <= len(lines) else ''}
        out.append({'ref': key, 'file': kit.rel(p), 'line': n, **hit})
    if any(o['ref'] == rid for rid in seen for o in out):
        for o in out:
            if o.get('fallback') and o.get('size', 0) > 40:
                o['more'] = True
    for o in out:
        o.pop('fallback', None)
        o.pop('size', None)
    shown = 0
    for o in out:
        if not o.get('more'):
            shown += 1
            if shown > SHOW:
                o['more'] = True
    return out


def context(where, review_path):
    """確認列「在哪裡」指到的內容：表格列附欄名，標題附那一段，清單項目附它底下的子項目。
    人不用打開檔案、在一長列 Markdown 表格裡找那一格。"""
    sdir = os.path.dirname(os.path.dirname(review_path))   # reviews/ 的上一層是切片資料夾
    out, seen = [], set()
    for name, ln in FILE_LINE.findall(where or ''):
        p = kit.resolve(name, sdir)
        if not p:
            continue
        n = int(ln)
        hit = _row_at(p, n)
        if hit:
            key = (p, tuple(map(tuple, hit['fields'])))
        else:
            lines = _read_lines(p)
            if not 0 < n <= len(lines):
                continue
            i, line = n - 1, lines[n - 1]
            m = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
            par = _parent(lines, i - 1) if not m else None
            if m:
                text, title = _section(p, i, lines, level=len(m.group(1))), m.group(2)
            elif re.match(r'^\s*[-*]\s', line):
                text, title = _section(p, i, lines, indent=len(line) - len(line.lstrip())), par[2] if par else ''
            else:
                text, title = line.strip(), par[2] if par else ''
            body = text.split('\n')
            hit = {'title': title, 'text': '\n'.join(body[:MAX_LINES]) + ('\n…（還有 %d 行，打開檔案看）' % (len(body) - MAX_LINES) if len(body) > MAX_LINES else '')}
            key = (p, n)
        if key in seen or ('text' in hit and any(o['file'] == kit.rel(p) and hit['text'] in o.get('text', '') for o in out)):
            continue   # 同一列，或已經在前面那一段裡
        seen.add(key)
        out.append({'file': kit.rel(p), 'line': n, **hit})
    return out
