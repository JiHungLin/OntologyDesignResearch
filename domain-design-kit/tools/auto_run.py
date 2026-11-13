#!/usr/bin/env python3
"""全自動模式的跑步器（docs/01 0.2「全自動模式」，先試用）。

用法：python3 tools/auto_run.py [--max-steps 30] [--until-design-done | --stop-every N] [--design-only] [--claude claude]
  在設計 repo 根目錄執行。slices/PLAN.md 開頭區的「執行模式」要是「全自動」。
  每一圈開一個新的 claude -p session（一個 session 做一個動作，和手動時「一個 session 一步」相同），
  帶 tools/auto_hook.py 當 PreToolUse hook：不在禁止清單的工具呼叫直接放行並記錄，碰到禁止清單就擋下。
  AI 在回報最後一行寫「全自動：繼續」「全自動：擱置（<切片>：…）」「全自動：完成（…）」「全自動：需要人（…）」；
  擱置是只卡住一條切片（docs/01 0.2「擱置」）：原因已收進那條切片的事後審查頁，跑步器接著做別條；
  完成、需要人、沒有這一行、連續兩圈沒有任何改變、執行模式被改回手動（下一圈開始前檢查），或到了 --max-steps，就停下來。
  --stop-every N：這次開始後累計 N 條切片的 ⑤ 凍結了就停（切片地圖上出現新的「設計完成（待驗證）」切片，或回頭修改後 ⑤ 重新凍結、
  多了 <切片>/05-vN tag），讓人先看一次 AI 代答的審查頁；0＝不因此停。--until-design-done 等於 --stop-every 1。
  --design-only：只做到第 ⑤ 步，不開始任何切片的 ⑥；地圖上沒有切片可以做 ①～⑤ 時 AI 回報完成。
  要停下來又不改執行模式：建立 .domain-auto/stop（網頁的「關閉全自動」就是這樣做），這一圈做完就停。
  上一次是做到一半被切斷的（網頁強制中斷、用量上限、程序不在了），第一圈先收拾：
  提示詞多一段，要 AI 看 git status、diff、最後的 tag，把中斷時的那個動作做完或還原；留下的 .git/index.lock 先刪掉。
  跑到一半碰到用量上限（「You've hit your … limit · resets 3:30pm (Asia/Taipei)」）：不停下來，等到重置時間再多 2 分鐘，
  下一圈先收拾再往下；等的時候 state.json 的 waiting_until 寫要等到幾點，有人按停止（.domain-auto/stop）就不等了。
  看不懂重置時間的每 30 分鐘試一次；累計等超過 --limit-wait-hours（預設 168，一週上限也等得到）就停下來。

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
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import md2build as mb  # noqa: E402

PROMPT = ('全自動模式（docs/01 0.2「全自動模式」）：沒有人在線上，不要問人、不要等人。'
          '先執行 /domain-status，然後只做下一個動作（一步的產出到送審、一次凍結〔含 AI 審查〕、或一次回頭修改），做完就結束這個 session。'
          '要人做的事照全自動模式的規定標記後往下，不要停。'
          '只卡住一條切片、要人才能往下的，照 docs/01 0.2「擱置」收進那條切片的事後審查頁，回報「全自動：擱置（<切片>：原因）」，下一圈做別條；'
          '擱置中的切片（事後審查頁有來源「擱置」的題目還沒答）和依賴它的切片都跳過。'
          '回報一律用繁體中文；最後一行只寫其中一個：「全自動：繼續」「全自動：擱置（切片：原因）」「全自動：完成（原因）」「全自動：需要人（原因）」。')
DESIGN_ONLY = ('這次只做到第 ⑤ 步：不開始任何切片的第 ⑥ 步。地圖上已經沒有切片可以做 ①～⑤（都設計完成或擱置中）時，'
               '回報「全自動：完成（地圖上的切片都做到 ⑤ 或擱置）」。')
RECOVER = ('上一次全自動在第 {n} 圈做到一半被切斷（{why}）。這一圈先收拾，不做新的動作：'
           '看 git status、git diff、git log -3、git tag 最後幾個，和 /domain-status 的結果，判斷中斷時在做哪一個動作'
           '（寫一步、回頭修改、凍結〔檔頭、CHANGELOG、commit、tag、core/ 同步〕、⑥ 的指令）；'
           '送審中（狀態「待檢查」、審查頁已產生）還沒 commit 是正常的，不算做到一半，不要還原。'
           '真的做到一半的（例：規則改了 CHANGELOG 沒記、檔頭已凍結但沒有 commit 或 tag、core/ 只同步一部分），把那個動作做完；'
           '無法判斷怎麼做完的，才還原那一部分到最後一個 commit 的樣子。在這一圈的回報寫出做了哪一種、改了哪些檔案。'
           '沒有做到一半的東西就直接說沒有。\n\n')
LIMIT = re.compile(r"hit your .*?limit", re.I)
RESET = re.compile(r'resets\s+(?:([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(?:at\s+)?)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?:\s*\(([^)]+)\))?', re.I)
LIMIT_MARGIN = float(os.environ.get('DOMAIN_AUTO_LIMIT_MARGIN', 120))   # 重置時間之後再多等幾秒
LIMIT_RETRY = float(os.environ.get('DOMAIN_AUTO_LIMIT_RETRY', 1800))    # 看不懂重置時間時，幾秒後再試
MARK = re.compile(r'全自動：(繼續|擱置|完成|需要人)(?:（([^）]*)）)?')


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


def frozen5(repo):
    """⑤ 凍結的 tag（<切片>/05-vN）：回頭修改後重新凍結也會多一個。"""
    out = subprocess.run(['git', '-C', repo, 'tag', '-l', '*/05-v*'], capture_output=True, text=True).stdout
    return set(out.split())


def reset_at(text, now=None):
    """用量上限的訊息 → 重置的時間（本機時間，naive）；看不懂回傳 None。"""
    m = RESET.search(text or '')
    if not m:
        return None
    mon, day, h, mi, ap, tz = m.groups()
    h = int(h) % 12 + (12 if ap.lower() == 'pm' else 0)
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(tz) if tz else None
    except Exception:
        zone = None
    now_z = datetime.now(zone) if zone else (now or datetime.now())
    if now and zone:
        now_z = now.astimezone(zone) if now.tzinfo else now.replace(tzinfo=datetime.now().astimezone().tzinfo).astimezone(zone)
    t = now_z.replace(hour=h, minute=int(mi or 0), second=0, microsecond=0)
    if mon:
        try:
            t = t.replace(month=datetime.strptime(mon, '%b').month, day=int(day))
        except ValueError:
            return None
        if t < now_z - timedelta(days=1):
            t = t.replace(year=t.year + 1)
    elif t <= now_z:
        t += timedelta(days=1)
    return t.astimezone().replace(tzinfo=None) if zone else t


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


def interrupted(auto):
    """上一次是不是做到一半被切斷：回傳 (第幾圈, 原因)，不是就回傳 None。"""
    try:
        with open(os.path.join(auto, 'state.json'), encoding='utf-8') as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = None
    if st:
        alive = False
        if st.get('running'):
            try:
                os.kill(st.get('pid'), 0)
                alive = True
            except (OSError, TypeError):
                pass
        if st.get('interrupted'):
            return st.get('round', 0), '網頁強制中斷'
        if st.get('running') and not alive:
            return st.get('round', 0), '跑步器的程序不在了'
        if str(st.get('last', '')).startswith('沒有回報結果'):
            return st.get('round', 0), st['last'][6:].strip() or '這一圈沒有回報結果'
        return None
    try:   # 還沒有 state.json 的舊紀錄：看 runs.md 最後一行
        with open(os.path.join(auto, 'runs.md'), encoding='utf-8') as f:
            last = [l for l in f if l.startswith('- ')][-1]
    except (OSError, IndexError):
        return None
    m = re.search(r'第 (\d+) 圈：沒有回報結果\s*(.*?)\s*（runs/', last)
    return (int(m.group(1)), m.group(2) or '這一圈沒有回報結果') if m else None


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
    ap.add_argument('--until-design-done', action='store_true', help='有一條切片的 ⑤ 凍結（設計完成）就停（＝--stop-every 1）')
    ap.add_argument('--stop-every', type=int, default=0, help='累計幾條切片的 ⑤ 凍結就停；0＝不因此停')
    ap.add_argument('--design-only', action='store_true', help='只做到第 ⑤ 步，不開始 ⑥')
    ap.add_argument('--limit-wait-hours', type=float, default=168, help='碰到用量上限時最多累計等幾小時')
    a = ap.parse_args()
    every = 1 if a.until_design_done and not a.stop_every else max(a.stop_every, 0)
    repo = os.path.realpath(os.getcwd())
    m = mode(repo)
    if not m.startswith('全自動'):
        sys.exit(f'slices/PLAN.md 開頭區的「執行模式」是「{m or "（沒有）"}」，不是「全自動」；要全自動先改這一列（docs/02 切片地圖）。')
    auto = os.path.join(repo, '.domain-auto')
    os.makedirs(os.path.join(auto, 'runs'), exist_ok=True)
    stop = os.path.join(auto, 'stop')
    if os.path.exists(stop):
        os.remove(stop)
    cut = interrupted(auto)
    lock = os.path.join(repo, '.git', 'index.lock')
    if cut and os.path.exists(lock):   # 被切斷的 git 指令留下的；這時沒有別的 AI 在跑（網頁在全自動跑時不開 AI 工作）
        os.remove(lock)
    STATE = State(auto, max_steps=a.max_steps, until_design_done=every == 1, stop_every=every, design_only=a.design_only, parked=[], designed=[],
                  recovered=f'第 {cut[0]} 圈（{cut[1]}）' if cut else '')
    settings = json.dumps({'hooks': {'PreToolUse': [{'matcher': '*', 'hooks': [
        {'type': 'command', 'command': f'{sys.executable} {os.path.join(HERE, "auto_hook.py")}'}]}]}})
    env = dict(os.environ, DOMAIN_AUTO='1', DOMAIN_AUTO_REPO=repo)
    same, waited = 0, 0.0
    done_before, tags_before = design_done(repo), frozen5(repo)
    n = 0
    while n < a.max_steps:
        n += 1
        if n > 1 and not mode(repo).startswith('全自動'):   # 跑到一半改回手動（網頁的規劃頁或直接改 PLAN.md）：這一圈之後停
            sys.exit('執行模式已改回手動，停下來；之後照手動的流程做')
        if os.path.exists(stop):
            os.remove(stop)
            sys.exit('有人按了停止（.domain-auto/stop），這一圈做完後停下來；執行模式沒有改')
        before = snapshot(repo)
        stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        out = os.path.join(auto, 'runs', f'{stamp}_{n}.jsonl')
        STATE.save(round=n, log=os.path.basename(out), round_started=datetime.now().isoformat(timespec='seconds'))
        prompt = (RECOVER.format(n=cut[0], why=cut[1]) if cut else '') + PROMPT + (DESIGN_ONLY if a.design_only else '')
        cut = None
        cmd = [a.claude, '-p', prompt, '--output-format', 'stream-json', '--verbose',
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
        if not kind and LIMIT.search(reply):
            # 用量上限：等到重置再接著跑，下一圈先收拾這一圈做到一半的
            until = reset_at(reply)
            now = datetime.now()
            until = until + timedelta(seconds=LIMIT_MARGIN) if until else now + timedelta(seconds=LIMIT_RETRY)
            hours = (until - now).total_seconds() / 3600
            if waited + hours > a.limit_wait_hours:
                sys.exit(f'碰到用量上限（{reply.strip()[:80]}），要等到 {until:%m-%d %H:%M}，超過 --limit-wait-hours {a.limit_wait_hours:g}，停下來')
            STATE.save(waiting_until=until.isoformat(timespec='minutes'), reason=f'碰到用量上限，等到 {until:%H:%M} 再接著跑')
            print(f'碰到用量上限，等到 {until:%m-%d %H:%M} 再接著跑', flush=True)
            while datetime.now() < until:
                if os.path.exists(stop):
                    os.remove(stop)
                    sys.exit('有人按了停止（.domain-auto/stop），不等用量重置，停下來；下次開始時第一圈先收拾')
                time.sleep(min(10, max(0.1, (until - datetime.now()).total_seconds())))
            waited += hours
            STATE.save(waiting_until=None, reason='')
            cut = (n, '用量上限')
            n -= 1                                   # 被上限切掉的這一圈不算進 --max-steps
            continue
        if p.returncode != 0 and not kind:
            sys.exit(f'claude 結束碼 {p.returncode}，停下來；看 {out}')
        if kind == '擱置':            # 只卡住一條切片：原因在那條切片的事後審查頁，接著做別條
            STATE.save(parked=STATE.d['parked'] + [why or '（沒寫哪條）'])
        elif kind != '繼續':
            sys.exit(0 if kind == '完成' else 1)
        # 新的設計完成切片，或已設計完成的切片回頭修改後 ⑤ 重新凍結（多了 <切片>/05-vN tag）
        new = (design_done(repo) - done_before) | {t.split('/')[0] for t in frozen5(repo) - tags_before}
        STATE.save(designed=sorted(new))
        if every and len(new) >= every:
            sys.exit(f'{"、".join(sorted(new))} 設計完成（⑤ 凍結），累計 {len(new)} 條，照設定停下來；先看 AI 代答的審查頁')
        same = same + 1 if snapshot(repo) == before else 0
        if same >= 2:
            sys.exit('連續兩圈沒有任何改變（commit 與工作區都一樣），停下來；看 .domain-auto/runs.md')
    sys.exit(f'到了 --max-steps {a.max_steps}，停下來')


if __name__ == '__main__':
    main()
