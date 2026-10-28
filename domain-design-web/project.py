"""整個 domain 的進度：規劃（主題草案、現實資料盤點、推想草稿、切片地圖、名詞草圖）與各切片各步驟的狀態。
一律從切片 repo 的檔案算出（docs/02 第五節的格式），網頁不另存狀態。"""
import datetime
import os
import re

import kit
import review

STEP_FILES = [(1, '範圍', '01_scope.md'), (2, '名詞', '02_entities.md'), (3, '流程', '03_flows.md'),
              (4, '規則', '04_rules.md'), (5, '對照', '05_mapping.md'), (6, '驗收', '06_evidence/signoff.md')]
TOPIC_FILE = 'inputs/shared/主題草案.md'
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]*$')


def _p(*parts):
    return os.path.join(kit.repo(), *parts)


def _read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def _tables(path):
    mb = kit.md2build()
    mb.problems.clear()
    out = list(mb.Doc(path).tables())
    mb.problems.clear()
    return out


def head(path):
    """開頭區（| 項目 | 內容 |）：{項目: {'line', 'value'}}。"""
    if not os.path.exists(path):
        return {}
    for _, _, header, rows in _tables(path):
        if [h.strip() for h in header[:2]] == ['項目', '內容']:
            return {c[0].strip(): {'line': no, 'value': c[1].strip()} for no, c in rows}
    return {}


def _rows(path, h2_prefix, first_col):
    """某一節（## 開頭符合）裡、第一欄名稱符合的表格，每列轉成 {欄名: 值, 'line': 行號}。"""
    out = []
    for h2, _, header, rows in _tables(path):
        hs = [h.strip() for h in header]
        if (h2 or '').startswith(h2_prefix) and hs[:1] == [first_col]:
            out += [dict(zip(hs, [c.strip() for c in cells]), line=no) for no, cells in rows]
    return out


