#!/usr/bin/env python3
"""把 Markdown 交付物轉成 .build/ 的 YAML，給 check.py、derive.py、impact.py 讀。
用法：python tools/md2build.py <切片代號> [--root <repo 根目錄>]
讀 core/ 與 slices/<切片>/ 的 01～04，合併後寫出 .build/ 的
cq.yaml、entities.yaml、relations.yaml、glossary.yaml、flows.yaml、rules.yaml（只寫有內容的）。
格式依 docs/02。看不懂的列會逐一列出（檔案:行號），不靜默跳過；有看不懂的列時結束碼為 2。
驗收問題的 subject、answer_type 不在 Markdown 裡，不會轉出；要跑 check.py 的 D 項時另外補上。"""
import os, re, sys, yaml

ID_RE = re.compile(r'[A-Za-z][A-Za-z0-9_]*')
ATTR_REF_RE = re.compile(r'`([A-Z][A-Za-z0-9_]*)\.([a-z][A-Za-z0-9_]*)(?:\([^`]*\))?`')
CODE_RE = re.compile(r'^[A-Z][A-Z0-9_]*\.[A-Z0-9_]+$')
RULE_ID_RE = re.compile(r'\bR\d+\b')
Q_RE = re.compile(r'(?:[a-z0-9-]+:)?Q\d+')

SOURCE = {'Domain 專家': 'domain_expert', '客戶端使用者': 'client_user', '現場紀錄': 'field_record',
          '爭議案例': 'dispute_case', '外部從業者': 'practitioner', '維運': 'operations',
          '法規': 'regulation', 'AI': 'ai'}
HISTORY = {'只需現況': 'current_only', '需要軌跡': 'trail', '需要重建當時': 'reconstruct'}
TRIGGER = {'人的動作': 'actor', '其他單位個體的變化': 'entity_change',
           '外部系統或訊息': 'external', '時間或條件到達': 'time'}
LAYER = {'要求': 'command', '建議': 'proposal', '決定': 'decision', '發生': 'event', '執行': 'execution'}
TIMES = {'發生': 'occurred_at', '得知': 'recorded_at', '生效': 'effective_from'}
KIND = {'前提條件': 'precondition', '計算': 'calculation', '判定': 'determination'}
DECIDE = {'可自動判斷': 'automatic', '看條件': 'conditional', '需解釋': 'interpretive', '需人工判斷': 'human'}
VIOLATION = {'擋下': 'block', '提醒': 'warn', '交給人判斷': 'escalate', '—': 'none'}
TERM_KIND = {'Entity': 'entity', '屬性': 'attribute', '關係': 'relation', '事件': 'event',
             '狀態': 'state', '分類值': 'classification_value'}
CARD_KEYS = {'定義': 'definition', '身分': 'identity_basis', '何時開始': 'begins_when',
             '何時結束': 'ends_when', '不是什麼': 'not_used_for', '不能跟誰合併': 'not_mergeable_with',
             '主要屬性': 'attributes', '對應驗收問題': 'required_by_cq',
             '出處': 'source', '層': 'layer', '被引用': 'referenced_by', '備註': 'note'}
EMPTY = {'', '—', '-', '（無）', '無'}

problems = []   # 錯誤：違反 docs/02 的固定選項或結構 (檔案, 行號, 說明)
warnings = []   # 提醒：寫在格式之外、沒有轉出的內容

def problem(path, no, msg):
    problems.append((path, no, msg))

def warn(path, no, msg):
    warnings.append((path, no, msg))

def option(cell, table):
    """固定選項；允許後面接括號或分號說明（例：「看條件（人數、行業）」）。"""
    v = (cell or '').strip()
    if v in table: return table[v]
    for k, val in table.items():
        if v.startswith(k) and v[len(k):len(k) + 1] in ('（', '(', '；', ';', '，', ' '):
            return val
    return None

def lead_id(cell):
    """儲存格開頭的英文識別名稱（例：「ApproveLeave（核准請假）」→ ApproveLeave）。"""
    m = re.match(r'\s*`?([A-Za-z][A-Za-z0-9_]*)', cell or '')
    return m.group(1) if m else None

