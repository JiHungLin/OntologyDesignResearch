"""共用核心（core/）的閱讀頁：把 entities、relations、flows、rules、glossary 讀成結構，給網頁分頁顯示。
不另存資料：格式是 docs/02 第六節（各切片 ②③④ 的格式，加上狀態標記與出處、層、被引用）。"""
import os
import re

import flows
import kit

CARD = re.compile(r'^### ([A-Za-z][A-Za-z0-9]*)（([^）]+)）\s*(\[[^\]]+\])?')
FIELD = re.compile(r'^- ([^：]+)：\s*(.*)$')
ATTR = re.compile(r'^\s+- `([A-Za-z_]\w*)`(.*)$')
REL_LABEL = re.compile(r'^([A-Za-z][A-Za-z0-9]*)（([^）]+)）')


def _status(s):
    m = re.search(r'\[(候選|已驗證[^\]]*|已取代[^\]]*|已停用[^\]]*)\]', s or '')
    return m.group(1) if m else ''


def _entities(path):
    out, cur = [], None
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for no, line in enumerate(lines, 1):
        m = CARD.match(line)
        if m:
            cur = {'id': m.group(1), 'label': m.group(2), 'status': _status(m.group(3)), 'line': no,
                   'fields': [], 'attrs': []}
            out.append(cur)
            continue
        if line.startswith('#'):
            cur = None
            continue
        if not cur:
            continue
        m = FIELD.match(line)
        if m:
            k, v = m.groups()
            if k != '主要屬性':
                cur['fields'].append([k, v])
            continue
        m = ATTR.match(line)
        if m:
            cur['attrs'].append({'name': m.group(1), 'text': re.sub(r'^（(.*)）$', r'\1', m.group(2).strip())})
    return out


def _tables(path):
    mb = kit.md2build()
    mb.problems.clear()
    out = [{'h2': h2 or '', 'h3': h3 or '', 'header': [h.strip() for h in header],
            'rows': [{'line': no, 'cells': c} for no, c in rows]} for h2, h3, header, rows in mb.Doc(path).tables()]
    mb.problems.clear()
    return out


def _relations(tables):
    rels = []
    for t in tables:
        if t['header'][:3] != ['從', '關係', '到']:
            continue
        for r in t['rows']:
            c = dict(zip(t['header'], r['cells']))
            lab = REL_LABEL.match(c['關係'].strip())
            rels.append({'line': r['line'], 'from': c['從'].strip(), 'to': c['到'].strip(),
                         'name': lab.group(1) if lab else c['關係'], 'label': lab.group(2) if lab else '',
                         'card': c.get('幾對幾', '').strip(), 'period': c.get('有無期間', '').strip(),
                         'why': c.get('為什麼', ''), 'status': _status(c.get('狀態', '')),
                         'source': c.get('出處', ''), 'used_by': c.get('被引用', '')})
    return rels


def load():
    root = os.path.join(kit.repo(), 'core')
    if not os.path.isdir(root):
        return None
    p = lambda name: os.path.join(root, name)
    ok = lambda name: os.path.isfile(p(name))
    out = {'path': 'core', 'entities': [], 'relations': [], 'glossary': [], 'rules': [], 'flows': None,
           'flow_tables': [], 'changelog': ''}
    if ok('entities.md'):
        out['entities'] = _entities(p('entities.md'))
    if ok('relations.md'):
        out['relations'] = _relations(_tables(p('relations.md')))
    if ok('glossary.md'):
        out['glossary'] = _tables(p('glossary.md'))
    if ok('rules.md'):
        out['rules'] = _tables(p('rules.md'))
    if ok('flows.md'):
        out['flows'] = flows.load_path(p('flows.md'))
        out['flow_tables'] = [t for t in _tables(p('flows.md')) if not t['h3']]   # 事件表、更正方式；狀態機表在 flows 裡
    if ok('CHANGELOG.md'):
        with open(p('CHANGELOG.md'), encoding='utf-8') as f:
            out['changelog'] = f.read()
    return out
