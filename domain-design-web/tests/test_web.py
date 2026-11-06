"""執行：cd domain-design-web && python3 -m pytest tests -q
用 tests/fixture 的副本測試，不動 fixture 本身。"""
import os
import subprocess
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import kit  # noqa: E402
import project  # noqa: E402
import review  # noqa: E402
import sessions  # noqa: E402

REVIEW = 'slices/demo/reviews/2026-10-27_02.md'


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    shutil.copytree(os.path.join(HERE, 'fixture'), root)
    kit.set_repo(str(root))
    return root


@pytest.fixture
def client(repo):
    from fastapi.testclient import TestClient
    import server
    return TestClient(server.app)


def test_parse(repo):
    r = review.parse(str(repo / REVIEW))
    assert r['counts'] == {'questions': 2, 'questions_open': 2, 'confirms': 2, 'confirms_open': 2,
                           'spot_done': False, 'conclusion_done': False, 'cases': 1, 'cases_open': 1, 'open': 7}
    q = r['questions'][0]
    assert (q['n'], q['ref']) == (1, '② D-01')
    assert [(o['key'], o['recommended']) for o in q['options']] == [('A', True), ('B', False)]
    assert (q['options'][1]['summary'], q['options'][1]['outcome']) == ('刪除', '查不到取消紀錄')
    assert q['example'] == '小王 3/1 下單，3/2 取消'
    assert r['confirms'][1]['cells']['原文'] == '「| Order | customer（屬於客戶） | Customer | 1 |」'
    assert [m['key'] for m in r['meta']] == ['這輪審查的步驟', '起因']
    gc = r['cases'][0]
    assert gc['id'] == 'GC01' and gc['fields']['預期結果']['value'] == ''
    assert gc['fields']['要回答']['value'] == '① 訂單狀態；② 退款金額'
    assert r['problems'] == []


def test_answer_and_cells(repo):
    p = str(repo / REVIEW)
    r = review.parse(p)
    d = review.set_answer(p, r['questions'][0]['answer_line'], 'A', r['digest'])
    d = review.set_answer(p, r['questions'][1]['answer_line'], '只要一個帳單地址\n其他不限', d)
    d = review.set_cells(p, r['confirms'][1]['line'], {'確認': 'a|b'}, d)
    r2 = review.parse(p)
    assert [q['answer'] for q in r2['questions']] == ['A', '只要一個帳單地址 其他不限']
    assert r2['confirms'][1]['answer'] == 'a|b'
    assert r2['confirms'][1]['cells']['原文'] == r['confirms'][1]['cells']['原文']  # 其他欄的 \| 保留
    assert r2['counts']['questions_open'] == 0 and r2['counts']['confirms_open'] == 1


def test_rewrite_keeps_file(repo):
    p = str(repo / REVIEW)
    before = open(p, encoding='utf-8').read()
    r = review.parse(p)
    d = r['digest']
    for c in r['confirms']:
        d = review.set_cells(p, c['line'], {'確認': c['answer']}, d)
    assert open(p, encoding='utf-8').read() == before


def test_conflict_and_guard(repo):
    p = str(repo / REVIEW)
    r = review.parse(p)
    with pytest.raises(review.Conflict):
        review.set_answer(p, r['questions'][0]['answer_line'], 'A', 'stale')
    with pytest.raises(review.Conflict):  # 不是「你的回答」那一行
        review.set_answer(p, r['questions'][0]['line'], 'A', r['digest'])
    with pytest.raises(ValueError):  # AI 填的欄不能改
        review.set_cells(p, r['confirms'][0]['line'], {'原文': 'x'}, r['digest'])


def test_spot_row(repo):
    p = str(repo / REVIEW)
    r = review.parse(p)
    review.add_spot_row(p, r['digest'])
    assert len(review.parse(p)['spot']) == 2


def test_api(client):
    s = client.get('/api/status').json()
    assert s['slices'][0]['reviews'][0]['counts']['open'] == 7
    assert s['gitignored'] is False
    r = client.get('/api/review', params={'path': REVIEW}).json()
    assert r['slice'] == 'demo'
    res = client.post('/api/review/answer', json={'path': REVIEW, 'digest': r['digest'],
                                                  'line': r['questions'][0]['answer_line'], 'value': 'B'})
    assert res.status_code == 200
    res = client.post('/api/review/answer', json={'path': REVIEW, 'digest': r['digest'],
                                                  'line': r['questions'][1]['answer_line'], 'value': 'A'})
    assert res.status_code == 409  # 用舊的 digest