def ids_in(cell):
    """儲存格中以「、」「／」分隔的每一項的開頭識別名稱。"""
    return [i for i in (lead_id(p) for p in re.split(r'[、／,]', cell or '')) if i]

def status_of(markers):
    """標題列的狀態標記 → (status, superseded_by)。"""
    for m in markers:
        if m == '候選': return 'candidate', None
        if m == '已驗證': return 'verified', None
        if m == '已驗證（暫代）': return 'verified_proxy', None
        if m.startswith('已取代'):
            parts = re.split(r'[:：，,]\s*', m)
            return 'superseded', {'id': parts[1] if len(parts) > 1 else None,
                                  'effective_from': parts[2] if len(parts) > 2 else None}
        if m.startswith('已停用'):
            parts = re.split(r'[:：]\s*', m)
            return 'retired', {'effective_from': parts[1] if len(parts) > 1 else None}
    return None, None

def cancelled(cell):
    """[已取消: …] 標記；舊寫法（〔已取消…〕、（已取消…））也認得，但列為要改的寫法。"""
    s = (cell or '').strip()
    if s.startswith('[已取消'):
        return 'marker'
    if re.match(r'^[〔（(]已取消', s):
        return 'legacy'
    return None

# ---------- 讀檔：標題、表格、條列 ----------

class Doc:
    def __init__(self, path):
        self.path = path
        self.items = []          # (行號, h2, h3, 行)
        h2 = h3 = None
        in_code = in_comment = False
        with open(path, encoding='utf-8') as f:
            for no, line in enumerate(f, 1):
                line = line.rstrip('\n')
                s = line.strip()
                if s.startswith('```'):
                    in_code = not in_code; continue
                if in_code: continue
                if in_comment:
                    if '-->' in s: in_comment = False
                    continue
                if s.startswith('<!--'):
                    if '-->' not in s: in_comment = True
                    continue
                if line.startswith('## '):
                    h2, h3 = line[3:].strip(), None; continue
                if line.startswith('### '):
                    h3 = line[4:].strip()
                    self.items.append((no, h2, h3, None)); continue
                self.items.append((no, h2, h3, line))

    def tables(self):
        """逐一回傳表格：(h2, h3, 表頭, [(行號, 儲存格)])。欄數不符的列記為看不懂。"""
        out, cur = [], None
        lines = [(no, h2, h3, l) for no, h2, h3, l in self.items if l is not None]
        i = 0
        while i < len(lines):
            no, h2, h3, l = lines[i]
            nxt = lines[i + 1][3] if i + 1 < len(lines) else ''
            if l.strip().startswith('|') and re.match(r'^\s*\|[\s:|-]+\|\s*$', nxt or '') and '-' in nxt:
                header = split_row(l)
                rows, j = [], i + 2
                while j < len(lines) and lines[j][3].strip().startswith('|'):
                    cells = split_row(lines[j][3])
                    if len(cells) != len(header):
                        problem(self.path, lines[j][0], f'欄數不對：表頭 {len(header)} 欄，這列 {len(cells)} 欄')
                    else:
                        rows.append((lines[j][0], cells))
                    j += 1
                out.append((h2, h3, header, rows))
                i = j; continue
            i += 1
        return out

def split_row(line):
    s = line.strip()
    if s.startswith('|'): s = s[1:]
    if s.endswith('|'): s = s[:-1]
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', s)]

def col(header, *names):
    """依欄名找欄位位置（開頭符合即可）。"""
    for n in names:
        for k, h in enumerate(header):
            if h.startswith(n): return k
    return None

# ---------- ① 驗收問題 ----------

