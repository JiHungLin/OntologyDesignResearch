#!/usr/bin/env python3
"""Domain 設計流程網頁：從主題草案、規劃、開切片到每一步的審查與凍結。
用法：python3 server.py --repo <設計 repo> [--port 8765]
      python3 server.py --repo <空資料夾> --init   # 建立新的設計 repo（複製工具包、git init）
只綁 127.0.0.1，單人在本機使用。"""
import argparse
import base64
import os
import re
import shutil
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import kit
import model
import project
import review
import sessions

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title='Domain 設計流程網頁')
app.mount('/static', StaticFiles(directory=os.path.join(HERE, 'static')), name='static')

TEXT_EXT = {'.md', '.txt', '.yaml', '.yml', '.json', '.js', '.csv', '.py', ''}
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
    on = _review_steps(current['step']) if current else set()
    steps = project.steps(slice)
    levels = []
    for x in steps:
        state = ('review' if x['n'] in on else 'frozen' if x['status'].startswith('已凍結')
                 else 'wait' if x['status'] == '待檢查' else 'draft' if x['status'] != '未開始' else 'locked')
        levels.append({'n': x['n'], 'name': x['name'], 'state': state, 'status': x['status'], 'tag': x['version']})
    nxt = project.next_step(steps)
    eqs = project.eqs(slice)
    out = {'slice': slice, 'levels': levels, 'reviews': s['reviews'], 'current': None,
           'next': nxt, 'eqs': eqs, 'eq_open': len([e for e in eqs if e.get('狀態') != '已回覆']),
           'session': s['session']}
    if current:
        r = get_review(current['path'])
        out['current'] = {'path': r['path'], 'title': r['title'], 'step': current['step'], 'counts': r['counts'],
                          'meta': r['meta'], 'model': bool(r.get('model'))}
    return out


# ---- 整個 domain：主題草案 → 規劃 → 切片 ----

@app.get('/api/project')
def get_project():
    p = project.plan()
    slices = []
    for sl in kit.slices():
        steps = project.steps(sl)
        st = next((x for x in status()['slices'] if x['slice'] == sl), {})
        cur = next((r for r in st.get('reviews', []) if r.get('counts') and r['counts']['open']), None)
        eqs = project.eqs(sl)
        slices.append({'slice': sl, 'steps': steps, 'next': project.next_step(steps), 'review': cur,
                       'eq_open': len([e for e in eqs if e.get('狀態') != '已回覆']),
                       'eq_answered': len([e for e in eqs if e.get('狀態') == '已回覆' and not e.get('處理')]),
                       'session': sessions.active(sl), 'files': project.slice_files(sl)})
    return {'repo': kit.repo(), 'gitignored': sessions.gitignored(), 'topic': project.topic(),
            'plan': p, 'sketch': project.sketch(), 'drafts': project.drafts(), 'inputs': project.inputs(),
            'core': project.files_under('core'),
            'slices': slices, 'plan_session': sessions.active('_plan')}


class Topic(BaseModel):
    fields: dict


@app.post('/api/topic')
def post_topic(t: Topic):
    try:
        return {'path': project.write_topic({k: str(v) for k, v in t.fields.items()})}
    except ValueError as e:
        raise HTTPException(400, str(e))


class NewInput(BaseModel):
    folder: str = 'shared'
    name: str
    text: str = ''
    b64: str = ''


@app.post('/api/inputs')
def post_input(n: NewInput):
    try:
        if n.b64:
            return {'path': project.add_upload(n.folder, n.name, base64.b64decode(n.b64))}
        if not n.text.strip():
            raise ValueError('內容是空的')
        return {'path': project.add_input(n.folder, n.name, n.text)}
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


class Accept(BaseModel):
    path: str
    who: str
    digest: str = ''


@app.post('/api/draft/accept')
def post_accept(a: Accept):
    if not a.who.strip() or re.fullmatch(r'(?i)ai|claude', a.who.strip()):
        raise HTTPException(400, '接受者要寫人的名字')
    try:
        return {'digest': project.accept_draft(a.path, a.who.strip(), a.digest or None)}
    except review.Conflict:
        raise HTTPException(409, '草稿在你打開之後被改過，請重新載入')
    except ValueError as e:
        raise HTTPException(400, str(e))


class Asked(BaseModel):
    slice: str
    line: int
    digest: str = ''