def test_case_field(repo):
    p = str(repo / REVIEW)
    r = review.parse(p)
    f = r['cases'][0]['fields']
    d = review.set_case_field(p, f['預期結果']['line'], '預期結果', '① 已取消\n② 100 元', r['digest'])
    d = review.set_case_field(p, review.parse(p)['cases'][0]['fields']['計算者']['line'], '計算者', '小林', d)
    r2 = review.parse(p)
    f2 = r2['cases'][0]['fields']
    assert f2['預期結果']['value'] == '- ① 已取消\n- ② 100 元' and f2['計算者']['value'] == '小林'
    assert r2['counts']['cases_open'] == 1  # 計算過程還沒填
    # 再改一次：多行換單行，原本的續行要一起拿掉
    review.set_case_field(p, f2['預期結果']['line'], '預期結果', '已取消，退 100', d)
    r3 = review.parse(p)
    assert r3['cases'][0]['fields']['預期結果']['value'] == '已取消，退 100'
    assert r3['cases'][0]['fields']['紙上推演']['value'] == '取消 → 已取消，退 100'
    with pytest.raises(ValueError):  # AI 填的欄不能改
        review.set_case_field(p, f['紙上推演']['line'], '紙上推演', 'x', r3['digest'])


def test_model_and_home(client):
    r = client.get('/api/review', params={'path': REVIEW}).json()
    m = r['model']
    assert [(e['id'], e['changed']) for e in m['entities']] == [('Order', True)]
    assert m['entities'][0]['definition'] == '客戶下的一筆訂單。'
    assert [a['name'] for a in m['entities'][0]['attrs']] == ['ordered_on', 'total']
    assert [x['id'] for x in m['refs']] == ['Customer']
    assert m['relations'][0]['changed'] and m['relations'][0]['label'] == '屬於客戶'
    assert [s['n'] for s in r['spot_items']] == [1, 2]
    h = client.get('/api/home', params={'slice': 'demo'}).json()
    assert h['current']['path'] == REVIEW
    assert [lv['state'] for lv in h['levels']][:3] == ['frozen', 'review', 'locked']
    assert h['next']['n'] == 2 and h['eq_open'] == 1


def test_file_paths(client):
    f = client.get('/api/file', params={'path': '02_entities.md', 'base': 'slices/demo'})
    assert f.status_code == 200 and f.json()['path'] == 'slices/demo/02_entities.md'
    assert client.get('/api/file', params={'path': '../../etc/passwd'}).status_code == 404
    assert client.get('/api/review', params={'path': 'slices/demo/02_entities.md'}).status_code == 404


def test_sessions(repo, client):
    h = client.get('/api/handoff', params={'slice': 'demo', 'purpose': '審查 02', 'review': REVIEW}).json()['text']
    assert 'EQ-001' in h and 'EQ-002' not in h and REVIEW in h
    a = client.post('/api/sessions', json={'slice': 'demo', 'purpose': '審查 02', 'handoff': h}).json()
    b = client.post('/api/sessions', json={'slice': 'demo', 'purpose': '凍結 02', 'handoff': h}).json()
    items = {s['id']: s for s in sessions.load()}
    assert items[a['id']]['status'] == '已結束' and items[b['id']]['status'] == '使用中'
    assert sessions.active('demo')['id'] == b['id']
    assert client.post('/api/sessions', json={'slice': 'nope', 'purpose': 'x', 'handoff': ''}).status_code == 400
    assert sessions._command(b, 'hi')[-4:] == ['--session-id', b['id'], '-n', 'demo 凍結 02']
    b['turns'] = 1
    assert sessions._command(b, 'hi')[-2:] == ['--resume', b['id']]


