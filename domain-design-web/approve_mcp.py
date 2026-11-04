"""網頁 AI（claude -p）的權限核准：當作 --permission-prompt-tool 的 MCP 伺服器（stdio）。

允許清單之外、hook 沒有直接拒絕的指令（例：第 ⑥ 步的 docker、pytest、tools/run_evidence.py），
claude 會呼叫這裡的 approve。這裡把請求寫成 <DOMAIN_WEB_APPROVALS>/<請求>.json，等網頁寫回
<請求>.decision.json（人按「放行」或「不放行」），再把結果回給 claude。等太久就當作不放行。
沒有網頁時這個檔案用不到：終端機的 Claude Code 自己會問人（docs/01 ⑥「實作指令與執行紀錄」）。
"""
import json
import os
import sys
import threading
import time
import uuid

DIR = os.environ.get('DOMAIN_WEB_APPROVALS', '')
WAIT = int(os.environ.get('DOMAIN_WEB_APPROVAL_WAIT', '1800'))   # 秒
_out = threading.Lock()


def send(msg):
    with _out:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
        sys.stdout.flush()


def decide(args):
    """寫出請求、等網頁的決定；回傳 permission-prompt-tool 要的 {behavior, …}。"""
    rid = time.strftime('%Y%m%d%H%M%S') + '-' + uuid.uuid4().hex[:6]
    req = {'id': rid, 'tool': args.get('tool_name', ''), 'input': args.get('input', {}),
           'tool_use_id': args.get('tool_use_id', ''), 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, rid + '.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(req, f, ensure_ascii=False)
    os.replace(path + '.tmp', path)
    dpath = os.path.join(DIR, rid + '.decision.json')
    end = time.time() + WAIT
    while time.time() < end:
        if os.path.exists(dpath):
            try:
                with open(dpath, encoding='utf-8') as f:
                    d = json.load(f)
                break
            except (OSError, ValueError):
                pass
        time.sleep(0.5)
    else:
        d = {'behavior': 'deny', 'message': f'網頁上等了 {WAIT // 60} 分鐘沒有人核准，當作不放行。'}
        with open(dpath, 'w', encoding='utf-8') as f:
            json.dump(dict(d, by='timeout'), f, ensure_ascii=False)
    if d.get('behavior') == 'allow':
        return {'behavior': 'allow', 'updatedInput': req['input']}
    return {'behavior': 'deny', 'message': d.get('message') or '人在網頁上選了不放行。'}


def handle(msg):
    mid, method = msg.get('id'), msg.get('method')
    if method == 'initialize':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {
            'protocolVersion': msg.get('params', {}).get('protocolVersion', '2024-11-05'),
            'capabilities': {'tools': {}}, 'serverInfo': {'name': 'domain-web-approve', 'version': '1'}}})
    elif method == 'tools/list':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [{
            'name': 'approve', 'description': '把要執行的指令交給網頁上的人核准（放行或不放行）。',
            'inputSchema': {'type': 'object', 'properties': {
                'tool_name': {'type': 'string'}, 'input': {'type': 'object'}, 'tool_use_id': {'type': 'string'}},
                'required': ['tool_name', 'input']}}]}})
    elif method == 'tools/call':
        def work():
            try:
                r = decide(msg.get('params', {}).get('arguments', {}))
                send({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': json.dumps(r, ensure_ascii=False)}]}})
            except Exception as e:   # 出錯就當作不放行，不讓 claude 卡住
                r = {'behavior': 'deny', 'message': f'網頁核准出錯：{e}'}
                send({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': json.dumps(r, ensure_ascii=False)}]}})
        threading.Thread(target=work, daemon=True).start()
    elif method == 'ping':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
    elif mid is not None:
        send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'不支援 {method}'}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except ValueError:
            continue


if __name__ == '__main__':
    main()