@app.post('/api/eq/asked')
def post_asked(a: Asked):
    if a.slice not in kit.slices():
        raise HTTPException(404, f'沒有這條切片：{a.slice}')
    try:
        return {'digest': project.mark_asked(a.slice, a.line, a.digest or None)}
    except review.Conflict:
        raise HTTPException(409, 'questions.md 在你打開之後被改過，請重新載入')
    except ValueError as e:
        raise HTTPException(400, str(e))


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
    if os.path.splitext(p)[1].lower() not in TEXT_EXT:
        return {'path': kit.rel(p), 'binary': True, 'size': os.path.getsize(p)}
    with open(p, encoding='utf-8', errors='replace') as f:
        text = f.read()
    return {'path': kit.rel(p), 'text': text, 'digest': review.digest(text)}


# ---- AI session ----

@app.get('/api/sessions')
def list_sessions():
    items = [dict(s, running=sessions.busy(s['id'])) for s in sessions.load()]
    return {'sessions': items, 'gitignored': sessions.gitignored()}


@app.get('/api/handoff')
def get_handoff(slice: str, purpose: str, review: str = ''):
    return {'text': sessions.handoff(slice, purpose, review or None)}


class NewSession(BaseModel):
    slice: str
    purpose: str
    handoff: str


@app.post('/api/sessions')
def new_session(n: NewSession):
    planned = [x.get('切片', '') for x in (project.plan() or {}).get('slices', [])]
    if n.slice != '_plan' and n.slice not in kit.slices() and n.slice not in planned:
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
    """在背景交給 AI；進度用 /events 取（重新整理頁面也接得回來）。"""
    try:
        sessions.start(sid, m.text)
    except KeyError:
        raise HTTPException(404, '找不到這個 session')
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {'ok': True}


@app.get('/api/sessions/{sid}/events')
def get_events(sid: str, after: int = 0):
    if sessions.get(sid) is None:
        raise HTTPException(404, '找不到這個 session')
    return sessions.events(sid, after)


KIT = os.path.join(HERE, '..', 'domain-design-kit')


def init_repo(path):
    """建立新的設計 repo：複製工具包的檔案（照 CLAUDE.md 同步工具包的清單）、建立 slices/ 與 inputs/、git init、初始 commit。"""
    path = os.path.realpath(path)
    if os.path.isdir(path) and [n for n in os.listdir(path) if not n.startswith('.')]:
        raise SystemExit(f'{path} 不是空的資料夾')
    files = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '--', 'CLAUDE.md', 'README.md', '.gitignore',
                            'docs', 'templates', 'tools', '.claude'], cwd=KIT, capture_output=True, text=True, check=True).stdout.split('\n')
    for f in filter(None, files):
        dst = os.path.join(path, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(KIT, f), dst)
    for d in ('slices', 'inputs/shared', 'inputs/research', 'inputs/drafts'):
        os.makedirs(os.path.join(path, d), exist_ok=True)
        open(os.path.join(path, d, '.gitkeep'), 'a').close()
    with open(os.path.join(path, '.gitignore'), 'a', encoding='utf-8') as f:
        f.write('\n# 流程網頁的 AI session 登記表與紀錄（不是設計內容）\n.domain-web/\n')
    subprocess.run(['git', 'init', '-q'], cwd=path, check=True)
    # 初始 commit：之後凍結打 tag、AI commit 都有起點。沒設定 git 使用者時只提醒，不中斷
    subprocess.run(['git', 'add', '-A'], cwd=path, check=True)
    r = subprocess.run(['git', 'commit', '-q', '-m', '建立設計 repo：複製設計工具包'], cwd=path, capture_output=True, text=True)
    if r.returncode:
        print(f'初始 commit 沒做成（{(r.stderr or r.stdout).strip()}）；設定好 git 使用者後自己 commit 一次')
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default=os.environ.get('DOMAIN_REPO', os.getcwd()), help='切片 repo（工具包攤平在根目錄）')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--init', action='store_true', help='在 --repo 指定的空資料夾建立新的設計 repo')
    a = ap.parse_args()
    if a.init:
        print(f'已建立設計 repo：{init_repo(a.repo)}')
    kit.set_repo(a.repo)
    if not os.path.isdir(os.path.join(kit.repo(), 'slices')) and not os.path.isdir(os.path.join(kit.repo(), 'templates')):
        ap.error(f'{kit.repo()} 不是設計 repo（沒有 slices/ 也沒有 templates/）；新的 domain 請加 --init')
    import uvicorn
    print(f'切片 repo：{kit.repo()}\n打開 http://127.0.0.1:{a.port}/')
    uvicorn.run(app, host='127.0.0.1', port=a.port, log_level='warning')


if __name__ == '__main__':
    main()
