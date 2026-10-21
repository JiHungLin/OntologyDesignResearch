#!/usr/bin/env python3
"""讀 Markdown 表格（和 md2build.py、lint.py 用同一個切欄方式）。讀表格用它，不用 awk、cut 或自己切「|」：
連續的空欄（| | |）、儲存格裡的 \\| 都會切錯。
用法：python3 tools/table.py <檔案> [--h2 <章節>] [--row <第一欄的值>] [--col <欄名>]
  不加選項：列出檔案中每張表格的位置、表頭與列數。
  --h2：只看某個 ## 章節下的表格（開頭符合即可）。
  --row：只印第一欄等於這個值的列（例：EQ-002、D-07、R65）。
  --col：只印這一欄（欄名開頭符合即可）；可以寫多次。
每一列印成「行號｜欄名：值」，空欄印成（空）。欄數和表頭不同的列另外列出。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2build as mb

def main():
    args = sys.argv[1:]
    if not args or '--help' in args:
        print(__doc__); return 0
    opts = {'--h2': None, '--row': None}
    cols = []
    for opt in ('--h2', '--row', '--col'):
        while opt in args:
            i = args.index(opt)
            if opt == '--col': cols.append(args[i + 1])
            else: opts[opt] = args[i + 1]
            del args[i:i + 2]
    path = args[0]
    if not os.path.exists(path):
        print(f'找不到 {path}'); return 1
    tables = mb.Doc(path).tables()
    shown = 0
    for h2, h3, header, rows in tables:
        if opts['--h2'] and not (h2 or '').startswith(opts['--h2']): continue
        where = ' > '.join(x for x in (h2, h3) if x) or '（檔案開頭）'
        if opts['--row'] is None and not cols:
            print(f'{where}：{len(header)} 欄、{len(rows)} 列｜{" | ".join(header)}')
            shown += 1; continue
        ks = list(range(len(header)))
        if cols:
            ks = [mb.col(header, c) for c in cols]
            if any(k is None for k in ks): continue
        for no, c in rows:
            if opts['--row'] is not None and c[0] != opts['--row']: continue
            shown += 1
            print(f'{path}:{no}　{where}')
            for k in ks:
                print(f'  {header[k]}：{c[k] if c[k] else "（空）"}')
    for p, no, msg in mb.problems:
        print(f'注意 {p}:{no} {msg}')
    if not shown:
        print('沒有符合的表格或列'); return 1
    return 2 if mb.problems else 0

if __name__ == '__main__':
    sys.exit(main())
