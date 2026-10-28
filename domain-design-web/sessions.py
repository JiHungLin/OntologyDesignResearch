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
    s = next((s for s in load() if s['slice'] == slice_ and s['status'] == '使用中'), None)
    return dict(s, running=busy(s['id'])) if s else None


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
        lines.append('- `slices/PLAN.md`、`slices/ENTITY_SKETCH.md`、`slices/CHANGELOG.md`（有的話）、`inputs/` 的檔案清單')
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


# ---- 呼叫 claude -p（在背景跑，事件寫進 .domain-web/logs/<id>.jsonl，網頁輪詢） ----

# 網頁沒有選項介面也不能互動核准：檔案修改自動接受（只限切片 repo），常用指令先允許；
# 其他會被擋下、顯示在網頁上，請人到 terminal 用 --resume 處理。可用環境變數 DOMAIN_WEB_ALLOWED（以逗號分隔）覆寫。
FETCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fetch_text.py')
ALLOWED = os.environ.get('DOMAIN_WEB_ALLOWED', ','.join([
    'Read', 'Edit', 'Write', 'Glob', 'Grep', 'Agent', 'Skill', 'WebSearch', 'WebFetch',
    'Bash(python3 tools/*)', 'Bash(python3 -I tools/*)', 'Bash(git status*)', 'Bash(git diff*)', 'Bash(git log*)',
    'Bash(git show*)', 'Bash(git tag*)', 'Bash(git add*)', 'Bash(git commit*)', 'Bash(git rev-parse*)',
    'Bash(ls*)', 'Bash(cp *)', 'Bash(mkdir *)', 'Bash(curl *)', 'Bash(date*)',
    # 唯讀的小工具；cd 放行是為了「cd <repo> && …」這種串接（每一段都要在清單內才會過）
    'Bash(cd *)', 'Bash(cat *)', 'Bash(head *)', 'Bash(tail *)', 'Bash(wc *)', 'Bash(sed -n *)', 'Bash(echo *)',
    'Bash(sort *)', 'Bash(diff *)', 'Bash(grep *)', 'Bash(pdftotext *)',
    # 下載公開來源並轉文字（網頁附的小工具，見 fetch_text.py）
    f'Bash(python3 {FETCH} *)'])).split(',')

PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_prompt.md')


def web_prompt():
    """附加在 claude -p 的系統提示；每次執行時讀 web_prompt.md，改了不用重開伺服器。"""
    with open(PROMPT_FILE, encoding='utf-8') as f:
        return f.read().replace('{FETCH}', FETCH)


def _command(s, message):
    cmd = [CLAUDE, '-p', message, '--output-format', 'stream-json', '--verbose',
           '--permission-mode', 'acceptEdits', '--append-system-prompt', web_prompt(), '--allowedTools', *ALLOWED]
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


_running = {}   # session id → asyncio.Task


def busy(sid):
    t = _running.get(sid)
    return bool(t and not t.done())


def running_slices():
    return {s['slice'] for s in load() if busy(s['id'])}


def _log(sid):
    return os.path.join(kit.repo(), '.domain-web', 'logs', f'{sid}.jsonl')


def _append(sid, ev):
    p = _log(sid)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    ev = dict(ev, at=_now())
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(ev, ensure_ascii=False) + '\n')


def events(sid, after=0):
    """這個 session 從第 after 個事件之後的事件（重新整理頁面也接得回來）。"""
    try:
        with open(_log(sid), encoding='utf-8') as f:
            evs = [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        evs = []
    return {'events': evs[after:], 'n': len(evs), 'running': busy(sid)}


def start(sid, message):
    """在背景送一則訊息。同一個 session 一次只送一個。"""
    if get(sid) is None:
        raise KeyError(sid)
    if busy(sid):
        raise RuntimeError('這個 session 上一個請求還沒結束')
    _append(sid, {'kind': 'me', 'text': message})
    _running[sid] = asyncio.get_running_loop().create_task(_run(sid, message))


async def _run(sid, message):
    s = get(sid)
    try:
        proc = await asyncio.create_subprocess_exec(
            *_command(s, message), cwd=kit.repo(),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=2 ** 24)
    except OSError as e:
        _append(sid, {'kind': 'error', 'text': f'無法執行 {CLAUDE}：{e}'})
        return
    _update(sid, turns=s['turns'] + 1, last_used=_now())
    compacted, result = False, None
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
            if o['kind'] == 'result':
                result = o
            _append(sid, o)
    err = (await proc.stderr.read()).decode('utf-8', 'replace').strip()
    code = await proc.wait()
    kw = {}
    if compacted:
        kw['compacted'] = True
    if result:
        kw.update(last_reply=result['text'], last_ok=result['ok'], last_at=_now())
    if kw:
        _update(sid, **kw)
    if code != 0:
        if s['turns'] == 0:
            _update(sid, turns=0)  # 沒有成功建立，下次仍用 --session-id
        _append(sid, {'kind': 'error', 'text': err or f'claude 結束碼 {code}'})
