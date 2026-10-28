"""抽查用的證據：把 AI 自評裡寫的編號（D-01、X-03、Q08、EQ-002、US-D03、P-07）和「檔名:行號」換成實際內容，
人不用自己翻檔案找。只讀不寫。"""
import os
import re

import kit

ID = re.compile(r'(?<![\w-])(US-D\d+|EQ-\d+|[DXP]-\d+|Q\d+)(?![\w-])')
FILE_LINE = re.compile(r'([\w./\-一-鿿]+\.md):(\d+)')
SLICE_FILES = ['01_scope.md', '02_entities.md', '03_flows.md', '03_use_cases.md', '04_rules.md', '05_mapping.md', 'questions.md']


def _tables(path):
    mb = kit.md2build()
    mb.problems.clear()
    out = list(mb.Doc(path).tables())
    mb.problems.clear()
    return out


def _row_by_id(path, rid):
    for h2, h3, header, rows in _tables(path):
        for no, cells in rows:
            if cells and cells[0].strip() == rid:
                return {'title': h3 or h2 or '', 'line': no,
                        'fields': [[h.strip(), c.strip()] for h, c in zip(header, cells)]}
    return None


def _row_at(path, line):
    for h2, h3, header, rows in _tables(path):
        for no, cells in rows:
            if no == line:
                return {'title': h3 or h2 or '', 'fields': [[h.strip(), c.strip()] for h, c in zip(header, cells)]}
    return None


TERM = re.compile(r'「([^」]{1,12})」')


def _sections(path, criterion):
    """完成標準裡用「」括起來的項目（「做」「不做」「切片情境」…）：在交付物裡找同名的清單項目（「- 做：」）或標題，
    把那一段（含底下縮排的子項目）整段拿出來，最多 25 行。AI 自評沒寫出處時，人也看得到這條標準說的內容。"""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    out = []
    for term in dict.fromkeys(TERM.findall(criterion)):
        pat = re.compile(r'^(\s*)(?:[-*]\s+|#{2,4}\s+)' + re.escape(term) + r'(?:（[^）]*）)?\s*(?:[：:]|$)')
        for i, l in enumerate(lines):
            m = pat.match(l)
            if not m:
                continue
            ind, heading = len(m.group(1)), l.lstrip().startswith('#')
            block = [l]
            for nxt in lines[i + 1:]:
                if heading and re.match(r'^#{1,4}\s', nxt):
                    break
                if not heading and nxt.strip() and len(nxt) - len(nxt.lstrip()) <= ind:
                    break
                block.append(nxt)
            block = [b for b in block if not b.strip().startswith('<!--')][:25]
            out.append({'ref': f'「{term}」', 'file': kit.rel(path), 'line': i + 1, 'title': '交付物裡的這一段',
                        'text': '\n'.join(b[ind:] if b.startswith(' ' * ind) else b for b in block).strip()})
            break
    return out


FUNC = set('的與和及或在是有第步了都也不沒這那用把被給到從對')
CJK = re.compile(r'[\u4e00-\u9fff]{2}')


def _headings(path, criterion):
    """完成標準沒有用「」點名時：交付物裡標題和完成標準有共同詞（兩個字、不含虛詞）的段落，例：「範圍」「交給第 ② 步的觀察」「驗收問題」。"""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    out = []
    for i, l in enumerate(lines):
        m = re.match(r'^(#{2,3})\s+(.+?)\s*$', l)
        if not m:
            continue
        title = m.group(2)
        grams = {title[k:k + 2] for k in range(len(title) - 1)}
        if not any(CJK.fullmatch(g) and not (set(g) & FUNC) and g in criterion for g in grams):
            continue
        block = []
        for nxt in lines[i + 1:]:
            if re.match(r'^#{1,%d}\s' % len(m.group(1)), nxt):
                break
            block.append(nxt)
        text = re.sub(r'<!--.*?-->', '', '\n'.join(block), flags=re.S).strip()   # 範本的說明註解不算內容
        if text:
            out.append({'ref': title, 'file': kit.rel(path), 'line': i + 1, 'title': '交付物裡的這一段',
                        'text': '\n'.join(text.split('\n')[:30]), 'body': text})
    return out


ASCII_WORD = re.compile(r'(?<![\w./-])([A-Za-z][A-Za-z0-9_]*(?:[A-Z_][A-Za-z0-9_]*)+|[a-z]+_[a-z0-9_]+)(?![\w./-])')
NOT_ID = {'AI', 'PLAN', 'CHANGELOG', 'ENTITY_SKETCH', 'EQ', 'US', 'P0', 'P1', 'P2', 'PDF', 'Excel', 'GHG', 'ISO', 'LED', 'PR', 'CR'}


def _english(sections):
    """完成標準說「沒有英文識別名稱、表名、欄位名」時：把這幾段裡像識別名稱的英文字（駝峰、底線）列出來，人只要看這份清單。"""
    found = {}
    for sec in sections:
        for k, l in enumerate(sec['body'].split('\n')):
            for w in ASCII_WORD.findall(l):
                if w not in NOT_ID and not re.fullmatch(r'[A-Z]{1,3}\d*', w):
                    found.setdefault(w, f"{sec['ref']}（第 {sec['line'] + 1 + k} 行）")
    return {'ref': '網頁掃過這幾段的英文字', 'file': sections[0]['file'], 'line': sections[0]['line'], 'title': '',
            'text': ('找到這些，看是不是英文識別名稱、表名或欄位名：\n' + '\n'.join(f'- {w}　{where}' for w, where in found.items()))
            if found else '沒有找到駝峰或底線寫法的英文字（像 ElectricityBill、bill_id 這種）。'}


def find(text, file, criterion=''):
    """text：AI 自評；file：這條完成標準所在的交付物（相對路徑）；criterion：完成標準本身（找「」括起來的段落）。
    回傳 [{ref, file, line, title, fields | text}]。"""
    own = kit.resolve(file)
    if not own:
        return []
    sdir = os.path.dirname(own)
    order = [own] + [p for p in (os.path.join(sdir, f) for f in SLICE_FILES) if p != own and os.path.isfile(p)]
    order += [p for p in (os.path.join(kit.repo(), 'slices', f) for f in ('PLAN.md', 'ENTITY_SKETCH.md')) if os.path.isfile(p)]
    out = _sections(own, criterion) if criterion else []
    if criterion and not out:
        out = _headings(own, criterion) or _headings(own, text)   # 標準沒點名段落時，看 AI 自評提到哪一段（例：「驗收問題 15 條」）
        if out and re.search(r'英文|表名|欄位名|識別名稱', criterion):
            # 「沒有…」這種標準：掃描結果最有用，放第一張；整段內容收起來，需要時再看
            for o in out:
                o['more'] = True
            out.insert(0, _english(out))
        for o in out:
            o.pop('body', None)
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
        p = kit.resolve(name, sdir) or kit.resolve(os.path.join('slices', name))
        if not p:
            continue
        n = int(ln)
        hit = _row_at(p, n)
        if not hit:
            with open(p, encoding='utf-8') as f:
                lines = f.read().split('\n')
            hit = {'title': '', 'text': lines[n - 1].strip() if 0 < n <= len(lines) else ''}
        out.append({'ref': key, 'file': kit.rel(p), 'line': n, **hit})
    return out