def parse_cq(doc):
    cqs = []
    for h2, h3, header, rows in doc.tables():
        if not (header[0] == '編號' and len(header) > 1 and header[1].startswith('問題')):
            continue
        ci, cp, cs, cc = col(header, '問題'), col(header, '優先'), col(header, '來源'), col(header, '確認')
        for no, c in rows:
            if not re.fullmatch(r'Q\d+', c[0]):
                problem(doc.path, no, f'驗收問題編號「{c[0]}」不是 Qnn'); continue
            q = {'id': c[0], 'question': c[ci]}
            if cp is not None: q['priority'] = c[cp]
            if cs is not None:
                src = next((v for k, v in SOURCE.items() if c[cs].startswith(k)), None)
                if src: q['source'] = src
                else: problem(doc.path, no, f'{c[0]} 的來源「{c[cs]}」不在固定選項內')
            if cc is not None:
                v = c[cc]
                q['confirmed'] = ('pending_expert' if '待專家確認' in v else 'proxy' if '暫代' in v
                                  else 'confirmed' if '已確認' in v else None)
                if not q['confirmed']:
                    problem(doc.path, no, f'{c[0]} 的確認「{v}」不在固定選項內'); del q['confirmed']
            cqs.append(q)
    return cqs

# ---------- ② Entity 卡、關係、詞彙對照表 ----------

