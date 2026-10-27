"""第 ② 步的模型圖：從 slices/<切片>/02_entities.md 讀出 Entity 卡、引用與關係，給「看圖確認」用。
不另存資料：卡片、關係表都是 docs/02 第 ② 步的格式；這輪改到哪些，看審查頁確認列指到的行號。"""
import os
import re

import kit

H3_CARD = re.compile(r'^### ([A-Z][A-Za-z0-9]*)（([^）]+)）\s*$')
FIELD = re.compile(r'^- ([^：]+)：\s*(.*)$')
ATTR = re.compile(r'^\s+- `([a-z_][a-z0-9_]*)`(?:、`[a-z_0-9]+`)*（([^；）]*)')
NAME = re.compile(r'^([A-Za-z][A-Za-z0-9]*)')
REL_LABEL = re.compile(r'^([A-Za-z][A-Za-z0-9]*)（([^）]+)）')
MARK = re.compile(r'〔[^〕]*〕')
TAG = re.compile(r'\[(?:解讀|待專家確認|未核對|靜態替代|推導)[^\]]*\]|`')


def _plain(s, limit=None):
    """給畫面看的白話：拿掉〔日期〕、[標記]、括號裡的出處。"""
    s = MARK.sub('', s)
    s = TAG.sub('', s)
    s = re.sub(r'（[^（）]*(?:D-\d+|X-\d+|Q\d+|EQ-\d+|\.md|#\d+)[^（）]*）', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if limit:
        first = re.split(r'(?<=。)', s, maxsplit=1)[0]
        s = first if len(first) <= limit else first[:limit] + '…'
    return s


def load(slice_name):
    path = os.path.join(kit.repo(), 'slices', slice_name, '02_entities.md')
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')

    entities, cur, h2 = [], None, None
    for no, line in enumerate(lines, 1):
        if line.startswith('## '):
            h2 = line[3:].strip()
            if cur:
                cur['end'] = no - 1
            cur = None
            continue
        m = H3_CARD.match(line)
        if m and h2 == '新增':
            if cur:
                cur['end'] = no - 1
            cur = {'id': m.group(1), 'label': m.group(2), 'line': no, 'end': no, 'kind': 'own',
                   'definition': '', 'what': '', 'not': '', 'separate': '', 'attrs': []}
            entities.append(cur)
            continue
        if line.startswith('### '):
            if cur:
                cur['end'] = no - 1
            cur = None
            continue
        if not cur:
            continue
        m = FIELD.match(line)
        if m:
            k, v = m.groups()
            if k == '定義':
                cur['definition'] = _plain(v, 90)
            elif k == '不是什麼':
                cur['not'] = _plain(v, 90)
            elif k == '不能跟誰合併':
                cur['separate'] = _plain(v, 110)
            continue
        m = ATTR.match(line)
        if m:
            cur['attrs'].append({'name': m.group(1), 'label': _plain(m.group(2))})
    if cur and cur['end'] == cur['line']:
        cur['end'] = len(lines)

    mb = kit.md2build()
    mb.problems.clear()
    refs, rels = [], []
    for t_h2, _, header, rows in mb.Doc(path).tables():
        hs = [h.strip() for h in header]
        if t_h2 == '引用' and hs[:1] == ['Entity']:
            for no, c in rows:
                n = NAME.match(c[0].strip())
                if n:
                    refs.append({'id': n.group(1), 'label': n.group(1), 'line': no, 'kind': 'core',
                                 'definition': _plain(c[hs.index('本切片怎麼用')], 90) if '本切片怎麼用' in hs else ''})
        elif t_h2 == '關係' and hs[:3] == ['從', '關係', '到']:
            for no, c in rows:
                cells = dict(zip(hs, c))
                lab = REL_LABEL.match(cells['關係'].strip())
                rels.append({'line': no, 'from': cells['從'].strip(), 'to': cells['到'].strip(),
                             'name': lab.group(1) if lab else cells['關係'], 'label': lab.group(2) if lab else '',
                             'card': cells.get('幾對幾', '').strip(),
                             'why': _plain(cells.get('為什麼', ''), 90),
                             'cancelled': '[已取消' in cells.get('為什麼', '')})

    known = {e['id'] for e in entities} | {r['id'] for r in refs}
    # 關係指到但不在本檔的（例：其他切片定義、core 已驗證的），也畫出來
    for r in rels:
        for k in ('from', 'to'):
            if r[k] not in known:
                refs.append({'id': r[k], 'label': r[k], 'line': None, 'kind': 'other', 'definition': ''})
                known.add(r[k])
    return {'path': kit.rel(path), 'entities': entities, 'refs': refs, 'relations': rels}


def mark_changed(model, review):
    """審查頁確認列「在哪裡」指到 02_entities.md 的哪幾行 → 哪些卡、哪些關係是這輪要看的。"""
    lines = {}
    for c in review['confirms']:
        for m in re.finditer(r'02_entities\.md:(\d+)', c['cells'].get('在哪裡', '')):
            lines.setdefault(int(m.group(1)), []).append(c['line'])
    for e in model['entities']:
        e['confirm_lines'] = sorted({cl for n, cls in lines.items() if e['line'] <= n <= e['end'] for cl in cls})
        e['changed'] = bool(e['confirm_lines'])
    for r in model['relations']:
        r['confirm_lines'] = lines.get(r['line'], [])
        r['changed'] = bool(r['confirm_lines'])
    return model
