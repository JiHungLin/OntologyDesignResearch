"""切片首頁與總覽「在什麼狀態該顯示什麼」：用無頭 Chrome 打開真的網頁，檢查主畫面的標題與按鈕。
每個情境照一次實際踩過的問題（試跑 domain-trial、HR）造出對應的檔案與 session 紀錄。
執行：cd domain-design-web && python3 -m pytest tests -q（沒有 google-chrome 或 websockets 時跳過）。
"""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
CHROME = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
websockets = pytest.importorskip('websockets')
pytestmark = pytest.mark.skipif(not CHROME, reason='沒有 Chrome')

REVIEW = 'slices/demo/reviews/2026-10-27_02.md'
HEAD = '| 項目 | 內容 |\n|---|---|\n| 切片 | demo |\n| 狀態 | {status} |\n| 版本 | {version} |\n\n'


def _port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ---------- 造出切片的狀態 ----------

class Repo:
    def __init__(self, root):
        self.root = root
        shutil.copytree(os.path.join(HERE, 'fixture'), root)
        self.git('init', '-q')
        self.sessions = []

    def git(self, *a):
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd=self.root, capture_output=True, check=True)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), 'w', encoding='utf-8') as f:
            f.write(text)

    def step(self, slice_, fn, status, tag=True):
        """寫一個步驟檔的檔頭；已凍結的打 tag（tag=False 模擬凍結做到一半）。"""
        n = fn[:2]
        version = f'{slice_}/{n}-v1' if status == '已凍結' else ''
        p = f'slices/{slice_}/{fn}'
        body = open(self.path(p), encoding='utf-8').read() if os.path.exists(self.path(p)) else f'# {slice_} {fn}\n'
        title, _, rest = body.partition('\n')
        rest = rest.split('| 版本 |', 1)[-1].split('\n', 1)[-1] if '| 版本 |' in rest else rest
        self.write(p, f'{title}\n\n' + HEAD.replace('demo', slice_).format(status=status, version=version) + rest.lstrip('\n'))
        if status == '已凍結' and tag:
            self.git('add', '-A'); self.git('commit', '-qm', p, '--allow-empty'); self.git('tag', version)

    def frozen_until(self, slice_, n):
        for fn in ('01_scope.md', '02_entities.md', '03_flows.md', '04_rules.md', '05_mapping.md')[:n]:
            self.step(slice_, fn, '已凍結')

    def answer_review(self):
        t = open(self.path(REVIEW), encoding='utf-8').read()
        t = (t.replace('- 你的回答：\n', '- 你的回答：A\n').replace('` | |\n', '` | ✓ |\n').replace('| | |\n', '| 第 1 條 | 屬實 |\n')
             .replace('| ② | | | |', '| ② | 審查者甲 | 2026-10-27 | 通過 |').replace('- 預期結果：（由人填）', '- 預期結果：① 已取消；② 100 元')
             .replace('- 計算過程：（由人填，附檔案位置）', '- 計算過程：100 全退').replace('- 計算者：（不得是 AI 或被測系統）', '- 計算者：審查者甲'))
        self.write(REVIEW, t)

    def session(self, purpose, reply, slice_='demo', status='使用中', started='2026-10-28T10:00:00'):
        for s in self.sessions:
            if s['slice'] == slice_ and s['status'] == '使用中':
                s['status'] = '已結束'
        self.sessions.append({'id': f'sid-{len(self.sessions)}', 'slice': slice_, 'purpose': purpose, 'name': f'{slice_} {purpose}',
                              'started': started, 'last_used': started, 'status': status, 'handoff': '', 'turns': 1,
                              'compacted': False, 'last_ok': True, 'last_at': started, 'last_reply': reply})
        self.write('.domain-web/sessions.json', json.dumps(self.sessions, ensure_ascii=False))


# ---------- 開網頁讀畫面 ----------

