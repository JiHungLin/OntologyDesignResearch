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


def find(text, file):
    """text：AI 自評；file：這條完成標準所在的交付物（相對路徑）。回傳 [{ref, file, line, title, fields | text}]。"""
    own = kit.resolve(file)
    if not own:
        return []
    sdir = os.path.dirname(own)
    order = [own] + [p for p in (os.path.join(sdir, f) for f in SLICE_FILES) if p != own and os.path.isfile(p)]
    order += [p for p in (os.path.join(kit.repo(), 'slices', f) for f in ('PLAN.md', 'ENTITY_SKETCH.md')) if os.path.isfile(p)]
    out, seen = [], set()
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