def _bullets(path, h2):
    text = _read(path) or ''
    m = re.search(r'^## ' + re.escape(h2) + r'\s*$(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not m:
        return []
    return [l[2:].strip() for l in m.group(1).split('\n') if l.startswith('- ')]


# ---- 規劃 ----

def plan():
    path = _p('slices', 'PLAN.md')
    if not os.path.exists(path):
        return None
    h = head(path)
    st = h.get('狀態', {}).get('value', '')
    return {
        'path': 'slices/PLAN.md', 'status': st, 'agreed': st.startswith('已同意'),
        'basis': h.get('依據', {}).get('value', ''),
        'inventory': _rows(path, '現實資料盤點', '資料'),
        'goals': _bullets(path, '整體目標'),
        'domains': _rows(path, '領域', '領域'),
        'slices': _rows(path, '切片', '切片'),
        'pending': _rows(path, '待釐清', '編號'),
        'decisions': _rows(path, '決定與理由', '#'),
    }


def sketch():
    path = _p('slices', 'ENTITY_SKETCH.md')
    if not os.path.exists(path):
        return None
    h = head(path)
    unsure = _bullets(path, '不確定的地方')
    return {'path': 'slices/ENTITY_SKETCH.md', 'status': h.get('狀態', {}).get('value', ''),
            'nouns': _rows(path, '名詞', '名詞'), 'unsure': unsure}


def drafts():
    d = _p('inputs', 'drafts')
    out = []
    if not os.path.isdir(d):
        return out
    for n in sorted(os.listdir(d)):
        if not n.endswith('.md'):
            continue
        path = os.path.join(d, n)
        h = head(path)
        title = next((l[2:].strip() for l in (_read(path) or '').split('\n') if l.startswith('# ')), n)
        st = h.get('狀態', {})
        out.append({'path': kit.rel(path), 'title': title, 'status': st.get('value', ''), 'status_line': st.get('line'),
                    'unsure': h.get('最不確定的地方', {}).get('value', ''),
                    'who': h.get('需要誰確認', {}).get('value', ''),
                    'pending': st.get('value', '').startswith('待接受')})
    return out


def inputs():
    """inputs/ 底下的檔案（相對路徑），依資料夾分組。"""
    root = _p('inputs')
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(x for x in dns if not x.startswith('.'))
        for f in sorted(fns):
            if f.startswith('.'):
                continue
            rel = kit.rel(os.path.join(dp, f))
            out.setdefault(os.path.dirname(rel), []).append(rel)
    return out


def topic():
    path = _p(TOPIC_FILE)
    return TOPIC_FILE if os.path.exists(path) else None


# ---- 切片 ----

def steps(slice_):
    """各步驟的狀態（草稿／待檢查／已凍結；檔案不存在＝未開始）與版本。"""
    out = []
    for n, name, fn in STEP_FILES:
        path = _p('slices', slice_, fn)
        if not os.path.exists(path):
            out.append({'n': n, 'name': name, 'file': fn, 'status': '未開始', 'version': ''})
            continue
        h = head(path)
        out.append({'n': n, 'name': name, 'file': fn, 'status': h.get('狀態', {}).get('value', '草稿') or '草稿',
                    'version': h.get('版本', {}).get('value', '')})
    return out


def eqs(slice_):
    path = _p('slices', slice_, 'questions.md')
    if not os.path.exists(path):
        return []
    return [r for r in _rows(path, '', '編號') if re.match(r'EQ-\d+', r.get('編號', ''))]


def next_step(st):
    """下一個要 AI 做的步驟：第一個不是「已凍結」的；⑥ 在有系統時才做，所以 ①～⑤ 都凍結就算設計完成。"""
    for s in st:
        if not s['status'].startswith('已凍結'):
            return s
    return None


# ---- 寫入（只寫人做的事） ----

def _today():
    return datetime.date.today().isoformat()


def accept_draft(rel, who, expect_digest=None):
    """推想草稿：使用者接受為假設。只改開頭區的「狀態」，而且只從「待接受」改。"""
    path = kit.resolve(rel)
    if not path or not kit.rel(path).startswith('inputs' + os.sep + 'drafts' + os.sep):
        raise ValueError('不是推想草稿')
    h = head(path)
    st = h.get('狀態')
    if not st or not st['value'].startswith('待接受'):
        raise ValueError(f'這份草稿的狀態是「{st and st["value"]}」，不是待接受')
    return review.set_row(path, st['line'], {'內容': f'已接受為假設（{who}，{_today()}）'}, {'內容'}, expect_digest)


def mark_asked(slice_, line, expect_digest=None):
    """專家問題：使用者已經問了專家（待問 → 已問）。"""
    path = _p('slices', slice_, 'questions.md')
    row = next((r for r in eqs(slice_) if r['line'] == line), None)
    if not row or row.get('狀態') != '待問':
        raise ValueError('這一題不是「待問」')
    return review.set_row(path, line, {'狀態': '已問'}, {'狀態'}, expect_digest)


def add_input(folder, name, text, note='使用者於對話中提供'):
    """把使用者貼上或寫下的東西存成 inputs/ 下的新檔（已存在的不覆寫）。"""
    folder = folder.strip('/')
    if folder not in ('shared',) and not SLUG.match(folder):
        raise ValueError('資料夾只能是 shared 或切片代號')
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name.strip()).strip('_') or '資料'
    if not name.endswith('.md'):
        name += '.md'
    path = _p('inputs', folder, name)
    if os.path.exists(path):
        raise FileExistsError(f'inputs/{folder}/{name} 已存在，換個名稱')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    title = name[:-3]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n> {note}，{_today()}（流程網頁）\n\n{text.strip()}\n')
    return kit.rel(path)


def add_upload(folder, name, data):
    """上傳的原始檔（Excel、PDF、圖片）原樣存進 inputs/。"""
    folder = folder.strip('/')
    if folder not in ('shared',) and not SLUG.match(folder):
        raise ValueError('資料夾只能是 shared 或切片代號')
    name = os.path.basename(name).strip()
    if not name or name.startswith('.'):
        raise ValueError('檔名不對')
    path = _p('inputs', folder, name)
    if os.path.exists(path):
        raise FileExistsError(f'inputs/{folder}/{name} 已存在')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return kit.rel(path)


def write_topic(fields):
    """主題草案：使用者自己寫的方向，存成 inputs/shared/主題草案.md（已存在就新增一節，不改舊的）。"""
    path = _p(TOPIC_FILE)
    order = ['想做的系統', '給誰用', '要解決什麼', '這一階段一定要做到', '明確不做', '有沒有專家或客戶', '其他']
    body = '\n'.join(f'- {k}：{fields[k].strip()}' for k in order if fields.get(k, '').strip())
    if not body:
        raise ValueError('至少寫一項')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'\n## {_today()} 補充\n\n> 使用者於對話中提供，{_today()}（流程網頁）\n\n{body}\n')
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'# 主題草案\n\n> 使用者於對話中提供，{_today()}（流程網頁）。這是使用者自己寫的方向，規劃時依它問清楚、盤點資料。\n\n'
                    f'## {_today()}\n\n{body}\n')
    return TOPIC_FILE