def parse_cards(doc, origin, only_h2=None):
    """Entity 卡：### 標題 + 「- 欄位：值」條列；主要屬性是下一層的條列。"""
    ents, cur, in_attrs = [], None, False
    for no, h2, h3, line in doc.items:
        if line is None:                          # 新的 ### 標題
            cur, in_attrs = None, False
            if only_h2 and h2 != only_h2: continue
            name = lead_id(h3)
            if not name:
                problem(doc.path, no, f'Entity 卡標題「{h3}」開頭不是英文識別名稱'); continue
            markers = re.findall(r'\[([^\]]+)\]', h3)
            zh = re.search(r'（([^）]*)）', h3)
            status, sup = status_of(markers)
            cur = {'name': name, 'origin': 'static_substitute' if '靜態替代' in markers else origin}
            if zh: cur['label'] = zh.group(1)
            if status: cur['status'] = status
            if sup: cur['superseded_by'] = sup
            cur['attributes'] = []
            cur['_line'] = no
            ents.append(cur); continue
        if cur is None or (only_h2 and h2 != only_h2): continue
        if not line.strip(): continue
        m = re.match(r'^- ([^：:]+)[：:]\s*(.*)$', line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            field = CARD_KEYS.get(key)
            in_attrs = field == 'attributes'
            if field is None:
                warn(doc.path, no, f'{cur["name"]} 卡片有格式以外的欄位「{key}」（沒有轉出）'); continue
            if field in ('begins_when', 'ends_when'):
                cur.setdefault('lifecycle', {})[field] = val
            elif field == 'not_used_for':
                cur[field] = [x.strip() for x in val.split('；') if x.strip()]
            elif field == 'not_mergeable_with':
                cur[field] = [i for i in (lead_id(x) for x in val.split('；')) if i]
            elif field == 'required_by_cq':
                cur[field] = Q_RE.findall(val)
            elif field == 'referenced_by':
                cur[field] = [x for x in re.split(r'[、,，\s]+', val) if x]
            elif field != 'attributes':
                cur[field] = val
            continue
        m = re.match(r'^\s{2,}- (.*)$', line)
        if m and in_attrs:
            a = re.match(r'`([A-Za-z][A-Za-z0-9_]*)(\([^`]*\))?`\s*(?:（([^）]*)）)?', m.group(1))
            if not a:
                problem(doc.path, no, f'{cur["name"]} 的屬性沒有用 `英文識別名稱` 開頭'); continue
            attr = {'name': a.group(1)}
            if a.group(2): attr['signature'] = a.group(1) + a.group(2)
            if a.group(3): attr['meaning'] = a.group(3)
            attr['derived'] = '[推導]' in m.group(1)
            cur['attributes'].append(attr)
            continue
        if line.startswith('  ') or line.startswith('\t'):
            continue                               # 前一項的續行
        if in_attrs or line.startswith('- '):
            problem(doc.path, no, f'{cur["name"]} 卡片中看不懂的行')
    for e in ents:
        e.pop('_line', None)
    return ents

def parse_refs(doc):
    out = []
    for h2, h3, header, rows in doc.tables():
        if h2 == '引用' and header[0] == 'Entity':
            for no, c in rows:
                if c[0] in EMPTY: continue
                n = lead_id(c[0])
                if n: out.append(n)
                else: problem(doc.path, no, f'引用表的「{c[0]}」不是英文識別名稱')
    return out

def parse_relations(doc):
    rels = []
    for h2, h3, header, rows in doc.tables():
        if not (header[:3] == ['從', '關係', '到']): continue
        cc, cp, cst = col(header, '幾對幾'), col(header, '有無期間'), col(header, '狀態')
        for no, c in rows:
            dom, name, rng = lead_id(c[0]), lead_id(c[1]), ids_in(c[2])
            if not (dom and name and rng):
                problem(doc.path, no, '關係的「從」「關係」「到」要寫英文識別名稱'); continue
            r = {'id': f'{dom}.{name}', 'name': name, 'domain': dom,
                 'range': rng[0] if len(rng) == 1 else rng}
            if cc is not None:
                if c[cc] not in ('0..1', '1', '0..*', '1..*'):
                    problem(doc.path, no, f'{dom}.{name} 的幾對幾「{c[cc]}」不在固定選項內')
                r['cardinality'] = c[cc]
            if cp is not None and c[cp].startswith('有'):
                r['temporal'] = {'valid_from': 'required'}
            if cst is not None:
                s, sup = status_of(re.findall(r'\[([^\]]+)\]', c[cst]))
                if s: r['status'] = s
            rels.append(r)
    return rels

def parse_glossary(doc):
    terms = []
    for h2, h3, header, rows in doc.tables():
        if not (header[0] == 'ID' and len(header) > 1 and header[1] == '種類'): continue
        cd, cz, cn, cst = col(header, '定義'), col(header, 'zh-TW'), col(header, '對照備註'), col(header, '狀態')
        for no, c in rows:
            kind = TERM_KIND.get(c[1])
            if c[1] == '規則':
                warn(doc.path, no, f'規則不登錄在詞彙對照表（規則表本身就是登錄處），「{c[0]}」這列可以刪除'); continue
            if not kind:
                problem(doc.path, no, f'詞彙「{c[0]}」的種類「{c[1]}」不在固定選項內'); continue
            t = {'id': c[0].strip('`'), 'kind': kind}
            if cd is not None: t['definition'] = c[cd]
            if cz is not None: t['labels'] = {'zh-TW': c[cz]}
            if cn is not None and c[cn] not in EMPTY: t['equivalence_note'] = c[cn]
            if cst is not None:
                s, _ = status_of(re.findall(r'\[([^\]]+)\]', c[cst]))
                if s: t['status'] = s
            terms.append(t)
    return terms

# ---------- ③ 狀態機、事件、更正方式 ----------

def parse_flows(doc):
    sms, events, cors = [], [], []
    # 狀態機：「## 狀態機…」底下、標題含「歷史需求」或有轉換表的 ###
    sm_by_h3 = {}
    for no, h2, h3, line in doc.items:
        if not (h2 or '').startswith('狀態機') or not h3: continue
        if line is None:
            name = lead_id(h3)
            hist = re.search(r'歷史需求：([^，,）]+)', h3)
            sm = {'entity': name, 'states': [], 'terminal': [], 'transitions': []}
            if hist:
                sm['history'] = HISTORY.get(hist.group(1).strip())
                if not sm['history']:
                    problem(doc.path, no, f'{name} 的歷史需求「{hist.group(1)}」不在固定選項內')
                sm['history_basis'] = Q_RE.findall(h3[hist.end():])
            sm['_has_history'] = bool(hist)
            sm_by_h3[(h2, h3)] = sm
            continue
        sm = sm_by_h3.get((h2, h3))
        if not sm: continue
        s = line.strip()
        if s.startswith('狀態：'):
            sm['states'] = re.findall(r'([A-Za-z][A-Za-z0-9_]*)（', s) or ID_RE.findall(s[3:])
        elif s.startswith('終態：'):
            sm['terminal'] = ID_RE.findall(s[3:])
    for h2, h3, header, rows in doc.tables():
        if (h2, h3) in sm_by_h3 and header[:3] == ['從', '到', '觸發事件']:
            sm = sm_by_h3[(h2, h3)]
            cw, cg, cr = col(header, '誰可以做'), col(header, '前提條件'), col(header, '規則')
            for no, c in rows:
                frm = c[0] if c[0] in EMPTY else lead_id(c[0])
                to, on = lead_id(c[1]), lead_id(c[2])
                ext = re.match(r'^[（(]由\s*([a-z0-9-]+)\s*定義', c[2])
                if ext and frm and to:
                    on = None                     # 觸發事件由其他切片定義
                if not (frm and to and (on or ext)):
                    problem(doc.path, no, f'{sm["entity"]} 的狀態轉換看不懂（從、到、觸發事件要寫英文識別名稱）'); continue
                t = {'from': frm, 'to': to, 'on': on}
                if ext: t['defined_by'] = ext.group(1)
                if cw is not None: t['authority'] = c[cw]
                if cg is not None and c[cg] not in EMPTY: t['guard'] = c[cg]
                if cr is not None: t['rules'] = RULE_ID_RE.findall(c[cr])
                sm['transitions'].append(t)
                for x in (frm, to):
                    if x not in EMPTY and x not in sm['states']: sm['states'].append(x)
    for sm in sm_by_h3.values():
        if sm.pop('_has_history') or sm['transitions']:
            if sm['states']: sm['initial'] = sm['states'][0]
            sms.append(sm)
    for h2, h3, header, rows in doc.tables():
        if header[:2] == ['事件', '觸發來源']:
            cl, cs, cch, ce, crv, ct = (col(header, '層'), col(header, '主體'), col(header, '改變什麼'),
                                        col(header, '證據'), col(header, '能否撤銷'), col(header, '有意義的時間'))
            for no, c in rows:
                name = lead_id(c[0])
                if not name:
                    problem(doc.path, no, f'事件「{c[0]}」開頭不是英文識別名稱'); continue
                ev = {'name': name}
                trig = option(c[1], TRIGGER)
                ev['trigger'] = trig or c[1]
                if not trig: problem(doc.path, no, f'{name} 的觸發來源「{c[1]}」不在固定選項內')
                if cl is not None:
                    ev['layer'] = option(c[cl], LAYER) or c[cl]
                    if not option(c[cl], LAYER): problem(doc.path, no, f'{name} 的層「{c[cl]}」不在固定選項內')
                if cs is not None: ev['subject'] = lead_id(c[cs]) or c[cs]
                if cch is not None: ev['changes'] = 'none' if '不改變狀態' in c[cch] else c[cch]
                if ce is not None and c[ce] not in EMPTY: ev['evidence'] = [c[ce]]
                if crv is not None: ev['reversible_by'] = c[crv]
                if ct is not None:
                    ev['time_semantics'] = {v: 'required' for k, v in TIMES.items() if k in c[ct]}
                events.append(ev)
        elif header[:2] == ['對象', '更正事件']:
            cd, ca, cr = col(header, '誰發現'), col(header, '誰核准'), col(header, '與原紀錄的關係')
            for no, c in rows:
                tgt, act = lead_id(c[0]) or c[0], lead_id(c[1])
                if not act:
                    warn(doc.path, no, '更正方式的「更正事件」開頭不是事件名稱（沒有轉出）'); continue
                cor = {'target': tgt, 'action': act}
                if cd is not None: cor['detected_by'] = c[cd]
                if ca is not None and c[ca] not in EMPTY and not c[ca].startswith('不需'):
                    cor['approved_by'] = c[ca]
                if cr is not None: cor['relation_to_original'] = c[cr]
                cors.append(cor)
    return sms, events, cors

# ---------- ④ 規則、守恆式、分類值 ----------

def parse_rules(doc):
    rules, cons, codes = [], [], []
    for h2, h3, header, rows in doc.tables():
        if header[:2] == ['編號', '規則']:
            idx = {k: col(header, k) for k in ('種類', '套用對象', '判斷方式', '違反時', '來源', '版本', '核對', '狀態')}
            for no, c in rows:
                if not re.fullmatch(r'R\d+', c[0]):
                    problem(doc.path, no, f'規則編號「{c[0]}」不是 Rnn'); continue
                text = c[1]
                r = {'id': c[0], 'statement': text}
                cx = cancelled(text)
                if cx:
                    r['status'] = 'cancelled'
                    if cx == 'legacy':
                        problem(doc.path, no, f'{c[0]} 的取消寫法要改成 [已取消: <依據>]')
                    rules.append(r); continue
                def get(k): return c[idx[k]] if idx[k] is not None else None
                for k, table, key in (('種類', KIND, 'kind'), ('判斷方式', DECIDE, 'decidability'),
                                      ('違反時', VIOLATION, 'on_violation')):
                    v = get(k)
                    if v is None: continue
                    if option(v, table): r[key] = option(v, table)
                    else: problem(doc.path, no, f'{c[0]} 的{k}「{v}」不在固定選項內')
                if get('套用對象'):
                    r['applies_to'] = ids_in(get('套用對象'))
                    r['applies_to_text'] = get('套用對象')
                if get('來源'): r['source'] = {'ref': get('來源')}
                ver = get('版本')
                if ver and ver not in EMPTY:
                    r['versioned'] = True
                    d = re.search(r'\d{4}-\d{2}-\d{2}', ver)
                    if d: r['effective_from'] = d.group(0)
                r['discriminates'] = sorted({f'{e}.{a}' for e, a in ATTR_REF_RE.findall(text)})
                r['interpretations'] = re.findall(r'\[解讀[:：]\s*([^\]]*)\]', text)
                chk = get('核對')
                if chk is not None:
                    r['verified'] = None if ('未核對' in chk or chk in EMPTY) else chk
                if get('狀態'):
                    s, _ = status_of(re.findall(r'\[([^\]]+)\]', get('狀態')))
                    if s: r['status'] = s
                rules.append(r)
        elif header[:2] == ['編號', '等式']:
            ca = col(header, '套用對象')
            for no, c in rows:
                cons.append({'id': c[0], 'equation': c[1],
                             'applies_to': c[ca] if ca is not None else None})
        elif header[:2] == ['代碼', '屬於']:
            cj, cz = col(header, '管轄區'), col(header, 'zh-TW')
            for no, c in rows:
                code = c[0].strip('`')
                if not CODE_RE.match(code):
                    problem(doc.path, no, f'分類值代碼「{c[0]}」格式不對：一列只寫一個代碼，格式 <分類>.<值>'); continue
                v = {'id': code, 'kind': 'classification_value', 'of': c[1]}
                if cj is not None: v['jurisdiction'] = c[cj]
                if cz is not None: v['labels'] = {'zh-TW': c[cz]}
                codes.append(v)
    return rules, cons, codes

# ---------- 合併與輸出 ----------

def merge(base, new, key):
    out = {key(x): x for x in base}
    for x in new: out[key(x)] = x
    return list(out.values())

def build(root, slice_name):
    core = lambda f: os.path.join(root, 'core', f)
    sl = lambda f: os.path.join(root, 'slices', slice_name, f)
    exists = os.path.exists
    data = {}

    if exists(sl('01_scope.md')):
        data['cq'] = parse_cq(Doc(sl('01_scope.md')))

    ents, rels, terms = [], [], []
    if exists(core('entities.md')): ents = parse_cards(Doc(core('entities.md')), 'core_ref')
    if exists(core('relations.md')): rels = parse_relations(Doc(core('relations.md')))
    if exists(core('glossary.md')): terms = parse_glossary(Doc(core('glossary.md')))
    if exists(sl('02_entities.md')):
        d = Doc(sl('02_entities.md'))
        known = {e['name'] for e in ents}
        for n in parse_refs(d):
            if n not in known:
                ents.append({'name': n, 'origin': 'core_ref', 'attributes': []}); known.add(n)
        ents = merge(ents, parse_cards(d, 'new', only_h2='新增'), lambda e: e['name'])
        rels = merge(rels, parse_relations(d), lambda r: (r['domain'], r['name'], str(r['range'])))
        terms = merge(terms, parse_glossary(d), lambda t: t['id'])
    sms, evts, cors = [], [], []
    for f in (core('flows.md'), sl('03_flows.md')):
        if exists(f):
            s, e, c = parse_flows(Doc(f))
            sms = merge(sms, s, lambda x: x['entity'])
            evts = merge(evts, e, lambda x: x['name'])
            cors = merge(cors, c, lambda x: (x['target'], x['action']))
    rules, cons, codes = [], [], []
    for f in (core('rules.md'), sl('04_rules.md')):
        if exists(f):
            r, c, v = parse_rules(Doc(f))
            rules = merge(rules, r, lambda x: x['id'])
            cons = merge(cons, c, lambda x: x['id'])
            codes = merge(codes, v, lambda x: x['id'])
    for f in (sl('03_flows.md'), sl('04_rules.md')):
        if exists(f): terms = merge(terms, parse_glossary(Doc(f)), lambda t: t['id'])

    if ents: data['entities'] = ents
    if rels: data['relations'] = rels
    if terms or codes: data['glossary'] = merge(terms, codes, lambda t: t['id'])
    if sms or evts or cors: data['flows'] = {'state_machines': sms, 'events': evts, 'corrections': cors}
    if rules or cons or codes:
        data['rules'] = {'rules': rules, 'conservation': cons, 'classification_values': codes}
    return data

FILES = [('cq', 'cq.yaml', 'competency_questions'), ('entities', 'entities.yaml', 'entities'),
         ('relations', 'relations.yaml', 'relations'), ('glossary', 'glossary.yaml', 'terms'),
         ('flows', 'flows.yaml', None), ('rules', 'rules.yaml', None)]

def write(root, data):
    out_dir = os.path.join(root, '.build')
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for key, fname, top in FILES:
        if key not in data: continue
        body = data[key] if top is None else {top: data[key]}
        with open(os.path.join(out_dir, fname), 'w', encoding='utf-8') as f:
            f.write('# 由 tools/md2build.py 從 Markdown 轉出，不要手改\n')
            yaml.safe_dump(body, f, allow_unicode=True, sort_keys=False)
        written.append(fname)
    return written

def main():
    args = [a for a in sys.argv[1:]]
    if not args or '--help' in args:
        print(__doc__); return 0
    root = '.'
    if '--root' in args:
        i = args.index('--root'); root = args[i + 1]; del args[i:i + 2]
    slice_name = args[0]
    if not os.path.isdir(os.path.join(root, 'slices', slice_name)):
        print(f'找不到 slices/{slice_name}/'); return 1
    data = build(root, slice_name)
    written = write(root, data)
    n = lambda k, sub=None: len((data.get(k) or {}).get(sub, []) if sub else data.get(k) or [])
    attrs = sum(len(e.get('attributes') or []) for e in data.get('entities') or [])
    new = sum(1 for e in data.get('entities') or [] if e.get('origin') == 'new')
    print(f"已寫出 .build/：{'、'.join(written) or '（沒有）'}")
    print(f"驗收問題 {n('cq')}；Entity {n('entities')}（本切片新增 {new}）、屬性 {attrs}；關係 {n('relations')}；"
          f"詞彙 {n('glossary')}；狀態機 {n('flows', 'state_machines')}、事件 {n('flows', 'events')}、"
          f"更正方式 {n('flows', 'corrections')}；規則 {n('rules', 'rules')}、守恆式 {n('rules', 'conservation')}、"
          f"分類值 {n('rules', 'classification_values')}")
    if warnings:
        print(f"\n提醒 {len(warnings)} 處（格式以外的寫法，沒有轉出）：")
        for path, no, msg in warnings:
            print(f"  {os.path.relpath(path, root)}:{no}　{msg}")
    if problems:
        print(f"\n看不懂或不合格式的列 {len(problems)} 處（請修正 Markdown）：")
        for path, no, msg in problems:
            print(f"  {os.path.relpath(path, root)}:{no}　{msg}")
        return 2
    print("\n沒有看不懂或不合格式的列。")
    return 0

if __name__ == '__main__':
    sys.exit(main())
