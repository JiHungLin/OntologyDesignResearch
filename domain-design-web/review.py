"""讀寫審查頁（slices/<切片>/reviews/<日期>_<步驟>.md），格式見工具包 templates/review.md。
切欄用工具包的 md2build（和 lint.py、table.py 同一個方式），寫回時只改人要填的欄位，其他行不動。"""
import hashlib
import re

import kit

H3_QUESTION = re.compile(r'^### 問題\s*(\d+)\s*(?:（(.*)）)?\s*$')
ITEM = re.compile(r'^- (背景|問題|其他|你的回答)：\s*(.*)$')
OPTION = re.compile(r'^- ([A-Z])(（建議）)?：\s*(.*)$')
FILE_REF = re.compile(r'`?([^\s`「」（）()、，]+?\.(?:md|ya?ml|js|sql|py)):(\d+)`?')


def digest(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def _empty(v):
    return not v or v.strip() in ('', '（空）')


def parse(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n')
    mb = kit.md2build()
    mb.problems.clear()
    doc = mb.Doc(path)
    title = next((l[2:].strip() for l in lines if l.startswith('# ')), path)

    # 選擇題：第一節與「通過後新增」都可能有
    questions, cur, h2 = [], None, None
    for no, line in enumerate(lines, 1):
        if line.startswith('## '):
            h2, cur = line[3:].strip(), None
            continue
        m = H3_QUESTION.match(line)
        if m:
            cur = {'n': int(m.group(1)), 'ref': m.group(2) or '', 'section': h2, 'line': no,
                   'background': '', 'question': '', 'options': [], 'other': '', 'answer': '', 'answer_line': None}
            questions.append(cur)
            continue
        if line.startswith('### '):
            cur = None
            continue
        if cur is None:
            continue
        m = OPTION.match(line)
        if m:
            cur['options'].append({'key': m.group(1), 'recommended': bool(m.group(2)), 'text': m.group(3)})
            continue
        m = ITEM.match(line)
        if m:
            k, v = m.groups()
            if k == '你的回答':
                cur['answer'], cur['answer_line'] = v, no
            else:
                cur[{'背景': 'background', '問題': 'question', '其他': 'other'}[k]] = v
            continue
        if line.startswith('  ') and line.strip() and not line.strip().startswith('<!--'):
            # 前一項的續行
            if cur['options'] and not cur['answer_line']:
                cur['options'][-1]['text'] += '\n' + line.strip()

    # 表格：確認、抽查、結論、開頭的項目表
    meta, confirms, spot, conclusion = [], [], [], []
    for t_h2, t_h3, header, rows in doc.tables():
        hs = [h.strip() for h in header]
        if t_h2 is None and hs[:2] == ['項目', '內容']:
            meta = [{'key': c[0], 'value': c[1]} for _, c in rows]
        elif '確認' in hs and '原文' in hs:
            for no, c in rows:
                confirms.append({'line': no, 'section': t_h2, 'cells': dict(zip(hs, c)), 'answer': c[hs.index('確認')]})
        elif hs and hs[0].startswith('抽查'):
            for no, c in rows:
                spot.append({'line': no, 'items': c[0], 'result': c[1] if len(c) > 1 else ''})
        elif '結論' in hs and '步驟' in hs:
            for no, c in rows:
                conclusion.append({'line': no, 'cells': dict(zip(hs, c))})

    sections = {}
    h2 = None
    for line in lines:
        if line.startswith('## '):
            h2 = line[3:].strip()
            sections[h2] = []
        elif h2:
            sections[h2].append(line)
    def section_text(prefix):
        for k, v in sections.items():
            if k.startswith(prefix):
                return '\n'.join(l for l in v if not l.strip().startswith('<!--')).strip()
        return ''
    spot_hint = next((l for l in sections.get(next((k for k in sections if k.startswith('四')), ''), [])
                      if l.startswith('可挑的條目')), '')

    counts = {
        'questions': len(questions),
        'questions_open': sum(1 for q in questions if _empty(q['answer'])),
        'confirms': len(confirms),
        'confirms_open': sum(1 for c in confirms if _empty(c['answer'])),
        'spot_done': any(not _empty(s['items']) and not _empty(s['result']) for s in spot),
        'conclusion_done': bool(conclusion) and all(not _empty(c['cells'].get('結論', '')) for c in conclusion),
    }
    counts['open'] = (counts['questions_open'] + counts['confirms_open']
                      + (0 if counts['spot_done'] else 1) + (0 if counts['conclusion_done'] else 1))
    return {
        'title': title, 'digest': digest(text), 'meta': meta,
        'questions': questions, 'confirms': confirms, 'spot': spot, 'spot_hint': spot_hint,
        'conclusion': conclusion, 'golden': section_text('三'), 'counts': counts,
        'problems': [f'{no} {msg}' for p, no, msg in mb.problems if p == path],
    }


class Conflict(Exception):
    """檔案在讀取之後被改過（例：AI 正在修改），請重新載入。"""


def _escape(v):
    return ' '.join(str(v).split('\n')).replace('|', '\\|').strip()


def _load(path, expect_digest):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if expect_digest and digest(text) != expect_digest:
        raise Conflict(path)
    return text.split('\n')


def _save(path, lines):
    text = '\n'.join(lines)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return digest(text)


def set_answer(path, line, value, expect_digest=None):
    """寫入選擇題的「你的回答」。line 是 parse() 給的 answer_line。"""
    lines = _load(path, expect_digest)
    if not 0 < line <= len(lines) or not lines[line - 1].startswith('- 你的回答：'):
        raise Conflict(path)
    lines[line - 1] = '- 你的回答：' + ' '.join(str(value).split('\n')).strip()
    return _save(path, lines)


def set_cells(path, line, values, expect_digest=None):
    """改表格某一列的幾個欄位（欄名 → 值）。只能改人填的欄。"""
    allowed = {'確認', '抽查了哪幾條', '結果', '審查者（非產出者）', '審查者', '日期', '結論'}
    lines = _load(path, expect_digest)
    header = _header_of(lines, line)
    if header is None:
        raise Conflict(path)
    split = kit.md2build().split_row
    cells = split(lines[line - 1])
    for k, v in values.items():
        if k not in allowed or k not in header:
            raise ValueError(f'不能改這一欄：{k}')
        cells[header.index(k)] = v
    lines[line - 1] = '|' + '|'.join(f' {v} ' if v else ' ' for v in map(_escape, cells)) + '|'
    return _save(path, lines)


def add_spot_row(path, expect_digest=None):
    """抽查表多加一列空白列（第一列已填時用）。"""
    lines = _load(path, expect_digest)
    split = kit.md2build().split_row
    for i, l in enumerate(lines):
        if l.startswith('|') and split(l)[0].startswith('抽查'):
            j = i + 2
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            lines.insert(j, '| | |')
            return _save(path, lines)
    raise Conflict(path)


def _header_of(lines, line):
    split = kit.md2build().split_row
    if not 0 < line <= len(lines) or not lines[line - 1].startswith('|'):
        return None
    i = line - 1
    while i > 0 and lines[i - 1].startswith('|'):
        i -= 1
    # i 是表頭；表頭下一行要是分隔線，要改的列在分隔線之後
    if line - 1 <= i + 1 or not re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
        return None
    return [h.strip() for h in split(lines[i])]
