#!/usr/bin/env python3
"""全自動模式的跑步器（docs/01 0.2「全自動模式」，先試用）。

用法：python3 tools/auto_run.py [--max-steps 30] [--until-design-done] [--claude claude]
  在設計 repo 根目錄執行。slices/PLAN.md 開頭區的「執行模式」要是「全自動」。
  每一圈開一個新的 claude -p session（一個 session 做一個動作，和手動時「一個 session 一步」相同），
  帶 tools/auto_hook.py 當 PreToolUse hook：不在禁止清單的工具呼叫直接放行並記錄，碰到禁止清單就擋下。
  AI 在回報最後一行寫「全自動：繼續」「全自動：完成（…）」「全自動：需要人（…）」；
  完成、需要人、沒有這一行、連續兩圈沒有任何改變、執行模式被改回手動（下一圈開始前檢查），或到了 --max-steps，就停下來。
  --until-design-done：切片地圖上出現新的「設計完成（待驗證）」切片（有一條切片的 ⑤ 凍結了）就停，讓人先看一次 AI 代答的審查頁。
  要停下來又不改執行模式：建立 .domain-auto/stop（網頁的「停止」就是這樣做），這一圈做完就停。

紀錄（.domain-auto/，不提交）：
  runs/<時間>_<n>.jsonl  每一圈 claude 的完整輸出（stream-json）
  runs.md                每一圈一行：時間、結果、AI 回報的第一行
  commands.jsonl         每個工具呼叫（auto_hook.py 寫）
  state.json             正在跑還是停了、第幾圈、這一圈的紀錄檔、停下來的原因（網頁讀這個顯示進度、鎖住其他 AI 工作）
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
          '回報一律用繁體中文；最後一行只寫其中一個：「全自動：繼續」「全自動：完成（原因）」「全自動：需要人（原因）」。')
MARK = re.compile(r'全自動：(繼續|完成|需要人)(?:（([^）]*)）)?')


def mode(repo):
    p = os.path.join(repo, 'slices', 'PLAN.md')
    if not os.path.exists(p):
        return ''
    for h2, h3, header, rows in mb.Doc(p).tables():
        if header[:2] == ['項目', '內容']:
            return next((c[1].strip() for no, c in rows if c[0].strip() == '執行模式'), '')
    return ''


def design_done(repo):
    """切片地圖上狀態是「設計完成（待驗證）」的切片代號。"""
    p = os.path.join(repo, 'slices', 'PLAN.md')
    if not os.path.exists(p):
        return set()
    out = set()
    for h2, h3, header, rows in mb.Doc(p).tables():
        if h2 == '切片' and '狀態' in header:
            k = header.index('狀態')
            out |= {c[0].strip() for no, c in rows if c[k].strip().startswith('設計完成')}
    return out


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


class State:
    """.domain-auto/state.json：每次改都整份重寫（先寫暫存檔再換名，網頁不會讀到一半）。"""
    def __init__(self, auto, **kw):
        self.path = os.path.join(auto, 'state.json')
        self.d = dict(kw, pid=os.getpid(), running=True, started=datetime.now().isoformat(timespec='seconds'), round=0)
        self.save()

    def save(self, **kw):
        self.d.update(kw)
        with open(self.path + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)
        os.replace(self.path + '.tmp', self.path)


def main():
    try:
        run()
    except SystemExit as e:
        if STATE:
            msg = e.code if isinstance(e.code, str) else ''
            STATE.save(running=False, ended=datetime.now().isoformat(timespec='seconds'), code=1 if msg else (e.code or 0),
                       reason=msg or STATE.d.get('reason', ''))
        raise


STATE = None


def run():
    global STATE
    ap = argparse.ArgumentParser(description='全自動模式：一圈一個 claude -p session，連續往下做')
    ap.add_argument('--max-steps', type=int, default=30)
    ap.add_argument('--claude', default=os.environ.get('CLAUDE_BIN', 'claude'))
    ap.add_argument('--until-design-done', action='store_true', help='有一條切片的 ⑤ 凍結（設計完成）就停')
    a = ap.parse_args()
    repo = os.path.realpath(os.getcwd())
    m = mode(repo)
    if not m.startswith('全自動'):
        sys.exit(f'slices/PLAN.md 開頭區的「執行模式」是「{m or "（沒有）"}」，不是「全自動」；要全自動先改這一列（docs/02 切片地圖）。')
    auto = os.path.join(repo, '.domain-auto')
    os.makedirs(os.path.join(auto, 'runs'), exist_ok=True)
    stop = os.path.join(auto, 'stop')
    if os.path.exists(stop):
        os.remove(stop)
    STATE = State(auto, max_steps=a.max_steps, until_design_done=a.until_design_done)
    settings = json.dumps({'hooks': {'PreToolUse': [{'matcher': '*', 'hooks': [
        {'type': 'command', 'command': f'{sys.executable} {os.path.join(HERE, "auto_hook.py")}'}]}]}})
    env = dict(os.environ, DOMAIN_AUTO='1', DOMAIN_AUTO_REPO=repo)
    same = 0
    done_before = design_done(repo)
    for n in range(1, a.max_steps + 1):
        if n > 1 and not mode(repo).startswith('全自動'):   # 跑到一半改回手動（網頁的規劃頁或直接改 PLAN.md）：這一圈之後停
            sys.exit('執行模式已改回手動，停下來；之後照手動的流程做')
        if os.path.exists(stop):
            os.remove(stop)
            sys.exit('有人按了停止（.domain-auto/stop），這一圈做完後停下來；執行模式沒有改')
        before = snapshot(repo)
        stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        out = os.path.join(auto, 'runs', f'{stamp}_{n}.jsonl')
        STATE.save(round=n, log=os.path.basename(out), round_started=datetime.now().isoformat(timespec='seconds'))
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
        STATE.save(last=f'{kind or "沒有回報結果"}{f"（{why}）" if why else ""}　{first}')
        if kind in ('完成', '需要人'):
            STATE.save(reason=f'AI 回報「{kind}」{f"：{why}" if why else ""}')
        if p.returncode != 0 and not kind:
            sys.exit(f'claude 結束碼 {p.returncode}，停下來；看 {out}')
        if kind != '繼續':
            sys.exit(0 if kind == '完成' else 1)
        new = design_done(repo) - done_before
        if a.until_design_done and new:
            sys.exit(f'{"、".join(sorted(new))} 設計完成（⑤ 凍結），照 --until-design-done 停下來；先看 AI 代答的審查頁')
        same = same + 1 if snapshot(repo) == before else 0
        if same >= 2:
            sys.exit('連續兩圈沒有任何改變（commit 與工作區都一樣），停下來；看 .domain-auto/runs.md')
    sys.exit(f'到了 --max-steps {a.max_steps}，停下來')


if __name__ == '__main__':
    main()
