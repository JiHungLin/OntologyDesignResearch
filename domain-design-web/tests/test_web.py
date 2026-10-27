"""執行：cd domain-design-web && python3 -m pytest tests -q
用 tests/fixture 的副本測試，不動 fixture 本身。"""
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import kit  # noqa: E402
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
    assert [lv['state'] for lv in h['levels']][:3] == ['locked', 'review', 'locked']


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
