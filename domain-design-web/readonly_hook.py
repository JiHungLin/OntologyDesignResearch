"""網頁裡的 AI（claude -p）用的 PreToolUse hook：只讀的串接指令直接放行。

claude -p 不能核准權限，允許清單又只能一個指令一個指令比對，AI 常把讀檔串成
「cd …; for f in …; do cat …; done」「grep … | head」被擋，再改用別的方法（白跑一趟，也讓人以為出錯）。
這裡把指令拆開，每一段都是只讀的指令、讀的路徑都在設計 repo（或網頁資料夾）裡，就回答 allow；
其他一律不表示意見，照原本的權限規則（允許清單、被擋就擋）。
"""
import json
import os
import re
import shlex
import sys

READ_ONLY = {'cd', 'ls', 'cat', 'head', 'tail', 'wc', 'grep', 'egrep', 'fgrep', 'rg', 'sed', 'awk', 'echo', 'printf',
             'sort', 'uniq', 'cut', 'tr', 'diff', 'find', 'nl', 'column', 'basename', 'dirname', 'pwd', 'true', 'test',
             '[', 'stat', 'file', 'realpath', 'readlink', 'tree', 'comm', 'paste', 'fold', 'expand', 'date'}
LOOP_WORDS = {'for', 'in', 'do', 'done', 'while', 'if', 'then', 'else', 'elif', 'fi', '!', '{', '}'}
SEPARATORS = {';', '&&', '||', '|', '\n', '(', ')', '&'}
SED_WRITE = re.compile(r'(^|[;\d$/,\s])\s*[weW](\s|$)')   # sed 的 w（寫檔）、e（執行）指令，前面可以有位址


def _ok_path(tok, roots):
    if not tok.startswith(('/', '~')):
        return '..' not in tok.split('/')
    p = os.path.realpath(os.path.expanduser(tok))
    return any(p == r or p.startswith(r + os.sep) for r in roots) or p == '/dev/null'


def read_only(cmd, roots):
    if re.search(r'\$\(|`|<<|>\s*[^&/]|>>|>\s*/(?!dev/null)', cmd):   # 指令替換、heredoc、寫檔（2>/dev/null 可以）
        return False
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=';&|()')
        lex.whitespace_split = True
        lex.whitespace = ' \t\r'
        toks = list(lex)
    except ValueError:
        return False
    head = True
    cur, pattern_left = None, False
    for t in toks:
        if t in SEPARATORS or t == '\n':
            head, cur = True, None
            continue
        if head:
            if t == 'for':   # for 變數 in 清單; do …：清單只檢查路徑，do 之後才是指令
                cur, head = 'for', False
                continue
            if t in LOOP_WORDS:
                continue
            if re.fullmatch(r'[A-Za-z_]\w*=.*', t):   # 變數設定（UA=…）
                continue
            if t not in READ_ONLY:
                return False
            cur, head = t, False
            pattern_left = t in ('grep', 'egrep', 'fgrep', 'rg', 'sed', 'awk')   # 第一個非選項參數是樣式或程式，不是路徑
            continue
        if t in ('do', 'then', 'else'):
            head, cur = True, None
            continue
        if t in LOOP_WORDS:
            continue
        if cur == 'sed' and (t.startswith('-i') or t == '--in-place' or SED_WRITE.search(t)):
            return False
        if cur == 'awk' and re.search(r'system|getline|print\s*>|printf\s*>|\|', t):
            return False
        if cur == 'find' and t in ('-exec', '-execdir', '-delete', '-ok', '-fprint', '-fprintf', '-fls'):
            return False
        if pattern_left and not t.startswith('-'):
            pattern_left = False
            if cur == 'sed' and SED_WRITE.search(t):
                return False
            continue
        if not t.startswith('-') and not _ok_path(t, roots):
            return False
    return True


def main():
    data = json.load(sys.stdin)
    if data.get('tool_name') != 'Bash':
        return
    cmd = (data.get('tool_input') or {}).get('command', '')
    roots = [os.path.realpath(data.get('cwd') or os.getcwd()), os.path.dirname(os.path.realpath(__file__))]
    if read_only(cmd, roots):
        json.dump({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow',
                                          'permissionDecisionReason': '只讀的指令（流程網頁 readonly_hook）'}}, sys.stdout)


if __name__ == '__main__':
    main()