def test_summarize():
    assert sessions.summarize({'type': 'system', 'subtype': 'compact_boundary'}) == {'kind': 'compacted'}
    out = sessions.summarize({'type': 'assistant', 'message': {'content': [
        {'type': 'text', 'text': '好'}, {'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'ls'}}]}})
    assert [o['kind'] for o in out] == ['text', 'tool']
    res = sessions.summarize({'type': 'result', 'is_error': False, 'result': 'ok',
                              'permission_denials': [{'tool_name': 'Bash', 'tool_input': {'command': 'rm x'}}]})
    assert res['denials'][0]['tool'] == 'Bash'


# ---- 整個 domain：規劃與切片進度（2026-10-28） ----

def test_project(client):
    p = client.get('/api/project').json()
    assert p['plan']['status'] == '討論中' and not p['plan']['agreed']
    assert [x['切片'] for x in p['plan']['slices']] == ['demo', 'return-order']
    assert [x['狀態'] for x in p['plan']['inventory']] == ['推想草稿', '待提供']
    assert p['plan']['pending'][0]['編號'] == 'P-01'
    assert p['plan']['goals'][0].startswith('要做的系統與對象')
    assert [n['名詞'] for n in p['sketch']['nouns']] == ['Customer（客戶）', 'Order（訂單）']
    assert p['sketch']['unsure'] == ['客戶要不要分會員與訪客']
    d = p['drafts'][0]
    assert d['pending'] and d['unsure'] == '貨到付款是否常見'
    s = p['slices'][0]
    assert s['slice'] == 'demo' and s['next']['n'] == 2 and s['review']['path'] == REVIEW
    assert s['eq_open'] == 1 and s['eq_answered'] == 1
    assert 'slices/demo/01_scope.md' in s['files'] and p['core'] == {}


def test_file_binary(repo, client):
    (repo / 'inputs' / 'shared').mkdir(parents=True, exist_ok=True)
    (repo / 'inputs' / 'shared' / '薪資表.xlsx').write_bytes(b'PK\x03\x04')
    f = client.get('/api/file', params={'path': 'inputs/shared/薪資表.xlsx'}).json()
    assert f['binary'] and f['size'] == 4 and 'text' not in f


def test_accept_draft_and_inputs(repo, client):
    path = 'inputs/drafts/一般下單流程.md'
    assert client.post('/api/draft/accept', json={'path': path, 'who': 'AI'}).status_code == 400
    assert client.post('/api/draft/accept', json={'path': path, 'who': '小明', 'digest': 'stale'}).status_code == 409
    assert client.post('/api/draft/accept', json={'path': path, 'who': '小明'}).status_code == 200
    text = (repo / path).read_text(encoding='utf-8')
    assert '| 狀態 | 已接受為假設（小明，' in text and '| 最不確定的地方 | 貨到付款是否常見 |' in text
    assert client.post('/api/draft/accept', json={'path': path, 'who': '小明'}).status_code == 400  # 已接受過
    assert client.post('/api/draft/accept', json={'path': 'slices/PLAN.md', 'who': '小明'}).status_code == 400

    r = client.post('/api/inputs', json={'folder': 'shared', 'name': '退貨 案例', 'text': '上週有人退了一半'}).json()
    assert r['path'] == 'inputs/shared/退貨_案例.md'
    assert '使用者於對話中提供' in (repo / r['path']).read_text(encoding='utf-8')
    assert client.post('/api/inputs', json={'folder': 'shared', 'name': '退貨 案例', 'text': 'x'}).status_code == 409
    assert client.post('/api/inputs', json={'folder': '../x', 'name': 'a', 'text': 'x'}).status_code == 400
    up = client.post('/api/inputs', json={'folder': 'demo', 'name': '表單.xlsx', 'b64': 'AAEC'}).json()
    assert (repo / up['path']).read_bytes() == b'\x00\x01\x02'

    t = client.post('/api/topic', json={'fields': {'想做的系統': '訂單系統', '明確不做': '金流'}}).json()
    text = (repo / t['path']).read_text(encoding='utf-8')
    assert '- 想做的系統：訂單系統\n- 明確不做：金流' in text
    client.post('/api/topic', json={'fields': {'其他': '要支援退貨'}})
    text = (repo / t['path']).read_text(encoding='utf-8')
    assert '- 想做的系統：訂單系統' in text and '補充' in text and '- 其他：要支援退貨' in text


def test_background_job(repo):
    import time
    from fastapi.testclient import TestClient
    import server
    sessions.CLAUDE = os.path.join(HERE, 'fake_claude.py')
    with TestClient(server.app) as c:
        s = c.post('/api/sessions', json={'slice': '_plan', 'purpose': '規劃', 'handoff': 'x'}).json()
        assert c.post(f"/api/sessions/{s['id']}/send", json={'text': '/domain-plan 訂單'}).status_code == 200
        # 同一個 repo 一次只跑一件：另一個範圍的 session 這時送不出去
        other = c.post('/api/sessions', json={'slice': 'demo', 'purpose': '第 2 步', 'handoff': 'x'}).json()
        r = c.post(f"/api/sessions/{other['id']}/send", json={'text': '/domain-step 2 demo'})
        assert r.status_code == 409 and '一次只跑一件' in r.json()['detail']
        for _ in range(50):
            ev = c.get(f"/api/sessions/{s['id']}/events").json()
            if not ev['running'] and any(e['kind'] == 'result' for e in ev['events']):
                break
            time.sleep(0.1)
    assert [e['kind'] for e in ev['events']] == ['me', 'tool', 'text', 'result']
    assert c.get(f"/api/sessions/{s['id']}/events", params={'after': 3}).json()['events'][0]['kind'] == 'result'
    s2 = sessions.get(s['id'])
    assert s2['turns'] == 1 and s2['last_reply'].startswith('問題：要先做哪條？')
    assert '--permission-mode' in sessions._command(s2, 'x')


def test_init_repo(tmp_path):
    import server
    root = server.init_repo(str(tmp_path / 'new'))
    for f in ('CLAUDE.md', 'templates/PLAN.md', 'tools/lint.py', '.claude/skills/domain-plan/SKILL.md', 'slices/.gitkeep'):
        assert os.path.exists(os.path.join(root, f)), f
    assert '.domain-web/' in open(os.path.join(root, '.gitignore'), encoding='utf-8').read()
    log = subprocess.run(['git', 'log', '--format=%s'], cwd=root, capture_output=True, text=True).stdout.split('\n')
    assert log[0] == '建立設計 repo：複製設計工具包'
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True).stdout
    with pytest.raises(SystemExit):
        server.init_repo(root)


def test_fetch_text_html():
    import fetch_text
    p = fetch_text.Text('https://example.gov.tw/law/')
    p.feed('<html><script>x=1</script><h1>碳費收費辦法</h1><p>第 1 條 <a href="a.html">附表</a></p><table><tr><td>A</td><td>300</td></tr></table></html>')
    t = p.text()
    assert '碳費收費辦法' in t and 'x=1' not in t
    assert '附表 <https://example.gov.tw/law/a.html>' in t and '| A | 300' in t


def test_one_slice_at_a_time(repo, client):
    # fixture 的 demo 還在做（② 之後沒凍結），地圖上的 return-order 不能開
    r = client.post('/api/sessions', json={'slice': 'return-order', 'purpose': '第 1 步', 'handoff': 'x'})
    assert r.status_code == 409 and 'demo' in r.json()['detail']
    assert client.post('/api/sessions', json={'slice': 'demo', 'purpose': '第 2 步', 'handoff': 'x'}).status_code == 200
    assert client.post('/api/sessions', json={'slice': '_plan', 'purpose': '規劃', 'handoff': 'x'}).status_code == 200


def test_untouched_template_is_not_started(repo):
    # 開切片時複製過來、只換了 {{切片}} 的範本，不算「草稿」
    (repo / 'templates' / 'slice').mkdir(parents=True)
    tpl = '# {{切片}} ③ 流程\n\n| 項目 | 內容 |\n|---|---|\n| 狀態 | 草稿 |\n'
    (repo / 'templates' / 'slice' / '03_flows.md').write_text(tpl, encoding='utf-8')
    (repo / 'slices' / 'demo' / '03_flows.md').write_text(tpl.replace('{{切片}}', 'demo'), encoding='utf-8')
    st = {s['n']: s['status'] for s in project.steps('demo')}
    assert st[3] == '未開始'
    (repo / 'slices' / 'demo' / '03_flows.md').write_text(tpl.replace('{{切片}}', 'demo') + '\n開始寫了\n', encoding='utf-8')
    assert {s['n']: s['status'] for s in project.steps('demo')}[3] == '草稿'


def test_frozen_needs_tag(repo, client):
    # 檔頭寫「已凍結」但 tag 還沒打（凍結做到一半、AI 在等人回答）：算「凍結中」，首頁不能叫人開始下一關
    git = lambda *a: subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, check=True)
    git('init', '-q')
    git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x')
    assert project.steps('demo')[0]['status'] == '凍結中'
    h = client.get('/api/home', params={'slice': 'demo'}).json()
    assert h['next']['n'] == 1 and h['levels'][0]['state'] == 'freezing'
    git('tag', 'demo/01-v1')
    assert project.steps('demo')[0]['status'] == '已凍結'
    assert client.get('/api/home', params={'slice': 'demo'}).json()['levels'][0]['state'] == 'frozen'


def test_file_plan_short_name(client):
    # AI 常寫「PLAN.md:65」：從切片資料夾找不到時，也找 slices/ 底下
    f = client.get('/api/file', params={'path': 'PLAN.md', 'base': 'slices/demo'}).json()
    assert f['path'] == os.path.join('slices', 'PLAN.md')


def test_evidence_sections(repo):
    import evidence
    (repo / 'slices' / 'demo' / 'x.md').write_text('# x\n\n## 範圍\n- 做：\n  - 甲\n  - 乙\n- 不做（這版）：\n  - 丙\n- 模式：完整\n', encoding='utf-8')
    ev = evidence.find('✓：見 D-99', 'slices/demo/x.md', '範圍有寫「做」「不做」')
    assert [e['ref'] for e in ev] == ['「做」', '「不做」']
    assert ev[0]['text'] == '- 做：\n  - 甲\n  - 乙' and ev[1]['line'] == 7


def test_evidence_headings_and_english(repo):
    import evidence
    (repo / 'slices' / 'demo' / 'y.md').write_text('# y\n\n## 範圍\n- 做：登錄電費單\n\n## 交給第 ② 步的觀察\n- 每張帳單記 bill_id 與 ElectricityBill\n\n## 決定與理由\n- 無\n', encoding='utf-8')
    ev = evidence.find('✓：AI 檢查全文', 'slices/demo/y.md', '範圍與觀察都用業務語言寫，沒有英文識別名稱、表名或欄位名')
    assert [e['ref'] for e in ev] == ['網頁掃過這幾段的英文字', '範圍', '交給第 ② 步的觀察']
    assert 'bill_id' in ev[0]['text'] and 'ElectricityBill' in ev[0]['text'] and ev[1]['more']


def test_evidence_every_card_and_column(repo):
    import evidence
    (repo / 'slices' / 'demo' / 'z.md').write_text(
        '# z\n\n## 新增\n\n### Order（訂單）\n- 不是什麼：不是購物車\n- 主要屬性：金額\n\n### Customer（客戶）\n- 主要屬性：姓名\n\n'
        '## 草稿 User Story\n\n| 編號 | 故事 | 來源 |\n|---|---|---|\n| US-D01 | 下單 | AI |\n| US-D02 | 取消 | |\n\n'
        '## 反例處理\n\n| # | 反例 | 來源 |\n|---|---|---|\n| X-01 | 重複下單 | 領域實務 |\n', encoding='utf-8')
    ev = evidence.find('✓', 'slices/demo/z.md', '每張新卡都有「不是什麼」和「主要屬性」')
    assert ev[0]['ref'] == '「不是什麼」' and '1 張沒有' in ev[0]['text'] and 'Customer' in ev[0]['text']
    ev = evidence.find('✓', 'slices/demo/z.md', '每個草稿 User Story 都填了「來源」欄')
    assert [e['title'] for e in ev] == ['草稿 User Story'] and '1 列空白' in ev[0]['text']


def test_confirm_context(repo):
    import evidence
    d = repo / 'slices' / 'demo'
    (d / 'f.md').write_text('# f\n\n## 狀態機\n\n### Order（訂單）\n狀態：沒有狀態\n- 只記目前的值\n\n## 決定與理由\n\n'
                            '| # | 決定 | 理由 |\n|---|---|---|\n| D-01 | 不設狀態 | 由日期推出 |\n', encoding='utf-8')
    rv = str(d / 'reviews' / 'r.md')
    ctx = evidence.context('`f.md:5`、`f.md:7`、`f.md:13`', rv)
    assert [c['line'] for c in ctx] == [5, 13]   # 第 7 行在第 5 行那一段裡，不重複
    assert ctx[0]['title'] == 'Order（訂單）' and '只記目前的值' in ctx[0]['text']
    assert ctx[1]['fields'] == [['#', 'D-01'], ['決定', '不設狀態'], ['理由', '由日期推出']]


def test_flows_state_machines(repo):
    import flows
    (repo / 'slices' / 'demo' / '03_flows.md').write_text(
        '# f\n\n## 狀態機\n\n### Order（訂單）（歷史需求：需要軌跡，依 Q01）\n狀態：Open（處理中）→ Closed（已結案）\n終態：Closed\n\n'
        '| 從 | 到 | 觸發事件 | 誰可以做 | 前提條件 | 規則 |\n|---|---|---|---|---|---|\n'
        '| （無） | Open | PlaceOrder | 客戶 | — | |\n| Open | Closed | CloseOrder | 系統 | 已出貨 | |\n\n- 結案後不能改\n\n'
        '### Store（門市）（歷史需求：只需現況，依 Q02）\n狀態：沒有狀態，用開始營業日記\n\n'
        '## 事件\n\n| 事件 | 觸發來源 | 層 | 改變什麼 |\n|---|---|---|---|\n| PlaceOrder（下單） | 人的動作 | 發生 | 新增訂單 |\n', encoding='utf-8')
    f = flows.load('demo')
    order, store = f['machines']
    assert [s['label'] for s in order['states']] == ['處理中', '已結案'] and order['terminal'] == ['Closed']
    assert [(t['from'], t['to'], t['label']) for t in order['transitions']] == [('', 'Open', '下單'), ('Open', 'Closed', '')]
    assert order['notes'] == ['結案後不能改'] and order['history'] == '需要軌跡'
    assert not store['transitions'] and store['stateless'] == '沒有狀態，用開始營業日記'
    r = {'confirms': [{'line': 9, 'cells': {'在哪裡': '`03_flows.md:12`'}}]}
    flows.mark(f, r)
    assert r['confirms'][0]['machine'] == 'Order' and order['confirms'] == [9]


def test_core_view(repo, client):
    # 沒有 core/ 時回 empty；有的話名詞卡、關係、狀態機（含 [候選] 與出處）、規則表都讀得出來
    assert client.get('/api/core').json().get('empty')
    core = repo / 'core'
    core.mkdir()
    (core / 'entities.md').write_text(
        '# 共用核心：Entity\n\n### Site（據點） [候選]\n- 出處：demo（② @ demo/02-v1）\n- 層：domain\n- 定義：營運地點\n'
        '- 主要屬性：\n  - `name`（據點名稱）\n- 被引用：\n', encoding='utf-8')
    (core / 'relations.md').write_text(
        '| 從 | 關係 | 到 | 幾對幾 | 有無期間 | 為什麼 | 狀態 | 出處 | 被引用 |\n|---|---|---|---|---|---|---|---|---|\n'
        '| Site | partOf（屬於） | Organization | 1 | 無 | 理由 | [候選] | demo（② @ demo/02-v1） |  |\n', encoding='utf-8')
    (core / 'flows.md').write_text(
        '## 狀態機（demo）\n\n### Site（據點） [候選]（歷史需求：需要重建當時，依 demo:Q01）\n- 出處：demo（③ @ demo/03-v1）\n- 層：domain\n'
        '狀態：Open（營運中）、Closed（已結束）\n\n| 從 | 到 | 觸發事件 | 誰可以做 | 前提條件 | 規則 |\n|---|---|---|---|---|---|\n'
        '| （無） | Open | OpenSite | 使用者 | — | — |\n', encoding='utf-8')
    c = client.get('/api/core').json()
    e = c['entities'][0]
    assert (e['id'], e['label'], e['status']) == ('Site', '據點', '候選') and e['attrs'][0]['name'] == 'name'
    assert dict(e['fields'])['層'] == 'domain'
    assert c['relations'][0]['label'] == '屬於' and c['relations'][0]['status'] == '候選'
    sm = c['flows']['machines'][0]
    assert (sm['status'], sm['history'], sm['meta']['出處']) == ('候選', '需要重建當時', 'demo（③ @ demo/03-v1）')
    assert sm['notes'] == [] and sm['transitions'][0]['to'] == 'Open'


def test_golden_paper(repo):
    # 對答案：設計推出的答案在 06_evidence/golden_cases.md（AI 人填完後才推），[未執行] 或空的不算
    import server
    ev = repo / 'slices' / 'demo' / '06_evidence'
    ev.mkdir(parents=True, exist_ok=True)
    (ev / 'golden_cases.md').write_text(
        '## GC01 甲\n- 預期結果：（由人填）\n- 紙上推演：R01 算出 3 日\n  續行\n- 紙上判定：一致\n\n'
        '## GC02 乙\n- 紙上推演：\n- 紙上判定：[未執行]\n', encoding='utf-8')
    p = server._paper('demo')
    assert p == {'GC01': {'紙上推演': 'R01 算出 3 日\n續行', '紙上判定': '一致'}}


def test_readonly_hook():
    import readonly_hook as h
    root = ['/repo']
    assert h.read_only('cd /repo; for f in inputs/shared/*.md; do echo "=== $f"; cat -n "$f"; done', root)
    assert h.read_only("grep -n '^#' docs/01.md | awk -F: '$1<200'", root)
    assert h.read_only("sed -n '120,140p' docs/03.md | cat -n", root)
    assert h.read_only("grep -no 'EQ-0[0-9]' 03_flows.md | sort -t: -k3 | awk -F: '{print $3\" \"$1}'; git diff --stat; git log --oneline -- a.md", root)
    # domain-trial ④ 被擋的兩種：迴圈後的 2>/dev/null、串在後面的 python3 tools/lint.py
    assert h.read_only('ls inputs/shared; for f in inputs/shared/範圍釐清_*.md; do echo "== $f"; cat "$f"; done 2>/dev/null | head -80', root)
    # 碳管理送審前核對：多行、定義小函式一次查好幾處（本體照樣逐一檢查）
    assert h.read_only('cd /repo/slices/x && c(){ echo "== $1"; grep -nF -- "$3" "$1" | cut -d: -f1 | tr \'\\n\' \' \'; echo; }\nc 04_rules.md 38 \'(b) 還沒決定時\'\nc 05_mapping.md 224 \'R25\'', root)
    assert h.read_only('for f in a b\ndo cat $f; done', root)
    assert not h.read_only('c(){ rm -rf x; }; c', root)
    assert not h.read_only('c(){ echo hi; }; c /etc/passwd', root)
    assert not h.read_only('cat a\nrm x', root)
    assert h.read_only("grep -n -o 'EQ-[0-9]*' slices/x/04_rules.md | awk -F: '{print $1\": \"$NF}' | paste -sd' ' | tr '|' '\\n' | grep EQ; echo; python3 tools/lint.py x", root)
    assert h.read_only('python3 -I tools/lint.py x 2>&1 | tail -20', root)
    # domain-trial ⑤ 被擋的：cd 進切片後的 ../../、rev、<( )、絕對或相對路徑的 tools/*.py、變數
    assert h.read_only("cd /repo/slices/x && ls reviews; grep -n 'a' ../../inputs/r.md; wc -l *.md && git diff --stat", root)
    assert h.read_only("awk 'NR==68' slices/PLAN.md | rev | cut -c1-60 | rev", root)
    assert h.read_only("cd /repo/slices/x && diff <(sed -n '1,5p' a.md) <(sed -n '2,6p' b.md)", root)
    assert h.read_only('cd /repo/slices/x && python3 ../../tools/table.py 03_flows.md --row D-19 --col 提出', root)
    assert h.read_only('python3 /repo/tools/table.py /repo/slices/x/03_flows.md --row D-10', root)
    assert h.read_only('D=/repo; wc -l $D/slices/x/*.md; ls ${D}/inputs', root)
    for py in ("python3 -I - <<'EOF'\nprint(1)\nEOF", 'python3 -c "print(1)"', 'cd x && python3 - <<E'):
        assert h.INLINE_PY.search(py), py
    assert not h.INLINE_PY.search('python3 -I tools/lint.py electricity-emission')
    for bad in ('rm -rf slices', 'cat a.md > b.md', 'sed -i s/a/b/ x.md', "sed -n '1w out' a.md", 'cat /etc/passwd',
                'cat ../../x', 'echo $(rm x)', 'find . -delete', 'python3 -c 1', 'for f in *.md; do rm "$f"; done',
                "awk '{system(\"rm x\")}' a", 'git checkout .', 'git -c core.pager=sh log', 'git diff --output=x',
                'git grep -Ovim x', 'git push', 'python3 x.py', 'python3 /tmp/tools/a.py', 'ls; python3 ../tools/a.py',
                'cat a 2>/tmp/x', "cd /repo/slices/x && sed -n '1p' a.md > /tmp/a.txt", 'cd /repo/slices/x && cat ../../../etc/passwd',
                'cd /tmp && cat a', 'D=/etc; cat $D/passwd', 'cd /repo/slices && python3 ../x/tools/a.py', 'python3 /repo/tools/../x.py',
                'cd; cat .bashrc', "diff <(rm a) b"):
        assert not h.read_only(bad, root), bad


def test_review_steps():
    # 審查頁涵蓋的步驟：先看「這輪審查的步驟」（含回頭修改的步驟），沒有才看檔名；「05-2」的 2 是第 2 份
    import server
    meta = [{'key': '這輪審查的步驟', 'value': '⑤ schema.sql、api.yaml（依確認的對照表）；④ 04_rules.md（回頭修改）'}]
    assert server._review_steps('05-2', meta) == {4, 5}
    assert server._review_steps('05-2') == {5}
    assert server._review_steps('03-04') == {3, 4}
    assert server._review_steps('02-05') == {2, 3, 4, 5}


def test_approvals(repo, client, tmp_path):
    # 第 ⑥ 步的實作指令由網頁上的人逐條核准：approve_mcp.py 寫請求、等決定；網頁列出、寫回決定（docs/01 ⑥）
    import json as _json
    import threading
    s = sessions.create('leave-backfill', '第 6 步', '交接')
    d = sessions.approvals_dir(s['id'])
    env = dict(os.environ, DOMAIN_WEB_APPROVALS=d, DOMAIN_WEB_APPROVAL_WAIT='20')
    p = subprocess.Popen([sys.executable, os.path.join(HERE, '..', 'approve_mcp.py')], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, env=env)
    p.stdin.write(_json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
    p.stdin.write(_json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}) + '\n')
    p.stdin.write(_json.dumps({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'approve', 'arguments': {
        'tool_name': 'Bash', 'input': {'command': 'docker run postgres:15', 'description': '起資料庫'}}}}) + '\n')
    p.stdin.flush()
    assert _json.loads(p.stdout.readline())['id'] == 1
    assert _json.loads(p.stdout.readline())['result']['tools'][0]['name'] == 'approve'
    import time
    for _ in range(100):   # 機器忙時（另一個 AI 在跑）approve_mcp.py 寫出請求會慢一點
        pend = client.get(f"/api/sessions/{s['id']}/approvals").json()['pending']
        if pend: break
        time.sleep(0.1)
    assert pend and pend[0]['input']['command'] == 'docker run postgres:15'
    r = client.post(f"/api/sessions/{s['id']}/approvals/{pend[0]['id']}", json={'allow': False, 'message': '先不要用 docker', 'by': '甲'})
    assert r.status_code == 200
    out = _json.loads(_json.loads(p.stdout.readline())['result']['content'][0]['text'])
    assert out == {'behavior': 'deny', 'message': '先不要用 docker'}
    assert client.post(f"/api/sessions/{s['id']}/approvals/{pend[0]['id']}", json={'allow': True}).status_code == 409
    assert client.get(f"/api/sessions/{s['id']}/approvals").json()['pending'] == []
    ev = sessions.events(s['id'])['events']
    assert ev[-1]['kind'] == 'approval' and ev[-1]['by'] == '甲' and not ev[-1]['allow']
    p.stdin.close(); p.wait(timeout=5)
    # tools/run_evidence.py 在 tools/ 底下，但會執行實作指令：hook 一律交給人核准
    hp = subprocess.run([sys.executable, os.path.join(HERE, '..', 'readonly_hook.py')], capture_output=True, text=True,
                        input=_json.dumps({'tool_name': 'Bash', 'cwd': str(repo),
                                           'tool_input': {'command': 'python3 tools/run_evidence.py x golden -- pytest'}}))
    assert _json.loads(hp.stdout)['hookSpecificOutput']['permissionDecision'] == 'ask'
    cmd = sessions._command(dict(s, turns=0, name='n'), 'hi')
    assert cmd[cmd.index('--permission-prompt-tool') + 1] == 'mcp__web__approve'
    assert _json.loads(sessions._mcp(s['id']))['mcpServers']['web']['env']['DOMAIN_WEB_LOG'] == sessions._log(s['id'])
    # 等太久沒人按：當作不放行，也記進對話紀錄（網頁上看得到）
    env = dict(env, DOMAIN_WEB_APPROVAL_WAIT='1', DOMAIN_WEB_LOG=sessions._log(s['id']))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, '..', 'approve_mcp.py')], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, env=env)
    p.stdin.write(_json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'approve', 'arguments': {
        'tool_name': 'Bash', 'input': {'command': 'docker compose up'}}}}) + '\n')
    p.stdin.flush()
    out = _json.loads(_json.loads(p.stdout.readline())['result']['content'][0]['text'])
    assert out['behavior'] == 'deny'
    ev = sessions.events(s['id'])['events']
    assert ev[-1]['kind'] == 'approval' and ev[-1]['by'] == 'timeout' and not ev[-1]['allow'] and ev[-1]['brief'] == 'docker compose up'
    p.stdin.close(); p.wait(timeout=5)