class Browser:
    def __init__(self):
        self.dir = tempfile.mkdtemp()
        self.port = _port()
        self.p = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', f'--remote-debugging-port={self.port}',
                                   '--window-size=1280,1000', f'--user-data-dir={self.dir}', 'about:blank'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json'))
                self.ws = next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl']
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError('Chrome 沒有啟動')

    def run(self, url, js, wait='.hero, .celebrate'):
        async def go():
            async with websockets.connect(self.ws, max_size=2 ** 24) as ws:
                n = 0

                async def call(method, **params):
                    nonlocal n
                    n += 1
                    await ws.send(json.dumps({'id': n, 'method': method, 'params': params}))
                    while True:
                        m = json.loads(await ws.recv())
                        if m.get('id') == n:
                            return m
                await call('Page.navigate', url='about:blank')
                await call('Page.navigate', url=url)
                code = (f'(async()=>{{for(let i=0;i<100&&!document.querySelector({json.dumps(wait)});i++)'
                        f'await new Promise(r=>setTimeout(r,50));{js}}})()')
                r = await call('Runtime.evaluate', expression=code, awaitPromise=True, returnByValue=True)
                res = r['result']
                if 'exceptionDetails' in res:
                    raise AssertionError(res['exceptionDetails'])
                return res['result'].get('value')
        return asyncio.run(go())

    def close(self):
        self.p.terminate()
        self.p.wait()
        shutil.rmtree(self.dir, ignore_errors=True)


@pytest.fixture(scope='module')
def browser():
    b = Browser()
    yield b
    b.close()


@pytest.fixture
def repo(tmp_path):
    return Repo(str(tmp_path / 'repo'))


HERO = ("const h=document.querySelector('.hero, .celebrate');"
        "return {title:(h.querySelector('h1')||{}).innerText||'', text:h.innerText,"
        "buttons:[...h.querySelectorAll('button, a.btn')].map(b=>b.innerText.trim())}")


def page(browser, repo, route):
    port = _port()
    srv = subprocess.Popen([sys.executable, 'server.py', '--repo', repo.root, '--port', str(port)], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/api/project')
                break
            except Exception:
                time.sleep(0.1)
        return browser.run(f'http://127.0.0.1:{port}/#{route}', HERO)
    finally:
        srv.terminate()
        srv.wait()


def home(browser, repo):
    return page(browser, repo, '/s/demo')


# ---------- 情境 ----------

def test_review_unanswered(browser, repo):
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    h = home(browser, repo)
    assert h['buttons'], h


def test_review_answered_hand_to_ai(browser, repo):
    # 審查頁都填好、AI 還沒處理：交給 AI
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    h = home(browser, repo)
    assert '審查填好了' in h['title'] and '交給 AI 處理答案' in h['buttons'], h


def test_handled_can_freeze(browser, repo):
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    repo.session('審查 02', '審查頁都填好了，結論通過。\n\n下一步：請按凍結。')
    h = home(browser, repo)
    assert 'AI 處理完了' in h['title'] and h['buttons'][0].startswith('請 AI 凍結'), h


def test_handled_cannot_freeze_go_back(browser, repo):
    # domain-trial ⑥：AI 說不能凍結、要回頭修改 → 主按鈕是回頭修改，不是凍結
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    repo.session('審查 02', '這一輪不能凍結：問題 1 選 B，要回頭修改 ①。\n\n下一步：請 AI 依審查頁回頭修改。')
    h = home(browser, repo)
    assert '還不能凍結' in h['title'] and h['buttons'][0].startswith('請 AI 依審查頁回頭修改'), h


def test_handled_redo_step(browser, repo):
    # domain-trial ⑥：設計已改好、AI 說要重做這一步 → 主按鈕是重做，不是再回頭修改
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    repo.session('審查 02', '這次還不能凍結，設計已經改好了。\n\n下一步：請重做第 ② 步。')
    h = home(browser, repo)
    assert h['buttons'][0].startswith('請 AI 重做第 ② 步'), h


def test_after_go_back_session(browser, repo):
    # 回頭修改的 session 做完也算處理過，不會退回「交給 AI 處理答案」（domain-trial 審查 → 回頭修改 → 審查的循環）
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    repo.session('回頭修改', '設計都改好並凍結了，程式還沒改，還不能凍結。\n\n下一步：請在 ② 按「開始」重做。')
    h = home(browser, repo)
    assert '交給 AI 處理答案' not in h['buttons'] and h['buttons'][0].startswith('請 AI 重做第 ② 步'), h


def test_redo_stopped_halfway(browser, repo):
    # 依審查頁重做到一半停下（核准逾時）：主按鈕是繼續，不是再交一次審查頁
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '待檢查')
    repo.answer_review()
    repo.session('第 2 步', '核准卡片等了 30 分鐘沒有回應，先停在這裡。\n\n下一步：回到網頁時說「繼續」。')
    h = home(browser, repo)
    assert '重做到一半' in h['title'] and h['buttons'][0].startswith('請 AI 繼續第 ② 步'), h
    assert '交給 AI 處理答案' not in h['buttons'], h


