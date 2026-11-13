#!/usr/bin/env python3
"""全自動模式的 PreToolUse hook（docs/01 0.2「全自動模式」，先試用）。

只在環境變數 DOMAIN_AUTO=1 時作用（tools/auto_run.py 或網頁的全自動 session 設定），其他時候不表示意見。
作用時：每個工具呼叫記一筆到 <repo>/.domain-auto/commands.jsonl（時間、工具、指令或檔案、放行或擋下、理由），
不在禁止清單的直接放行（取代逐條核准）；碰到禁止清單就擋下，理由告訴 AI 停下來、在回報寫「全自動：需要人」。

禁止清單：
- git push；sudo、su
- 碰新專案 repo 以外的家目錄（/home/…、~、$HOME）；寫入、刪除 repo 與 /tmp 以外的絕對路徑
- docker 掛 docker.sock、--privileged、host 網路或 PID、掛 repo 以外的主機路徑
- Write、Edit 到 repo 與 /tmp 以外的檔案；Read、Grep、Glob 讀 repo 以外的家目錄

repo 是 DOMAIN_AUTO_REPO，沒有就用 hook 輸入的 cwd。
"""
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone

WRITE_CMDS = {'rm', 'rmdir', 'mv', 'cp', 'chmod', 'chown', 'tee', 'dd', 'truncate', 'ln', 'install', 'touch', 'mkdir'}
FILE_TOOLS = {'Write', 'Edit', 'MultiEdit', 'NotebookEdit'}
READ_TOOLS = {'Read', 'Glob', 'Grep'}


def inside(path, roots):
    p = os.path.realpath(os.path.expanduser(path))
    return any(p == r or p.startswith(r.rstrip('/') + '/') for r in roots)


def session_dir(repo):
    """Claude Code 為這個 repo 存的 session 資料（太長的工具輸出存成 tool-results/*.txt 再讓 AI 讀）：~/.claude/projects/<repo 路徑把 / 換成 ->。只能讀。"""
    return os.path.join(os.path.realpath(os.path.expanduser('~')), '.claude', 'projects', re.sub(r'[^A-Za-z0-9]', '-', repo))


def bash_reason(cmd, repo):
    """違反禁止清單時回傳理由，沒有就回傳 None。"""
    ok_roots = [repo, '/tmp']
    if re.search(r'\bgit\s+(?:-\S+\s+)*push\b', cmd):
        return 'git push：全自動模式不推到遠端（push 只在人要求時做）'
    if re.search(r'(^|[;&|(\s])(sudo|su)(\s|$)', cmd):
        return 'sudo／su：全自動模式不用管理者權限'
    if 'docker' in cmd:
        if 'docker.sock' in cmd:
            return 'docker.sock：掛上它等於能控制主機的 docker'
        if re.search(r'--privileged|--(net|network)[= ]host|--pid[= ]host|--cap-add', cmd):
            return 'docker 的 privileged、host 網路或 PID、cap-add：驗證環境不和主機共用（docs/01 ⑥「驗證環境」）'
        for m in re.finditer(r'(?:-v|--volume|--mount)[= ](\S+)', cmd):
            spec = m.group(1)
            src = spec.split(':', 1)[0] if not spec.startswith('type=') else (re.search(r'(?:source|src)=([^,]+)', spec) or [None, ''])[1]
            if src.startswith(('/', '~', '$HOME')) and not inside(src.replace('$HOME', '~'), [repo]):
                return f'docker 掛載 repo 以外的主機路徑 {src}'
    try:
        tokens = shlex.split(cmd.replace('\n', ' ; '), posix=True)
    except ValueError:
        tokens = cmd.split()
    for t in tokens:
        for p in re.findall(r'(?:^|=)((?:~|\$HOME|/home)[^\s:;|&>]*)', t):
            if not inside(p.replace('$HOME', '~'), [repo, session_dir(repo)]):
                return f'{p}：全自動模式不碰新專案 repo 以外的家目錄（其他 repo、設定檔、機密）'
    # 寫入或刪除 repo 與 /tmp 以外的絕對路徑（含 > 重新導向）
    for seg in re.split(r'[;&|\n]+', cmd):
        words = seg.split()
        if words and os.path.basename(words[0]) in WRITE_CMDS:
            for w in words[1:]:
                if w.startswith('/') and not inside(w, ok_roots):
                    return f'{words[0]} {w}：全自動模式不寫入、不刪除 repo 與 /tmp 以外的路徑'
        for m in re.finditer(r'>{1,2}\s*(/\S+)', seg):
            if m.group(1) != '/dev/null' and not inside(m.group(1), ok_roots):
                return f'寫入 {m.group(1)}：全自動模式不寫入 repo 與 /tmp 以外的路徑'
    return None


def decide(data, repo):
    tool, ti = data.get('tool_name', ''), data.get('tool_input') or {}
    if tool == 'Bash':
        return bash_reason(ti.get('command', ''), repo), ti.get('command', '')
    if tool in FILE_TOOLS:
        path = ti.get('file_path') or ti.get('notebook_path') or ''
        if path and not inside(path, [repo, '/tmp']):
            return f'{tool} {path}：全自動模式不改 repo 與 /tmp 以外的檔案', path
        return None, path
    if tool in READ_TOOLS:
        path = ti.get('file_path') or ti.get('path') or ''
        home = os.path.realpath(os.path.expanduser('~'))
        if path and inside(path, [home]) and not inside(path, [repo, session_dir(repo)]):
            return f'{tool} {path}：全自動模式不讀新專案 repo 以外的家目錄', path
        return None, path
    return None, json.dumps(ti, ensure_ascii=False)[:200]


def main():
    if os.environ.get('DOMAIN_AUTO') != '1':
        return
    data = json.load(sys.stdin)
    repo = os.path.realpath(os.environ.get('DOMAIN_AUTO_REPO') or data.get('cwd') or os.getcwd())
    reason, what = decide(data, repo)
    log = os.path.join(repo, '.domain-auto', 'commands.jsonl')
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'session': data.get('session_id', ''),
                                'tool': data.get('tool_name', ''), 'what': what, 'by': 'auto',
                                'allow': reason is None, 'reason': reason or ''}, ensure_ascii=False) + '\n')
    except OSError:
        pass
    if reason:
        out = {'permissionDecision': 'deny',
               'permissionDecisionReason': f'全自動模式的禁止清單：{reason}。不要換別的方法繞過；停下來，在回報最後一行寫「全自動：需要人（{reason}）」。'}
    else:
        out = {'permissionDecision': 'allow', 'permissionDecisionReason': '全自動模式：放行並記錄（.domain-auto/commands.jsonl）'}
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', **out}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
