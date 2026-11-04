#!/usr/bin/env python3
"""第 ⑥ 步的執行紀錄：執行一個指令，把輸出連同指令、執行目錄、實作版本、時間、結束碼
存成 slices/<切片>/06_evidence/results/<日期>_<時分秒>_<名稱>.log（docs/02 ⑥ `results/`）。

用法（在實作程式所在的資料夾執行，實作版本取那裡的 git）：
    python3 <設計 repo>/tools/run_evidence.py <切片> <名稱> -- <指令…>
例：
    python3 ../domain-trial/tools/run_evidence.py electricity-emission golden -- pytest tests/test_golden.py -v

log 由這支工具產生，AI 不手寫、不修改；結束碼照原指令回傳。它會執行包住的指令，所以和其他實作指令一樣要人逐條核准。
"""
import datetime
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('DESIGN_REPO') or os.path.dirname(HERE)   # 設計 repo：tools/ 的上一層（測試時用 DESIGN_REPO 指定）
HEADER = '# 執行紀錄（tools/run_evidence.py 產生，不手改）'


def git(*args):
    try:
        p = subprocess.run(['git', *args], capture_output=True, text=True, timeout=20)
        return p.stdout.strip() if p.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def version():
    """執行目錄的實作版本：<branch> @ <短 commit>（有未 commit 的修改：是／否）；不是 git repo 時寫明。"""
    commit = git('rev-parse', '--short', 'HEAD')
    if not commit:
        return '（執行目錄不是 git repo，沒有實作版本）'
    branch = git('rev-parse', '--abbrev-ref', 'HEAD') or '?'
    dirty = '是' if git('status', '--porcelain', '--untracked-files=no') else '否'
    return f'{branch} @ {commit}（有未 commit 的修改：{dirty}）'


def main(argv):
    if '--' not in argv or argv.index('--') != 2 or len(argv) < 4:
        sys.exit('用法：python3 tools/run_evidence.py <切片> <名稱> -- <指令…>')
    slice_, name, cmd = argv[0], argv[1], argv[3:]
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name):
        sys.exit(f'名稱只用英文小寫、數字與 -（現在是「{name}」）')
    sdir = os.path.join(ROOT, 'slices', slice_)
    if not os.path.isdir(sdir):
        sys.exit(f'沒有這條切片：slices/{slice_}')
    out_dir = os.path.join(sdir, '06_evidence', 'results')
    os.makedirs(out_dir, exist_ok=True)
    start = datetime.datetime.now().astimezone()
    path = os.path.join(out_dir, f"{start:%Y-%m-%d_%H%M%S}_{name}.log")
    ver = version()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
        code, output = p.returncode, p.stdout + (('\n' if p.stdout and not p.stdout.endswith('\n') else '') + p.stderr if p.stderr else '')
    except OSError as e:
        code, output = 127, f'無法執行：{e}\n'
    end = datetime.datetime.now().astimezone()
    shown = ' '.join(c if re.fullmatch(r"[\w./:=@%+,-]+", c) else "'" + c.replace("'", "'\\''") + "'" for c in cmd)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"{HEADER}\n- 切片：{slice_}\n- 名稱：{name}\n- 指令：{shown}\n- 執行目錄：{os.getcwd()}\n"
                f"- 實作版本：{ver}\n- 開始：{start.isoformat(timespec='seconds')}\n- 結束：{end.isoformat(timespec='seconds')}\n"
                f"- 結束碼：{code}\n\n## 輸出\n{output}")
    sys.stdout.write(output)
    print(f"\n執行紀錄：{os.path.relpath(path, sdir)}（結束碼 {code}）")
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
