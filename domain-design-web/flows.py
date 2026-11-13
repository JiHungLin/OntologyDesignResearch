"""第 ③ 步的狀態圖：從 slices/<切片>/03_flows.md 讀出每個名詞的狀態、轉換、事件，給「看圖確認」用。
不另存資料：格式是 docs/02 第 ③ 步的狀態機表（從／到／觸發事件／誰可以做／前提條件／規則）與事件表；
中文名稱取自標題、「狀態：」那一行與事件欄的括號。"""
import os
import re

import kit
from model import _plain

H3 = re.compile(r'^([A-Za-z][A-Za-z0-9]*)（([^）]+)）\s*(\[[^\]]+\])?\s*(?:（歷史需求：([^，,）]+)[^）]*）)?')   # core/ 的標題多一個 [候選]
META = re.compile(r'^- (出處|層|被引用)：\s*(.*)$')   # core/flows.md 每個名詞的出處、層、被引用
LABELED = re.compile(r'([A-Za-z][A-Za-z0-9_]*)（([^）]+)）')
NAME = re.compile(r'^([A-Za-z][A-Za-z0-9]*)')
EMPTY = {'', '（無）', '(無)', '無', '—', '-'}


def load(slice_name):
    return load_path(os.path.join(kit.repo(), 'slices', slice_name, '03_flows.md'))


def load_path(path):
    """切片的 03_flows.md 或 core/flows.md（格式相同，core 多了狀態標記與出處、層、被引用）。"""
    if not os.path.isfile(path):
        return None
    mb = kit.md2build()
    mb.problems.clear()
    doc = mb.Doc(path)
    tables = doc.tables()
    mb.problems.clear()

    machines, by_h3 = [], {}
    for no, h2, h3, line in doc.items:
        if not (h2 or '').startswith('狀態機') or not h3:
            continue
        if line is None:
            m = H3.match(h3)
            if not m:
                continue
            sm = {'id': m.group(1), 'label': m.group(2), 'history': (m.group(4) or '').strip(), 'line': no, 'end': no,
                  'status': (m.group(3) or '')[1:-1], 'meta': {}, 'states': [], 'terminal': [], 'transitions': [], 'notes': []}
            by_h3[(h2, h3)] = sm
            machines.append(sm)
            continue
        sm = by_h3.get((h2, h3))
        if not sm:
            continue
        sm['end'] = no
        s = line.strip()
        if s.startswith('狀態：'):
            sm['states'] = [{'id': a, 'label': b} for a, b in LABELED.findall(s)]
            if not sm['states']:
                sm['stateless'] = s[3:]
        elif s.startswith('終態：'):
            sm['terminal'] = re.findall(r'[A-Za-z][A-Za-z0-9_]*', s[3:])
        elif mm := META.match(s):
            sm['meta'][mm.group(1)] = mm.group(2)
        elif re.match(r'^- ', line):
            sm['notes'].append(s[2:])
        elif re.match(r'^\s+- ', line) and sm['notes']:
            sm['notes'][-1] += '\n' + s

    events = {}
    for h2, h3, header, rows in tables:
        if header[:1] == ['事件']:
            for no, c in rows:
                m = NAME.match(c[0])
                if m:
                    lab = LABELED.match(c[0])
                    row = dict(zip(header, c))
                    events[m.group(1)] = {'label': lab.group(2) if lab else '', 'line': no, 'layer': row.get('層', ''),
                                          'trigger': row.get('觸發來源', ''), 'changes': row.get('改變什麼', '')}
        sm = by_h3.get((h2, h3))
        if sm and header[:3] == ['從', '到', '觸發事件']:
            for no, c in rows:
                row = dict(zip(header, c))
                frm = '' if c[0].strip() in EMPTY else (NAME.match(c[0].strip()) or [None, c[0].strip()])[1]
                to = (NAME.match(c[1].strip()) or [None, c[1].strip()])[1]
                on = (NAME.match(c[2].strip()) or [None, c[2].strip()])[1]
                sm['transitions'].append({'from': frm, 'to': to, 'on': on, 'line': no, 'who': row.get('誰可以做', ''),
                                          'guard': row.get('前提條件', ''), 'rules': row.get('規則', '')})
                known = {s['id'] for s in sm['states']}
                for x in (frm, to):
                    if x and x not in known:
                        sm['states'].append({'id': x, 'label': ''})
                        known.add(x)
    for sm in machines:
        sm['summary'] = _plain(sm['notes'][0], 120) if sm['notes'] else ''
        for t in sm['transitions']:
            t['label'] = (events.get(t['on']) or {}).get('label', '')
    return {'path': kit.rel(path), 'machines': machines, 'events': events}


def mark(flows, review):
    """確認列指到 03_flows.md 某個名詞那一段的，掛到那個名詞（網頁在狀態圖旁邊顯示）。"""
    name = os.path.basename(flows['path'])
    for c in review['confirms']:
        for f, ln in re.findall(r'([\w./-]+\.md):(\d+)', c['cells'].get('在哪裡', '')):
            if os.path.basename(f) != name:
                continue
            for sm in flows['machines']:
                if sm['line'] <= int(ln) <= sm['end']:
                    c['machine'] = sm['id']
                    sm.setdefault('confirms', []).append(c['line'])
    return flows