def test_freezing_halfway(browser, repo):
    # 檔頭寫已凍結、還沒有 tag：凍結做到一半
    repo.frozen_until('demo', 1)
    repo.step('demo', '02_entities.md', '已凍結', tag=False)
    os.remove(repo.path(REVIEW))
    h = home(browser, repo)
    assert '凍結還沒做完' in h['title'] and h['buttons'][0].startswith('請 AI 把凍結做完'), h


def test_draft_shows_last_said(browser, repo):
    # HR hire-employee ⑥：上一個 session 說了下一步，首頁「還沒做完」要帶出來
    repo.frozen_until('demo', 5)
    repo.step('demo', '06_evidence/signoff.md', '草稿')
    os.remove(repo.path(REVIEW))
    repo.session('審查 02', '② 凍結好了。GC02 寫了「同 GC01」要補。\n\n下一步：回到 ⑥，跑之前暫停的簽核測試。')
    h = home(browser, repo)
    assert '第 ⑥ 步還沒做完' in h['title'] and 'AI 上次說' in h['text'] and h['buttons'][0].startswith('請 AI 繼續第 ⑥ 步'), h


def test_hub_prefers_review_waiting(browser, repo):
    # HR：demo 在做 ⑥（輪到 AI）、return-order 有審查頁等人作答 → 總覽先顯示輪到你的
    repo.frozen_until('demo', 5)
    repo.step('demo', '06_evidence/signoff.md', '草稿')
    os.makedirs(repo.path('slices/return-order/reviews'))
    shutil.move(repo.path(REVIEW), repo.path('slices/return-order/reviews/2026-10-27_02.md'))
    repo.write('slices/return-order/01_scope.md', '# return-order ①\n')
    repo.frozen_until('return-order', 1)
    shutil.copy(repo.path('slices/demo/02_entities.md'), repo.path('slices/return-order/02_entities.md'))
    repo.step('return-order', '02_entities.md', '待檢查')
    plan = open(repo.path('slices/PLAN.md'), encoding='utf-8').read()
    repo.write('slices/PLAN.md', plan.replace('| 狀態 | 討論中 |', '| 狀態 | 已同意 |'))
    h = page(browser, repo, '/')
    assert 'return-order' in h['text'] and '輪到你' in h['text'], h


