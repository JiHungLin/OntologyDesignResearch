"""從網頁開始、停止、中斷全自動跑步器（設計 repo 的 tools/auto_run.py），並讀它的進度。
跑步器本身不依賴網頁（終端機照樣能跑）；網頁只讀 .domain-auto/state.json、runs.md、runs/<圈>.jsonl，
停止是建立 .domain-auto/stop（這一圈做完就停），中斷是結束整個程序群組（這一圈做到一半的修改留在工作區，下一圈接著做）。"""
import json
import os
import signal
import subprocess
import sys

import kit
import sessions

_proc = None   # 這個伺服器開的跑步器（伺服器重開後改看 state.json 的 pid）


def _dir():
    return os.path.join(kit.repo(), '.domain-auto')


def _alive(pid):
    if _proc is not None and _proc.pid == pid:
        return _proc.poll() is None   # 自己開的子程序：poll() 也順便收掉結束的程序，免得 kill(pid, 0) 把殭屍當成還在跑
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def state():
    try:
        with open(os.path.join(_dir(), 'state.json'), encoding='utf-8') as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {'running': False, 'round': 0}
    if st.get('running') and not _alive(st.get('pid')):
        st.update(running=False, reason=st.get('reason') or '跑步器的程序不在了（被中斷或主機重開）')
    st['stopping'] = st.get('running') and os.path.exists(os.path.join(_dir(), 'stop'))
    return st


def running():
    return state()['running']


def rounds(limit=60):
    """runs.md 每一圈一行（新到舊）。"""
    try:
        with open(os.path.join(_dir(), 'runs.md'), encoding='utf-8') as f:
            lines = [l.strip()[2:] for l in f if l.startswith('- ')]
    except OSError:
        return []
    out = []
    for l in lines[-limit:][::-1]:
        log = l.rsplit('（runs/', 1)
        out.append({'text': log[0].strip(), 'log': log[1].rstrip('）') if len(log) > 1 else ''})
    return out


def denied(limit=20):
    """被禁止清單擋下的工具呼叫（新到舊）。"""
    try:
        with open(os.path.join(_dir(), 'commands.jsonl'), encoding='utf-8') as f:
            rows = [json.loads(l) for l in f if '"allow": false' in l]
    except (OSError, ValueError):
        return []
    return rows[-limit:][::-1]


def events(log, after=0):
    """某一圈的 AI 對話（照 AI 對話抽屜的事件格式）。"""
    if not log or '/' in log or not log.endswith('.jsonl'):
        raise KeyError(log)
    p = os.path.join(_dir(), 'runs', log)
    if not os.path.exists(p):
        raise KeyError(log)
    evs = []
    with open(p, encoding='utf-8', errors='replace') as f:
        for raw in f:
            try:
                out = sessions.summarize(json.loads(raw))
            except ValueError:
                continue
            if out is not None:
                evs += out if isinstance(out, list) else [out]
    st = state()
    return {'events': evs[after:], 'n': len(evs), 'running': bool(st['running'] and st.get('log') == log)}


def start(max_steps=40, until_design_done=True):
    global _proc
    if not sessions.auto_mode():
        raise ValueError('執行模式不是全自動，先在規劃頁改成全自動')
    if running():
        raise RuntimeError('全自動已經在跑了')
    other = next((x for x in sessions.load() if sessions.busy(x['id'])), None)
    if other:
        raise RuntimeError(f'AI 正在做「{other["name"]}」，做完再開始全自動')
    os.makedirs(_dir(), exist_ok=True)
    cmd = [sys.executable, os.path.join(kit.repo(), 'tools', 'auto_run.py'), '--max-steps', str(int(max_steps))]
    if until_design_done:
        cmd.append('--until-design-done')
    log = open(os.path.join(_dir(), 'runner.log'), 'a', encoding='utf-8')
    # 自己一個程序群組：伺服器重開不會帶走它，中斷時連同這一圈的 claude 一起結束
    _proc = subprocess.Popen(cmd, cwd=kit.repo(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    log.close()
    return {'pid': _proc.pid}


def stop():
    """這一圈做完就停（auto_run.py 每圈開始前看 .domain-auto/stop）。"""
    if not running():
        raise RuntimeError('全自動沒有在跑')
    open(os.path.join(_dir(), 'stop'), 'w').close()


def interrupt():
    """立刻結束跑步器與這一圈的 claude。做到一半的修改留在工作區（沒有 commit），下一圈的 /domain-status 會接著做。"""
    st = state()
    if not st['running']:
        raise RuntimeError('全自動沒有在跑')
    try:
        os.killpg(os.getpgid(st['pid']), signal.SIGTERM)
    except OSError as e:
        raise RuntimeError(f'中斷不了：{e}')
    st_path = os.path.join(_dir(), 'state.json')
    raw = json.load(open(st_path, encoding='utf-8'))
    raw.update(running=False, reason=f'在網頁上中斷（第 {raw.get("round", 0)} 圈做到一半；修改留在工作區，下一圈接著做）')
    with open(st_path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    os.replace(st_path + '.tmp', st_path)
    stopf = os.path.join(_dir(), 'stop')
    if os.path.exists(stopf):
        os.remove(stopf)
