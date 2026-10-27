#!/usr/bin/env python3
"""Domain 設計流程網頁（第一版：審查）。
用法：python3 server.py --repo <切片 repo> [--port 8765]
只綁 127.0.0.1，單人在本機使用。"""
import argparse
import json
import os
import re
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import kit
import model
import review
import sessions

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title='Domain 設計流程網頁')
app.mount('/static', StaticFiles(directory=os.path.join(HERE, 'static')), name='static')

REVIEW_NAME = re.compile(r'^(\d{4}-\d{2}-\d{2})_(.+)\.md$')


@app.get('/')
def index():
    return FileResponse(os.path.join(HERE, 'static', 'index.html'))


def _review_path(rel):
    p = kit.resolve(rel)
    if not p or os.sep + 'reviews' + os.sep not in p or not p.endswith('.md'):
        raise HTTPException(404, '找不到審查頁')
    return p


def _slice_of(path):
    parts = kit.rel(path).split(os.sep)
    return parts[1] if len(parts) > 2 and parts[0] == 'slices' else None


@app.get('/api/status')
def status():
    out = []
    for s in kit.slices():
        rdir = os.path.join(kit.repo(), 'slices', s, 'reviews')
        reviews = []
        if os.path.isdir(rdir):
            for n in sorted(os.listdir(rdir), reverse=True):
                m = REVIEW_NAME.match(n)
                if not m:
                    continue
                p = os.path.join(rdir, n)
                try:
                    r = review.parse(p)
                    reviews.append({'path': kit.rel(p), 'date': m.group(1), 'step': m.group(2),
                                    'title': r['title'], 'counts': r['counts']})
                except Exception as e:  # 看不懂的審查頁照樣列出，讓人知道
                    reviews.append({'path': kit.rel(p), 'date': m.group(1), 'step': m.group(2),
                                    'title': n, 'error': str(e)})
        out.append({'slice': s, 'reviews': reviews, 'session': sessions.active(s)})
    return {'repo': kit.repo(), 'slices': out, 'gitignored': sessions.gitignored()}


STEPS = [('01', '範圍', '01_scope.md'), ('02', '名詞', '02_entities.md'), ('03', '流程', '03_flows.md'),
         ('04', '規則', '04_rules.md'), ('05', '對照', '05_mapping.md'), ('06', '驗收', '06_evidence')]


def _review_steps(step):
    """審查頁檔名的步驟：「02」或「02-05」（合成一份，含中間各步）。"""
    nums = [int(x) for x in re.findall(r'\d+', step)]
    return set(range(nums[0], nums[-1] + 1)) if nums else set()