def test_approval_card_keeps_typing(browser, repo):
    # HR：核准卡片在 AI 執行中被輪詢重畫，核准人輸入框一直失去焦點、字被清掉
    port = _port()
    srv = subprocess.Popen([sys.executable, 'server.py', '--repo', repo.root, '--port', str(port)], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/api/project'); break
            except Exception:
                time.sleep(0.1)
        r = browser.run(f'http://127.0.0.1:{port}/#/', """
          document.querySelector('.ai-btn').click(); await new Promise(r=>setTimeout(r,800));
          const m=await import('/static/js/ai.js'), c=await import('/static/js/core.js');
          const s={id:'x1',running:true,slice:'demo'};
          c.state.approvals.x1=[{id:'r1',tool:'Bash',input:{command:'docker compose up -d'}}];
          await m.renderAiNext(s);
          const w=document.querySelector('#apWho'); w.focus(); w.value='乙'; const f0=document.activeElement===w;
          await m.renderAiNext(s); await m.renderAiNext(s);
          c.state.approvals.x1.push({id:'r2',tool:'Bash',input:{command:'pytest'}}); await m.renderAiNext(s);
          const w2=document.querySelector('#apWho');
          return {same:w===w2, value:w2.value, focused:document.activeElement===w2, f0,
                  label:document.querySelector('.approve-card .label').innerText}""", wait='.ai-btn')
    finally:
        srv.terminate(); srv.wait()
    # 卡片沒被換掉（同一個輸入框）就不會失去焦點；無頭 Chrome 的分頁有時拿不到焦點，拿得到時再比一次
    assert r['same'] and r['value'] == '乙' and r['focused'] == r['f0'] and '還有 1 條' in r['label'], r


def test_nav_step6_in_progress(browser, repo):
    # HR hire-employee：⑥ 已經開始（簽核紀錄是草稿），左側不能顯示「設計完成」
    repo.frozen_until('demo', 5)
    os.remove(repo.path(REVIEW))
    port = _port()
    srv = subprocess.Popen([sys.executable, 'server.py', '--repo', repo.root, '--port', str(port)], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    nav = "return [...document.querySelectorAll('#navTree summary')].map(x=>x.innerText).find(t=>t.includes('demo'))"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/api/project'); break
            except Exception:
                time.sleep(0.1)
        before = browser.run(f'http://127.0.0.1:{port}/#/s/demo', nav, wait='#navTree summary')
        repo.step('demo', '06_evidence/signoff.md', '草稿')
        after = browser.run(f'http://127.0.0.1:{port}/#/s/demo', nav, wait='#navTree summary')
    finally:
        srv.terminate(); srv.wait()
    assert '設計完成' in before and '⑥ 驗證中' in after and '設計完成' not in after, (before, after)


def test_topic_in_header(browser, repo):
    # 主題決定後（切片地圖有領域）頂列與分頁標題用主題名稱，HR 與碳管理同時開兩個分頁才分得出來
    port = _port()
    srv = subprocess.Popen([sys.executable, 'server.py', '--repo', repo.root, '--port', str(port)], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    head = "return {brand:document.querySelector('.brand').innerText, title:document.title}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/api/project'); break
            except Exception:
                time.sleep(0.1)
        with_plan = browser.run(f'http://127.0.0.1:{port}/#/', head, wait='#navTree summary')
        os.remove(repo.path('slices/PLAN.md'))
        no_plan = browser.run(f'http://127.0.0.1:{port}/#/', head, wait='.hero, .celebrate, main section')
    finally:
        srv.terminate(); srv.wait()
    assert with_plan['brand'].startswith('銷售') and with_plan['title'] == '銷售｜Domain 設計', with_plan
    assert no_plan['brand'] == 'DOMAIN 設計' and no_plan['title'] == 'Domain 設計', no_plan


def test_background_results_keep_last_reply(browser, repo):
    # 碳管理：有背景子代理時一輪有好幾個 result，舊的中間回報在最後一起到，
    # 對話框最後顯示「第 2 輪核對在背景執行中」，看起來像 AI 還沒做完（其實已經結束、按鈕照最後的回覆）
    port = _port()
    srv = subprocess.Popen([sys.executable, 'server.py', '--repo', repo.root, '--port', str(port)], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/api/project'); break
            except Exception:
                time.sleep(0.1)
        r = browser.run(f'http://127.0.0.1:{port}/#/', """
          document.querySelector('.ai-btn').click(); await new Promise(r=>setTimeout(r,800));
          const m=await import('/static/js/ai.js');
          const d=(c)=>({tool:'Bash',input:{command:c}});
          [{kind:'me',text:'照審查頁修改'},
           {kind:'text',text:'第 2 輪核對在背景執行中，回報後我再收尾。'},
           {kind:'text',text:'做完了，送審頁是 reviews/x.md。'},
           {kind:'result',ok:true,text:'三個挑錯子代理還在跑。',denials:[]},
           {kind:'result',ok:true,text:'第 2 輪核對在背景執行中，回報後我再收尾。',denials:[d('python3 - <<EOF')]},
           {kind:'result',ok:true,text:'做完了，送審頁是 reviews/x.md。',denials:[d('python3 - <<EOF')]}].forEach(m.showEvent);
          const log=document.querySelector('#aiLog');
          return {texts:[...log.querySelectorAll(':scope > .t')].map(x=>x.innerText.trim()),
                  ends:log.querySelectorAll('.turn-end').length, denies:log.querySelectorAll('details.deny').length,
                  denyItems:log.querySelectorAll('details.deny li').length,
                  lastBefore:(log.querySelector('.turn-end').previousElementSibling||{}).innerText}""", wait='.ai-btn')
    finally:
        srv.terminate(); srv.wait()
    assert r['texts'][-1].startswith('做完了'), r
    assert r['ends'] == 1 and r['denies'] == 1 and r['denyItems'] == 1, r