def test_executor_cell(tmp_path):
    # ⑥ 的結論表多一欄「執行者」，簽名時和審查者、日期、結論一起寫回（docs/02「第 ⑥ 步的審查頁」）
    p = tmp_path / 'r.md'
    p.write_text('# r\n\n## 結論\n\n| 步驟 | 執行者 | 審查者（非產出者） | 日期 | 結論 |\n|---|---|---|---|---|\n| ⑥ | | | | |\n', encoding='utf-8')
    review.set_cells(str(p), 7, {'執行者': '甲', '審查者（非產出者）': '乙', '日期': '2026-11-05', '結論': '通過'})
    assert '| ⑥ | 甲 | 乙 | 2026-11-05 | 通過 |' in p.read_text(encoding='utf-8')
    with pytest.raises(ValueError):
        review.set_cells(str(p), 7, {'步驟': '⑤'})


def test_auto_mode_session_settings(repo):
    # 切片地圖「執行模式」是全自動（docs/01 0.2）：網頁的 session 改帶工具包的 tools/auto_hook.py，並設 DOMAIN_AUTO
    import sessions
    plan = os.path.join(str(repo), 'slices', 'PLAN.md')
    os.makedirs(os.path.join(str(repo), 'tools'), exist_ok=True)
    open(os.path.join(str(repo), 'tools', 'auto_hook.py'), 'w').close()
    assert not sessions.auto_mode() and 'readonly_hook' in sessions._settings()
    t = open(plan, encoding='utf-8').read().replace('| 狀態 | 討論中 |', '| 狀態 | 討論中 |\n| 執行模式 | 全自動 |', 1)
    open(plan, 'w', encoding='utf-8').write(t)
    assert sessions.auto_mode() and 'auto_hook.py' in sessions._settings() and '"matcher": "*"' in sessions._settings()