def _tags(slice_name):
    try:
        out = subprocess.run(['git', '-C', kit.repo(), 'tag', '-l', f'{slice_name}/*'],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return out.split()


@app.get('/api/home')
def home(slice: str):
    if slice not in kit.slices():
        raise HTTPException(404, f'沒有這條切片：{slice}')
    st = status()
    s = next(x for x in st['slices'] if x['slice'] == slice)
    current = next((r for r in s['reviews'] if r.get('counts') and r['counts']['open']), None)
    tags = _tags(slice)
    on = _review_steps(current['step']) if current else set()
    levels = []
    for code, name, fn in STEPS:
        n = int(code)
        frozen = sorted(t for t in tags if t.split('/', 1)[1].startswith(code + '-'))
        exists = os.path.exists(os.path.join(kit.repo(), 'slices', slice, fn))
        state = 'review' if n in on else 'frozen' if frozen else 'draft' if exists else 'locked'
        levels.append({'n': n, 'name': name, 'state': state, 'tag': frozen[-1] if frozen else ''})
    out = {'slice': slice, 'levels': levels, 'reviews': s['reviews'], 'current': None,
           'eq_open': len(sessions._open_eqs(os.path.join(kit.repo(), 'slices', slice, 'questions.md'))), 'session': s['session']}
    if current:
        r = get_review(current['path'])
        out['current'] = {'path': r['path'], 'title': r['title'], 'step': current['step'], 'counts': r['counts'],
                          'meta': r['meta'], 'model': bool(r.get('model'))}
    return out


def _spot_items(r, p):
    """抽查可挑的條目：「`02_entities.md` 完成標準表由上往下第 1、2、3 條」→ 取出那幾條的文字。"""
    m = re.search(r'`?([\w.-]+\.md)`?\s*完成標準表[^第]*第\s*([\d、，, ]+)\s*條', r['spot_hint'])
    if not m:
        return []
    f = kit.resolve(m.group(1), os.path.dirname(os.path.dirname(p)))
    if not f:
        return []
    mb = kit.md2build()
    rows = []
    for _, h3, header, trs in mb.Doc(f).tables():
        if header and header[0].strip() == '完成標準' and (h3 or '').startswith('完成標準'):
            rows = trs
    mb.problems.clear()
    out = []
    for k in re.findall(r'\d+', m.group(2)):
        i = int(k)
        if 0 < i <= len(rows):
            out.append({'n': i, 'text': rows[i - 1][1][0], 'self': rows[i - 1][1][-1], 'line': rows[i - 1][0],
                        'file': kit.rel(f)})
    return out


@app.get('/api/review')
def get_review(path: str):
    p = _review_path(path)
    r = review.parse(p)
    r['path'] = kit.rel(p)
    r['slice'] = _slice_of(p)
    r['spot_items'] = _spot_items(r, p)
    r['model'] = None
    if r['slice'] and 2 in _review_steps((REVIEW_NAME.match(os.path.basename(p)) or [None, None, ''])[2]):
        m = model.load(r['slice'])
        if m:
            r['model'] = model.mark_changed(m, r)
    return r


class Answer(BaseModel):
    path: str
    digest: str
    line: int
    value: str = ''
    cells: dict = {}


def _write(fn, a, *args):
    p = _review_path(a.path)
    try:
        return {'digest': fn(p, a.line, *args, expect_digest=a.digest)}
    except review.Conflict:
        raise HTTPException(409, '審查頁在你打開之後被改過（可能是 AI 正在修改），請重新載入')
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post('/api/review/answer')
def post_answer(a: Answer):
    return _write(review.set_answer, a, a.value)


@app.post('/api/review/cells')
def post_cells(a: Answer):
    return _write(review.set_cells, a, a.cells)


class CaseField(BaseModel):
    path: str
    digest: str
    line: int
    key: str
    value: str = ''


@app.post('/api/review/case')
def post_case(a: CaseField):
    return _write(review.set_case_field, a, a.key, a.value)


@app.post('/api/review/spot-row')
def post_spot_row(a: Answer):
    p = _review_path(a.path)
    try:
        return {'digest': review.add_spot_row(p, expect_digest=a.digest)}
    except review.Conflict:
        raise HTTPException(409, '審查頁在你打開之後被改過，請重新載入')


@app.get('/api/file')
def get_file(path: str, base: str = ''):
    """查閱檔案（唯讀）。base 是審查頁所在的切片資料夾，用來解析「02_entities.md:150」這種相對路徑。"""
    p = kit.resolve(path, os.path.join(kit.repo(), base) if base else None)
    if not p:
        raise HTTPException(404, f'找不到 {path}')
    with open(p, encoding='utf-8', errors='replace') as f:
        return {'path': kit.rel(p), 'text': f.read()}


# ---- AI session ----

@app.get('/api/sessions')
def list_sessions():
    return {'sessions': sessions.load(), 'gitignored': sessions.gitignored()}


@app.get('/api/handoff')
def get_handoff(slice: str, purpose: str, review: str = ''):
    return {'text': sessions.handoff(slice, purpose, review or None)}


class NewSession(BaseModel):
    slice: str
    purpose: str
    handoff: str


@app.post('/api/sessions')
def new_session(n: NewSession):
    if n.slice != '_plan' and n.slice not in kit.slices():
        raise HTTPException(400, f'沒有這條切片：{n.slice}')
    return sessions.create(n.slice, n.purpose, n.handoff)


@app.post('/api/sessions/{sid}/end')
def end_session(sid: str):
    sessions.end(sid)
    return {'ok': True}


class Message(BaseModel):
    text: str


@app.post('/api/sessions/{sid}/send')
async def send(sid: str, m: Message):
    if sessions.get(sid) is None:
        raise HTTPException(404, '找不到這個 session')
    if sessions.busy(sid):
        raise HTTPException(409, '這個 session 上一個請求還沒結束')

    async def stream():
        async for ev in sessions.send(sid, m.text):
            yield json.dumps(ev, ensure_ascii=False) + '\n'
    return StreamingResponse(stream(), media_type='application/x-ndjson')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default=os.environ.get('DOMAIN_REPO', os.getcwd()), help='切片 repo（工具包攤平在根目錄）')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    kit.set_repo(a.repo)
    if not os.path.isdir(os.path.join(kit.repo(), 'slices')):
        ap.error(f'{kit.repo()} 底下沒有 slices/，不是切片 repo')
    import uvicorn
    print(f'切片 repo：{kit.repo()}\n打開 http://127.0.0.1:{a.port}/')
    uvicorn.run(app, host='127.0.0.1', port=a.port, log_level='warning')


if __name__ == '__main__':
    main()
