#!/usr/bin/env python3
"""全自動模式的跑步器（docs/01 0.2「全自動模式」，先試用）。

用法：python3 tools/auto_run.py [--max-steps 30] [--claude claude]
  在設計 repo 根目錄執行。slices/PLAN.md 開頭區的「執行模式」要是「全自動」。
  每一圈開一個新的 claude -p session（一個 session 做一個動作，和手動時「一個 session 一步」相同），
  帶 tools/auto_hook.py 當 PreToolUse hook：不在禁止清單的工具呼叫直接放行並記錄，碰到禁止清單就擋下。
  AI 在回報最後一行寫「全自動：繼續」「全自動：完成（…）」「全自動：需要人（…）」；
  完成、需要人、沒有這一行、連續兩圈沒有任何改變，或到了 --max-steps，就停下來。

紀錄（.domain-auto/，不提交）：
  runs/<時間>_<n>.jsonl  每一圈 claude 的完整輸出（stream-json）
  runs.md                每一圈一行：時間、結果、AI 回報的第一行
  commands.jsonl         每個工具呼叫（auto_hook.py 寫）
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import md2build as mb  # noqa: E402

PROMPT = ('全自動模式（docs/01 0.2「全自動模式」）：沒有人在線上，不要問人、不要等人。'
          '先執行 /domain-status，然後只做下一個動作（一步的產出到送審、一次凍結〔含 AI 審查〕、或一次回頭修改），做完就結束這個 session。'
          '要人做的事照全自動模式的規定標記後往下，不要停。'
          '回報最後一行只寫其中一個：「全自動：繼續」「全自動：完成（原因）」「全自動：需要人（原因）」。')
MARK = re.compile(r'全自動：(繼續|完成|需要人)(?:（([^）]*)）)?')


def mode(repo):
    p = os.path.join(repo, 'slices', 'PLAN.md')
    if not os.path.exists(p):
        return ''
    for h2, h3, header, rows in mb.Doc(p).tables():
        if header[:2] == ['項目', '內容']:
            return next((c[1].strip() for no, c in rows if c[0].strip() == '執行模式'), '')
    return ''


def snapshot(repo):
    run = lambda *a: subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout
    return run('rev-parse', 'HEAD') + run('status', '--porcelain')


def last_reply(lines):
    reply = ''
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('type') == 'result' and e.get('result'):
            reply = e['result']
    return reply


def main():
    ap = argparse.ArgumentParser(description='全自動模式：一圈一個 claude -p session，連續往下做')
    ap.add_argument('--max-steps', type=int, default=30)
    ap.add_argument('--claude', default=os.environ.get('CLAUDE_BIN', 'claude'))
    a = ap.parse_args()
    repo = os.path.realpath(os.getcwd())
    m = mode(repo)
    if not m.startswith('全自動'):
        sys.exit(f'slices/PLAN.md 開頭區的「執行模式」是「{m or "（沒有）"}」，不是「全自動」；要全自動先改這一列（docs/02 切片地圖）。')
    auto = os.path.join(repo, '.domain-auto')
    os.makedirs(os.path.join(auto, 'runs'), exist_ok=True)
    settings = json.dumps({'hooks': {'PreToolUse': [{'matcher': '*', 'hooks': [
        {'type': 'command', 'command': f'{sys.executable} {os.path.join(HERE, "auto_hook.py")}'}]}]}})
    env = dict(os.environ, DOMAIN_AUTO='1', DOMAIN_AUTO_REPO=repo)
    same = 0
    for n in range(1, a.max_steps + 1):
        before = snapshot(repo)
        stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        out = os.path.join(auto, 'runs', f'{stamp}_{n}.jsonl')
        cmd = [a.claude, '-p', PROMPT, '--output-format', 'stream-json', '--verbose',
               '--settings', settings, '--permission-mode', 'acceptEdits']
        with open(out, 'w', encoding='utf-8') as f:
            p = subprocess.run(cmd, cwd=repo, env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
        reply = last_reply(open(out, encoding='utf-8').read().splitlines())
        found = MARK.findall(reply)
        kind, why = found[-1] if found else ('', '')
        first = (reply.strip().splitlines() or [''])[0][:120]
        with open(os.path.join(auto, 'runs.md'), 'a', encoding='utf-8') as f:
            f.write(f'- {stamp} 第 {n} 圈：{kind or "沒有回報結果"}{f"（{why}）" if why else ""}　{first}　（runs/{os.path.basename(out)}）\n')
        print(f'第 {n} 圈：{kind or "沒有回報結果"}{f"（{why}）" if why else ""}　{first}', flush=True)
        if p.returncode != 0 and not kind:
            sys.exit(f'claude 結束碼 {p.returncode}，停下來；看 {out}')
        if kind != '繼續':
            sys.exit(0 if kind == '完成' else 1)
        same = same + 1 if snapshot(repo) == before else 0
        if same >= 2:
            sys.exit('連續兩圈沒有任何改變（commit 與工作區都一樣），停下來；看 .domain-auto/runs.md')
    sys.exit(f'到了 --max-steps {a.max_steps}，停下來')


if __name__ == '__main__':
    main()
