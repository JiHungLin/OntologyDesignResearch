"""AI session 管理（設計見 互動元件盤點.md 第五節）。
記憶在檔案，不在 session：網頁顯示的狀態一律從 .md 算出；session 只放這一段工作的上下文。
登記表放在切片 repo 的 .domain-web/sessions.json（要加進 .gitignore，不是設計內容）。"""
import asyncio
import datetime
import json
import os
import re
import uuid

import kit

CLAUDE = os.environ.get('CLAUDE_BIN', 'claude')
_locks = {}


def _path():
    return os.path.join(kit.repo(), '.domain-web', 'sessions.json')


def _now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def load():
    try:
        with open(_path(), encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _store(items):
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    tmp = _path() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path())


def get(sid):
    return next((s for s in load() if s['id'] == sid), None)


def active(slice_):
    return next((s for s in load() if s['slice'] == slice_ and s['status'] == '使用中'), None)


def _update(sid, **kw):
    items = load()
    for s in items:
        if s['id'] == sid:
            s.update(kw)
    _store(items)


def create(slice_, purpose, handoff):
    """開新的 session：同一條切片原本使用中的改為「已結束」。真正啟動在第一次 send。"""
    items = load()
    for s in items:
        if s['slice'] == slice_ and s['status'] == '使用中':
            s['status'] = '已結束'
            s['ended'] = _now()
    s = {'id': str(uuid.uuid4()), 'slice': slice_, 'purpose': purpose,
         'name': f'{slice_} {purpose}', 'started': _now(), 'last_used': None,
         'status': '使用中', 'handoff': handoff, 'turns': 0, 'compacted': False}
    items.append(s)
    _store(items)
    return s


def end(sid):
    _update(sid, status='已結束', ended=_now())


def gitignored():
    """.domain-web/ 有沒有被切片 repo 的 .gitignore 排除。"""
    try:
        with open(os.path.join(kit.repo(), '.gitignore'), encoding='utf-8') as f:
            return any(l.strip().rstrip('/') in ('.domain-web', '/.domain-web') for l in f)
    except FileNotFoundError:
        return False


# ---- 交接提示：由檔案產生，不由舊對話摘要 ----

def handoff(slice_, purpose, review=None):
    lines = [f'這是 `{slice_}` 的新 session，用途：{purpose}。',
             '開始前先讀下面的檔案，回報狀態或人說過什麼一律以檔案為準，不憑記憶：']
    sdir = os.path.join(kit.repo(), 'slices', slice_)
    if slice_ == '_plan':
        lines.append('- `slices/PLAN.md`、`slices/CHANGELOG.md`')
    else:
        lines.append(f'- `slices/{slice_}/CHANGELOG.md`（最後幾筆）')
        if review:
            lines.append(f'- 這輪的審查頁 `{review}`')
        open_eq = _open_eqs(os.path.join(sdir, 'questions.md'))
        if open_eq:
            lines.append(f'- `slices/{slice_}/questions.md` 還沒回覆的專家問題：{"、".join(open_eq)}')
    lines.append('讀完後執行 /domain-status，用一句話說明現在的狀態與下一步，等我指示。')
    return '\n'.join(lines)


def _open_eqs(path):
    if not os.path.exists(path):
        return []
    mb = kit.md2build()
    out = []
    for _, _, header, rows in mb.Doc(path).tables():
        k = mb.col(header, '狀態')
        if k is None:
            continue
        out += [c[0] for _, c in rows if re.match(r'EQ-\d+', c[0]) and c[k].strip() != '已回覆']
    return out


# ---- 呼叫 claude -p ----

def _command(s, message):
    cmd = [CLAUDE, '-p', message, '--output-format', 'stream-json', '--verbose']
    if s['turns'] == 0:
        cmd += ['--session-id', s['id'], '-n', s['name']]
    else:
        cmd += ['--resume', s['id']]
    return cmd


def summarize(event):
    """把 stream-json 的一個事件轉成網頁要顯示的東西；不用顯示的回傳 None。"""
    t = event.get('type')
    if t == 'system' and event.get('subtype') == 'compact_boundary':
        return {'kind': 'compacted'}
    if t == 'assistant':
        out = []
        for c in event.get('message', {}).get('content', []):
            if c.get('type') == 'text' and c.get('text', '').strip():
                out.append({'kind': 'text', 'text': c['text'], 'sub': bool(event.get('parent_tool_use_id'))})
            elif c.get('type') == 'tool_use':
                inp = c.get('input', {})
                brief = inp.get('command') or inp.get('file_path') or inp.get('description') or inp.get('skill') or ''
                out.append({'kind': 'tool', 'name': c.get('name'), 'brief': str(brief)[:200],
                            'sub': bool(event.get('parent_tool_use_id'))})
        return out or None
    if t == 'result':
        return {'kind': 'result', 'ok': not event.get('is_error'), 'text': event.get('result', ''),
                'denials': [{'tool': d.get('tool_name'), 'input': d.get('tool_input')}
                            for d in event.get('permission_denials', [])],
                'cost': event.get('total_cost_usd')}
    return None


def busy(sid):
    lock = _locks.get(sid)
    return bool(lock and lock.locked())


async def send(sid, message):
    """送一則訊息，逐一產生要顯示的事件。同一個 session 一次只送一個。"""
    s = get(sid)
    if s is None:
        yield {'kind': 'error', 'text': '找不到這個 session'}
        return
    lock = _locks.setdefault(sid, asyncio.Lock())
    if lock.locked():
        yield {'kind': 'error', 'text': '這個 session 上一個請求還沒結束'}
        return
    async with lock:
        proc = await asyncio.create_subprocess_exec(
            *_command(s, message), cwd=kit.repo(),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=2 ** 24)
        _update(sid, turns=s['turns'] + 1, last_used=_now())
        compacted = False
        async for raw in proc.stdout:
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            out = summarize(ev)
            if out is None:
                continue
            for o in (out if isinstance(out, list) else [out]):
                if o['kind'] == 'compacted':
                    compacted = True
                yield o
        err = (await proc.stderr.read()).decode('utf-8', 'replace').strip()
        code = await proc.wait()
        if compacted:
            _update(sid, compacted=True)
        if code != 0:
            if s['turns'] == 0:
                _update(sid, turns=0)  # 沒有成功建立，下次仍用 --session-id
            yield {'kind': 'error', 'text': err or f'claude 結束碼 {code}'}
