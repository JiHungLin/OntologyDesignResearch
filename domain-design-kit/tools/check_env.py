#!/usr/bin/env python3
"""第 ⑥ 步的驗證環境檢查：實作附的 Docker Compose 定義（compose.yaml）是不是一個隔離、可重建的沙盒
（docs/01 ⑥「驗證環境」）。只讀檔，不執行 docker。

用法：python3 tools/check_env.py <compose.yaml>
通過時結束碼 0，否則 1；最後一行印出環境指紋（定義檔與 Dockerfile 的 sha256 前 12 碼）。
tools/run_evidence.py 會自動呼叫這裡的 check()，把結果寫進執行紀錄的檔頭。
"""
import hashlib
import os
import re
import sys

import yaml

PINNED = re.compile(r'@sha256:[0-9a-f]{64}$')
LOCKFILES = ('requirements.txt', 'requirements.lock', 'poetry.lock', 'uv.lock', 'Pipfile.lock',
             'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'go.sum', 'Cargo.lock')


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def _inside(base, p):
    p = os.path.realpath(os.path.join(base, p))
    return p == base or p.startswith(base + os.sep)


def top(base):
    """定義檔所在的 git repo 根目錄（實作和設計同一個 repo 時，可以掛 slices/ 底下的 schema.sql）；不是 git repo 就是定義檔的資料夾。"""
    d = base
    while True:
        if os.path.exists(os.path.join(d, '.git')):
            return d
        up = os.path.dirname(d)
        if up == d:
            return base
        d = up


def check(path):
    """回傳 (問題清單, 指紋字串)。"""
    path = os.path.realpath(path)
    base = os.path.dirname(path)
    root = top(base)                      # bind mount 與 build context 只能在這裡面
    probs = []
    try:
        with open(path, encoding='utf-8') as f:
            doc = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        return [f'讀不了環境定義：{e}'], ''
    parts = [f'{os.path.basename(path)} sha256:{sha(path)}']
    services = doc.get('services') or {}
    if not services:
        probs.append('沒有任何 services')
    for name, s in services.items():
        s = s or {}
        where = f'services.{name}'
        if s.get('build'):
            b = s['build'] if isinstance(s['build'], dict) else {'context': s['build']}
            ctx = b.get('context', '.')
            if not _inside(root, os.path.join(base, ctx)):
                probs.append(f'{where}.build 的 context 在 repo 之外：{ctx}')
            df = os.path.join(base, ctx, b.get('dockerfile', 'Dockerfile'))
            if not os.path.exists(df):
                probs.append(f'{where} 的 Dockerfile 不存在：{os.path.relpath(df, base)}')
            else:
                parts.append(f'{os.path.relpath(df, base)} sha256:{sha(df)}')
                stages = set()                      # 多階段建置的 FROM <前一階段名稱> 不用固定
                for ln, line in enumerate(open(df, encoding='utf-8'), 1):
                    m = re.match(r'^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?', line, re.I)
                    if m and m.group(2):
                        stages.add(m.group(2).lower())
                    if m and m.group(1).lower() not in stages | {'scratch'} and not PINNED.search(m.group(1)):
                        probs.append(f'{os.path.relpath(df, base)}:{ln} 的 FROM {m.group(1)} 沒有用 @sha256: 固定版本')
        elif s.get('image'):
            if not PINNED.search(str(s['image'])):
                probs.append(f'{where}.image {s["image"]} 沒有用 @sha256: 固定版本')
        else:
            probs.append(f'{where} 沒有 image 也沒有 build')
        if s.get('privileged'):
            probs.append(f'{where} 用了 privileged')
        for k in ('network_mode', 'pid', 'ipc', 'userns_mode'):
            if str(s.get(k, '')).startswith('host'):
                probs.append(f'{where}.{k} 是 host，和主機共用')
        if s.get('cap_add'):
            probs.append(f'{where} 用了 cap_add：{s["cap_add"]}')
        for v in s.get('volumes') or []:
            src = v.get('source', '') if isinstance(v, dict) else str(v).split(':')[0]
            kind = v.get('type', '') if isinstance(v, dict) else ('bind' if src.startswith(('.', '/', '~')) else 'volume')
            if 'docker.sock' in src:
                probs.append(f'{where} 掛了 docker.sock，等於拿到主機的 docker')
            elif kind == 'bind' and (src.startswith(('/', '~')) or not _inside(root, os.path.join(base, src))):
                probs.append(f'{where} 掛了 repo 以外的主機路徑（只能用相對路徑掛 repo 裡的檔案）：{src}')
        for p in s.get('ports') or []:
            txt = str(p.get('host_ip', '') + ':' if isinstance(p, dict) and p.get('host_ip') else '') + (str(p.get('published', '')) if isinstance(p, dict) else str(p))
            if not txt.startswith('127.0.0.1:'):
                probs.append(f'{where}.ports {p} 對外開放；只綁 127.0.0.1（例：127.0.0.1:55432:5432），或不開 port')
    for lf in LOCKFILES:
        if os.path.exists(os.path.join(base, lf)):
            parts.append(f'{lf} sha256:{sha(os.path.join(base, lf))}')
    return probs, '；'.join(parts)


def main(argv):
    if len(argv) != 1:
        sys.exit('用法：python3 tools/check_env.py <compose.yaml>')
    probs, fp = check(argv[0])
    for p in probs:
        print(f'  ✗ {p}')
    print('驗證環境：' + ('通過' if not probs else f'{len(probs)} 個問題'))
    print(f'環境指紋：{fp}')
    return 1 if probs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
